#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IndexNow 送信ヘルパー (2026-09-04 ユーザ裁定「自前で直接叩く」)。

何: 本番で「実際に変更/削除された頁URL」を IndexNow API(Bing/Yandex/Naver/Seznam 系が共有)へ POST する。
     Google は IndexNow を読まない(= Google 向けは sitemap + 内部リンクのまま)。
なぜ: Cloudflare Crawler Hints は edge cache の変化を拾う仕組みで、Worker+R2 配信では発火しない疑いがある。
鍵:  public/<key>.txt(32hex)。 鍵は「ホストの所有証明」であって秘密ではない(エンジンが取りに来る公開ファイル)。
     第三者にできるのは mangal-db.com のURLを送るノイズだけ(エンジンはホスト一致と鍵ファイルを検証する)。
     回す時はファイル名を変えるだけ。

流れ(デプロイ側は自動連鎖・全て try/except で包み、IndexNow の失敗でデプロイを止めない):
  _r2-sync.py             → 差分PUT/prune の .html キーを pending に積む(送信は finalize の edge purge 後)
  _weekly-finalize.py     → pending を送信(drain)
  _deploy-feature.py      → 自前 purge 後に積んで即 drain
  _deploy-differential.py → 自前 purge 後に積んで即 drain
  各スクリプト --no-indexnow で抑止。 --dry では到達しない。

★本文ハッシュ層 (2026-09-04 ユーザ裁定「案A-2」= pending_add_files):
  全頁HTMLに `_next/static/chunks/<contenthash>.js` が埋まるため、コードを1行直すだけで
  **全頁の sha256 が変わり**「変更頁」として全件が流れる(実測: 送信対象 90,281頁 に対し
  本当に内容が変わったのは 4,067頁 = 有効 4.5%)。 IndexNow FAQ は無変更URLの再送信を
  クロール枠の浪費と明記。 → PUT の判定(byte)とは別に **「クローラが読む部分」だけのハッシュ**を
  `.cache/indexnow-content.json` に持ち、実質無変更の頁は通知しない。

手動:
  python scripts/_indexnow.py --status           # pending 件数・鍵ファイルの本番生存
  python scripts/_indexnow.py --drain [--dry] [--max N]   # pending を送信(既定 10,000/回)
  python scripts/_indexnow.py --urls /a,/b       # 任意URL(パス)を即送信
  python scripts/_indexnow.py --clear            # pending を捨てる(422等が続く時の人手リセット)
  python scripts/_indexnow.py --selftest

送信規約: 1 POST ≤ 10,000 URL / JSON {host,key,keyLocation,urlList} / 200・202=受理、
  400=不正、403=鍵無効、422=URLがホスト外 or 鍵不一致、429=送りすぎ。
  送信前に https://mangal-db.com/<key>.txt が 200 かつ中身=鍵 を確認し、未配信なら pending に留める
  (鍵ファイル自体が次の機能蒸留/週次で R2 に上がるまでは送っても捨てられる)。
記録: .cache/indexnow-pending.json(未送信) / .cache/indexnow-log.jsonl(送信履歴)。
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = "mangal-db.com"
ENDPOINT = "https://api.indexnow.org/indexnow"
PENDING = os.path.join(ROOT, ".cache", "indexnow-pending.json")
CONTENT = os.path.join(ROOT, ".cache", "indexnow-content.json")   # R2キー → 本文ハッシュ
LOG = os.path.join(ROOT, ".cache", "indexnow-log.jsonl")
CHUNK = 10000            # 1 POST の上限(仕様)
MAX_PER_DRAIN = 10000    # 1回の drain で送る上限(超過分は pending に残して次回。 黙って捨てない)
UA = "Mozilla/5.0 (compatible; MANGAL-deploy/1.0; +https://mangal-db.com/about)"

# 送らない頁: 開発用の面(sitemap にも載せていない)・404・placeholder
EXCLUDE_RE = re.compile(
    r"^(home-design-\d+|nav-lab|nav-pack|obi-design|search-proto|tab-design|adult-triage|"
    r"audit-date-order|column-sample|404)$"
)


def find_key():
    """public/<32hex>.txt を鍵として拾う(robots.txt 等と混ざらないよう 32hex に限定)。 無ければ None。"""
    pub = os.path.join(ROOT, "public")
    if not os.path.isdir(pub):
        return None
    for fn in sorted(os.listdir(pub)):
        m = re.fullmatch(r"([0-9a-f]{32})\.txt", fn)
        if m:
            body = open(os.path.join(pub, fn), encoding="utf-8").read().strip()
            if body == m.group(1):
                return body
    return None


def key_to_url(key):
    """R2 キー → 正規URL(パス)。 対象外は None。
    manga/x.html → /manga/x, index.html → /, a/index.html → /a/, .txt(RSC)/_next/json/sitemap は除外。"""
    if not key.endswith(".html"):
        return None
    if key.startswith("_next/"):
        return None
    p = key[:-5]
    if p == "index":
        return "/"
    if p.endswith("/index"):
        p = p[:-5]
    segs = [s for s in p.split("/") if s]
    if not segs or any(s == "_empty" for s in segs):
        return None
    if EXCLUDE_RE.match(segs[0]):
        return None
    return "/" + p


def keys_to_urls(keys):
    out = []
    seen = set()
    for k in keys or []:
        u = key_to_url(k)
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _load_pending():
    if not os.path.exists(PENDING):
        return {"urls": {}}
    try:
        d = json.load(open(PENDING, encoding="utf-8"))
        if not isinstance(d, dict) or "urls" not in d:
            return {"urls": {}}
        return d
    except Exception:
        return {"urls": {}}


def _save_pending(d):
    os.makedirs(os.path.dirname(PENDING), exist_ok=True)
    json.dump(d, open(PENDING, "w", encoding="utf-8"), ensure_ascii=False, indent=0)


# ★本文ハッシュ (案A-2): ビルド由来のローダを落として「エンジンが実際に読む中身」だけ残す。
#   落とす = <script src>/インライン script(RSC flight = self.__next_f.push)/preload・stylesheet の <link>。
#     ハッシュ付きチャンク名だけをマスクする案(A-1)では、RSC flight の参照番号($L9→$Ld)が
#     木の変化で総振り直しになるため空振りが残る(live↔local 実測: A-1=差分60ブロック / A-2=4ブロックで全部が本物)。
#   残す   = <title>/<meta>/JSON-LD/本文マークアップ。
#   速度   = 128MB/s。 byte変化した .html だけに掛けるので、コード無変更の週はほぼ0秒。
_SCRIPT_RE = re.compile(rb"<script\b([^>]*)>.*?</script>", re.S)
# 落とす rel = ローダ/資材(preload…)と アイコン類。 アイコンの href は `?<16hex>` の
# キャッシュバスタ付きなので、差し替えれば全頁が「変更」になる。 canonical/alternate は SEO の中身なので残す。
_LINK_RE = re.compile(
    rb"<link\b[^>]*\brel=\"(?:[^\"]*\s)?"
    rb"(?:preload|stylesheet|modulepreload|prefetch|preconnect|dns-prefetch|icon|apple-touch-icon|manifest)"
    rb"(?:\s[^\"]*)?\"[^>]*>", re.S)


def content_bytes(data):
    """HTML(bytes) → 比較用の本文(bytes)。"""
    def _script(m):
        if b"application/ld+json" in m.group(1).lower():   # 構造化データ = 内容なので残す
            return m.group(0)
        return b"<script/>"
    return _LINK_RE.sub(b"", _SCRIPT_RE.sub(_script, data))


def content_hash(path):
    """ローカルHTMLの本文ハッシュ。 読めなければ None(= 判定不能 → 呼び手は送る側に倒す)。"""
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(content_bytes(f.read())).hexdigest()
    except Exception:
        return None


def _load_content():
    try:
        d = json.load(open(CONTENT, encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_content(d):
    os.makedirs(os.path.dirname(CONTENT), exist_ok=True)
    tmp = CONTENT + ".tmp"
    json.dump(d, open(tmp, "w", encoding="utf-8"))
    os.replace(tmp, CONTENT)   # 7MB級なので途中終了で壊さないよう原子的に置換


def _log(ev):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    ev = dict(ev, at=time.strftime("%Y-%m-%dT%H:%M:%S"))
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")


def pending_add(put_keys, del_keys=(), source="?"):
    """変更(put)/削除(del)された R2 キーを URL に写して pending へ積む。 戻り=人向け1行。"""
    d = _load_pending()
    now = time.strftime("%Y-%m-%d %H:%M")
    n_put = n_del = 0
    for u in keys_to_urls(put_keys):
        if u not in d["urls"]:
            n_put += 1
        d["urls"][u] = {"op": "put", "src": source, "at": now}
    for u in keys_to_urls(del_keys):
        if u not in d["urls"]:
            n_del += 1
        d["urls"][u] = {"op": "del", "src": source, "at": now}
    _save_pending(d)
    _log({"ev": "pending_add", "src": source, "put": n_put, "del": n_del, "total": len(d["urls"])})
    return f"IndexNow pending: +{n_put} 変更 / +{n_del} 削除 → 未送信 {len(d['urls']):,} URL ({source})"


def pending_add_files(put_pairs, del_keys=(), source="?", seed_pairs=(), dry=False):
    """★byte差分でなく「本文が変わった頁」だけを pending に積む入口 (2026-09-04)。

    put_pairs  = [(R2キー, ローカルpath)] = 実際に PUT した(= byte が変わった)キー。
                 .html は本文ハッシュを台帳と比べ、実質無変更(= チャンク名/RSC番号だけの差)は積まない。
    seed_pairs = 通知はしないが台帳には記録するキー(= ETag照合で PUT を省いた分。 台帳の穴を残さない)。
    del_keys   = 削除キー(そのまま積む。 404/410 の通知は仕様上の推奨動作)。

    ★初回(台帳が空)は「台帳を作るだけで一切通知しない」。 台帳消失時も同じ挙動 =
      いきなり9万URLを送りつける事故を構造的に封じる(1週分の通知を捨てる方に倒す)。
    """
    cm = _load_content()
    bootstrap = not cm
    notify, unchanged, fresh, unreadable = [], 0, 0, 0
    for key, path in put_pairs or ():
        if key_to_url(key) is None:      # 送信対象外(.txt / _next/ / 除外面)は台帳にも積まない
            continue
        h = content_hash(path)
        if h is None:
            unreadable += 1
            notify.append(key)           # 判定不能は送る側に倒す(台帳には書かない=次回再判定)
            continue
        old = cm.get(key)
        cm[key] = h
        if old == h:
            unchanged += 1
        elif old is None:
            if bootstrap:
                unchanged += 1           # 初回 = 既存頁の記録だけ
            else:
                fresh += 1
                notify.append(key)       # 台帳に無い = 新規URL
        else:
            notify.append(key)
    for key, path in seed_pairs or ():
        if key_to_url(key) is None:
            continue
        h = content_hash(path)
        if h:
            cm[key] = h
    for k in del_keys or ():
        cm.pop(k, None)
    if not dry:
        _save_content(cm)
    _log({"ev": "content_gate", "src": source, "notify": len(notify), "unchanged": unchanged,
          "new": fresh, "unreadable": unreadable, "bootstrap": bootstrap, "ledger": len(cm)})
    head = pending_add(notify, del_keys, source)
    detail = (f"  本文ハッシュ判定: 通知 {len(notify):,} / 実質無変更 {unchanged:,} は送らず"
              + (f" / 新規 {fresh:,}" if fresh else "")
              + (f" / 読めず {unreadable:,}" if unreadable else "")
              + (" ★初回=台帳作成のみ(通知なし)" if bootstrap else "")
              + f" / 台帳 {len(cm):,} キー"
              + ("\n  ※初回は基準が無いので1件も通知しない。 今回の変更を通知したい時だけ手動で: "
                 "python scripts/_indexnow.py --add-keys-file <R2キー一覧> → --drain" if bootstrap else ""))
    return head + "\n" + detail


def purge_token():
    """R2_PURGE_TOKEN を env / .env.local から。 無ければ ""(= purge できない)。"""
    t = os.environ.get("R2_PURGE_TOKEN", "")
    if t:
        return t.strip()
    for name in (".env.local", ".env"):
        p = os.path.join(ROOT, name)
        if os.path.exists(p):
            for ln in open(p, encoding="utf-8"):
                if ln.startswith("R2_PURGE_TOKEN=") and "=" in ln:
                    return ln.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def purge_urls(urls, token=None, batch=10, sleep=0.2, log_every=100, timeout=60):
    """★通知する前に、そのURLの edge cache を落とす (2026-09-04)。 戻り = (purged, 失敗したURLの集合)。

    なぜ: HTML は `s-maxage=86400`(エッジ1日)。 purge せずにクローラを呼ぶと **旧HTMLを掴ませる**
    = IndexNow を打つ意味が消える。 週次 finalize の purge は索引/JSON/sitemap だけで
    **変更した漫画頁を落としていなかった**(= 設計意図と実装のズレ)。
    ★batch=10 は worker の CPU 上限(≥50 で落ちる)に合わせた実測値。"""
    token = token if token is not None else purge_token()
    if not token:
        return 0, set(urls)
    purged, failed = 0, set()
    for i in range(0, len(urls), batch):
        part = urls[i:i + batch]
        try:
            rq = urllib.request.Request(f"https://{HOST}/api/purge", method="POST",
                                        data=json.dumps({"paths": part, "token": token}).encode(),
                                        headers={"content-type": "application/json", "User-Agent": UA})
            purged += json.load(urllib.request.urlopen(rq, timeout=timeout)).get("purged", 0)
        except Exception:
            failed.update(part)
        if log_every and (i // batch) % log_every == 0 and i:
            print(f"    purge {i:,}/{len(urls):,} (失敗 {len(failed):,})", flush=True)
        time.sleep(sleep)
    return purged, failed


def key_file_live(key, timeout=20):
    """本番の鍵ファイルが 200 かつ中身一致か。"""
    try:
        rq = urllib.request.Request(f"https://{HOST}/{key}.txt?v={int(time.time())}", headers={"User-Agent": UA})
        with urllib.request.urlopen(rq, timeout=timeout) as r:
            return r.status == 200 and r.read().decode("utf-8", "replace").strip() == key
    except Exception:
        return False


def _post(key, urls, timeout=60):
    body = json.dumps({
        "host": HOST,
        "key": key,
        "keyLocation": f"https://{HOST}/{key}.txt",
        "urlList": [f"https://{HOST}{u}" for u in urls],
    }).encode("utf-8")
    rq = urllib.request.Request(ENDPOINT, method="POST", data=body,
                                headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": UA})
    try:
        with urllib.request.urlopen(rq, timeout=timeout) as r:
            return r.status, ""
    except urllib.error.HTTPError as e:
        try:
            msg = e.read().decode("utf-8", "replace")[:200]
        except Exception:
            msg = ""
        return e.code, msg
    except Exception as e:  # ネットワーク断など
        return 0, str(e)[:200]


# ★送ってよいパスの形 (2026-09-04 実害): Git Bash(MSYS)は引数の `/` を `C:/Program Files/Git/` に
#   書き換えるため、`--urls /,/about` がトップでなく `https://mangal-db.com/C:/Program Files/Git/` を
#   送っていた(初回送信で実際に混入)。 呼び手側の事故を送信の一点で止める。
_URL_OK_RE = re.compile(r"^/(?![/\\])[^\s:\\]*$")


def sanitize_urls(urls):
    """(送ってよいURL, 弾いたURL)。 パス以外(Windows絶対パス・空白・スキーム混入)を落とす。"""
    ok, bad = [], []
    for u in urls:
        (ok if _URL_OK_RE.match(u or "") else bad).append(u)
    return ok, bad


def submit(urls, dry=False, verify=True):
    """URL(パス)群を ≤10,000 ずつ POST。 戻り = (受理したURLのlist, 失敗URL数, 人向け要約)。
    鍵未配信なら送らず ([], len, 理由) を返す(呼び手は pending に留める)。

    ★戻りが「件数」でなく「受理したURLそのもの」なのは意図的 (2026-09-04 修正):
      非429の失敗(403/422/400/ネットワーク断)では break せず次チャンクへ進むため、
      受理URLは先頭から連続とは限らない。 件数で前方一致削除すると
      「失敗したURLを消して成功したURLを残す」取り違えが起きる(再現テストで実証)。"""
    urls = list(dict.fromkeys(urls))
    urls, junk = sanitize_urls(urls)
    if junk:
        _log({"ev": "junk_url", "n": len(junk), "sample": junk[:3]})
        print(f"★IndexNow: URLの形が不正な {len(junk)} 件を送らず破棄: {junk[:3]}")
    if not urls:
        return [], 0, "IndexNow: 送るURLなし" + (f"(不正 {len(junk)} 件を破棄)" if junk else "")
    key = find_key()
    if not key:
        return [], len(urls), "IndexNow: 鍵ファイル(public/<32hex>.txt)が無い → 送信せず"
    if verify and not key_file_live(key):
        return [], len(urls), (f"IndexNow: https://{HOST}/{key}.txt が本番未配信(200+中身一致でない) → 送信せず pending に保持"
                               "(鍵ファイルは次の機能蒸留/週次で R2 に上がる)")
    if dry:
        return [], 0, f"IndexNow --dry: {len(urls):,} URL を {(len(urls) + CHUNK - 1) // CHUNK} POST で送る予定(未送信)"
    ok_urls = []
    bad = 0
    notes = []
    for i in range(0, len(urls), CHUNK):
        part = urls[i:i + CHUNK]
        code, msg = _post(key, part)
        if code == 429:  # 送りすぎ → 少し待って1回だけ再試行
            time.sleep(5)
            code, msg = _post(key, part)
        accepted = code in (200, 202)
        _log({"ev": "post", "n": len(part), "code": code, "msg": msg, "sample": part[:3]})
        if accepted:
            ok_urls.extend(part)
        else:
            bad += len(part)
            notes.append(f"HTTP {code} {msg}".strip())
            if code in (403, 429):
                # 403=鍵が無効(全チャンクで同じ結果) / 429=送りすぎ。 残りを投げても無駄なので中断し pending に残す
                bad += len(urls) - (i + len(part))
                break
    summary = f"IndexNow: 受理 {len(ok_urls):,} / 失敗 {bad:,} URL" + (f" ({'; '.join(notes[:2])})" if notes else "")
    return ok_urls, bad, summary


def drain(dry=False, verify=True, max_urls=MAX_PER_DRAIN, exclude=None, purge=False):
    """pending を送信し、受理分だけ pending から消す。 戻り=人向け要約。

    ★max_urls = 1回で送る上限(既定 10,000 = 1 POST)。 本文ハッシュ層(pending_add_files)を抜けて
      なお巨大になる唯一の場合 = テンプレート改修等で**本当に全頁の内容が変わった**時。
      その時も一度に9万を投げず、古い順に上限まで送って残りは pending に留める(= 次の drain で継続)。
      黙って切り捨てず、必ず残数を表示する。
    ★exclude = 今回は送らないURL(= edge purge に失敗した分)。 pending には残るので次回送られる。
    ★purge=True で、送る直前に自分でそのURLを purge する(週次 finalize 用。
      finalize の purge は索引/JSONだけで、変更した漫画頁を落としていなかった)。"""
    d = _load_pending()
    urls = list(d["urls"].keys())
    if not urls:
        return "IndexNow: pending なし"
    skipped_purge = 0
    if exclude:
        ex = set(exclude)
        urls = [u for u in urls if u not in ex]
        skipped_purge = len(d["urls"]) - len(urls)
        if not urls:
            return (f"IndexNow: 送信見送り(edge purge 未完了 {skipped_purge:,} URL)。 pending に保持 = "
                    f"次回のデプロイ/週次で送る")
    held = 0
    if max_urls and len(urls) > max_urls:
        held = len(urls) - max_urls
        urls = urls[:max_urls]           # dict は挿入順 = 古いものから送る
    if purge and not dry:
        # ★送る前に自分で落とす。 失敗したURLは今回送らない(旧HTMLを掴ませないため pending に残す)
        tok = purge_token()
        if not tok:
            return ("IndexNow: 送信見送り(R2_PURGE_TOKEN 未設定 = edge の旧HTMLを落とせない)。 "
                    f"pending {len(d['urls']):,} は保持")
        n_purged, pfail = purge_urls(urls, tok)
        print(f"    IndexNow前 purge: {len(urls):,} URL / purged {n_purged:,} / 失敗 {len(pfail):,}", flush=True)
        if pfail:
            urls = [u for u in urls if u not in pfail]
            skipped_purge += len(pfail)
            if not urls:
                return f"IndexNow: 送信見送り(purge が全滅 {len(pfail):,})。 pending {len(d['urls']):,} は保持"
    ok_urls, bad, summary = submit(urls, dry=dry, verify=verify)
    if ok_urls:
        # ★受理された URL そのものだけを消す(件数での前方一致削除は取り違える。 submit の docstring 参照)
        for u in ok_urls:
            d["urls"].pop(u, None)
        _save_pending(d)
    if held:
        summary += f" / 上限 {max_urls:,}/回 のため {held:,} URL は次回 drain に持ち越し"
    if skipped_purge:
        summary += f" / edge purge 未完了で見送り {skipped_purge:,}(pending に保持)"
    return summary + (f" / 残 {len(d['urls']):,}" if d["urls"] else "")


def status():
    d = _load_pending()
    key = find_key()
    live = key_file_live(key) if key else False
    ops = {}
    for v in d["urls"].values():
        ops[v.get("op", "?")] = ops.get(v.get("op", "?"), 0) + 1
    cm = _load_content()
    return (f"鍵: {key or '(無し)'} / 本番配信: {'OK' if live else 'NG(未配信 or 不一致)'}\n"
            f"pending: {len(d['urls']):,} URL {ops} (1回の送信上限 {MAX_PER_DRAIN:,})\n"
            f"本文ハッシュ台帳: {len(cm):,} キー" + ("  ★空 = 次回は台帳作成のみで通知なし" if not cm else "") + "\n"
            f"pending={PENDING}\ncontent={CONTENT}\nlog={LOG}")


def selftest():
    cases = {
        "index.html": "/",
        "manga/one-piece.html": "/manga/one-piece",
        "genre/action/completed.html": "/genre/action/completed",
        "magazine/weekly-shonen-jump/2.html": "/magazine/weekly-shonen-jump/2",
        "shinkan/index.html": "/shinkan/",
        "manga/one-piece.txt": None,
        "_next/static/chunks/a.js": None,
        "404.html": None,
        "manga/_empty.html": None,
        "home-design-12.html": None,
        "sitemap-1.xml": None,
        "manga-list-index.json": None,
    }
    bad = [(k, v, key_to_url(k)) for k, v in cases.items() if key_to_url(k) != v]
    assert not bad, bad
    assert keys_to_urls(["a.html", "a.html", "b.txt"]) == ["/a"]

    # ★本文ハッシュ: ビルド由来の差(チャンク名・RSC flight・css link)は同一、本文の差は別。
    def page(chunk, body, extra=""):
        return (f'<html><head><title>T</title><meta name="description" content="D">'
                f'<link rel="stylesheet" href="/_next/static/css/{chunk}.css"/>'
                f'<script src="/_next/static/chunks/main-app-{chunk}.js" async=""></script>'
                f'<script type="application/ld+json">{{"@type":"Book","name":"{body}"}}</script>'
                f'</head><body><h1>{body}</h1>{extra}'
                f'<script>self.__next_f.push([1,"3:I[6534,[\\"2619\\",\\"static/chunks/{chunk}.js\\"]]\\n{body}"])</script>'
                f'</body></html>').encode()
    h1 = hashlib.sha256(content_bytes(page("aaaa1111", "ワンピース"))).hexdigest()
    h2 = hashlib.sha256(content_bytes(page("bbbb2222", "ワンピース"))).hexdigest()
    h3 = hashlib.sha256(content_bytes(page("aaaa1111", "ワンピース", "<p>103巻</p>"))).hexdigest()
    h4 = hashlib.sha256(content_bytes(page("aaaa1111", "ナルト"))).hexdigest()
    assert h1 == h2, "チャンク名だけの差で本文ハッシュが変わってはいけない"
    assert h1 != h3, "本文の追加を取り逃している"
    assert h1 != h4, "見出し/JSON-LD の変化を取り逃している"
    assert b"ld+json" in content_bytes(page("aaaa1111", "ワンピース")), "JSON-LD は残すこと"
    assert b"__next_f" not in content_bytes(page("aaaa1111", "ワンピース")), "RSC flight は落とすこと"

    # ★URLの形の番人(Git Bash の `/` → `C:/Program Files/Git/` 化を送信の一点で止める)
    ok, bad = sanitize_urls(["/", "/manga/one-piece", "/genre/action/completed",
                             "/C:/Program Files/Git/", "/a b", "//evil.com", "https://x/y", "", "/x\\y"])
    assert ok == ["/", "/manga/one-piece", "/genre/action/completed"], ok
    assert len(bad) == 6, bad
    print("selftest OK")


def main():
    ap = argparse.ArgumentParser(description="IndexNow 送信ヘルパー")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--drain", action="store_true", help="pending を送信")
    ap.add_argument("--urls", help="即送信するパス(カンマ区切り。例 /manga/one-piece,/genre/action)")
    ap.add_argument("--add-keys-file", help="R2キー一覧(1行1キー)を pending に積む")
    ap.add_argument("--clear", action="store_true", help="pending を捨てる")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--purge", action="store_true",
                    help="送る直前に対象URLの edge cache を落とす(失敗分は送らず pending に残す)")
    ap.add_argument("--max", type=int, default=MAX_PER_DRAIN,
                    help=f"1回の drain で送る上限(既定 {MAX_PER_DRAIN:,}。 超過分は pending に残る)")
    ap.add_argument("--no-verify", action="store_true", help="鍵ファイルの本番生存確認を省く")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest(); return
    if a.clear:
        _save_pending({"urls": {}}); print("pending cleared"); return
    if a.add_keys_file:
        keys = [ln.strip() for ln in open(a.add_keys_file, encoding="utf-8") if ln.strip()]
        print(pending_add(keys, [], "manual")); return
    if a.urls:
        urls = [u.strip() for u in a.urls.split(",") if u.strip()]
        urls = [u if u.startswith("/") else "/" + u for u in urls]
        _, _, s = submit(urls, dry=a.dry, verify=not a.no_verify); print(s); return
    if a.drain:
        print(drain(dry=a.dry, verify=not a.no_verify, max_urls=a.max, purge=a.purge)); return
    print(status())


if __name__ == "__main__":
    main()
