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

手動:
  python scripts/_indexnow.py --status           # pending 件数・鍵ファイルの本番生存
  python scripts/_indexnow.py --drain [--dry]    # pending を送信
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
LOG = os.path.join(ROOT, ".cache", "indexnow-log.jsonl")
CHUNK = 10000
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


def submit(urls, dry=False, verify=True):
    """URL(パス)群を ≤10,000 ずつ POST。 戻り = (受理URL数, 失敗URL数, 人向け要約)。
    鍵未配信なら送らず (0, len, 理由) を返す(呼び手は pending に留める)。"""
    urls = list(dict.fromkeys(urls))
    if not urls:
        return 0, 0, "IndexNow: 送るURLなし"
    key = find_key()
    if not key:
        return 0, len(urls), "IndexNow: 鍵ファイル(public/<32hex>.txt)が無い → 送信せず"
    if verify and not key_file_live(key):
        return 0, len(urls), (f"IndexNow: https://{HOST}/{key}.txt が本番未配信(200+中身一致でない) → 送信せず pending に保持"
                              "(鍵ファイルは次の機能蒸留/週次で R2 に上がる)")
    if dry:
        return 0, 0, f"IndexNow --dry: {len(urls):,} URL を {(len(urls) + CHUNK - 1) // CHUNK} POST で送る予定(未送信)"
    ok = bad = 0
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
            ok += len(part)
        else:
            bad += len(part)
            notes.append(f"HTTP {code} {msg}".strip())
            if code == 429:
                break  # 以降も弾かれる = 残りは pending に残す
    summary = f"IndexNow: 受理 {ok:,} / 失敗 {bad:,} URL" + (f" ({'; '.join(notes[:2])})" if notes else "")
    return ok, bad, summary


def drain(dry=False, verify=True):
    """pending を送信し、受理分だけ pending から消す。 戻り=人向け要約。"""
    d = _load_pending()
    urls = list(d["urls"].keys())
    if not urls:
        return "IndexNow: pending なし"
    ok, bad, summary = submit(urls, dry=dry, verify=verify)
    if ok:
        # 受理は先頭から ok 件(POST は順序通り・失敗チャンクで break するので前方一致で消せる)
        for u in urls[:ok]:
            d["urls"].pop(u, None)
        _save_pending(d)
    return summary + (f" / 残 {len(d['urls']):,}" if d["urls"] else "")


def status():
    d = _load_pending()
    key = find_key()
    live = key_file_live(key) if key else False
    ops = {}
    for v in d["urls"].values():
        ops[v.get("op", "?")] = ops.get(v.get("op", "?"), 0) + 1
    return (f"鍵: {key or '(無し)'} / 本番配信: {'OK' if live else 'NG(未配信 or 不一致)'}\n"
            f"pending: {len(d['urls']):,} URL {ops}\n"
            f"pending={PENDING}\nlog={LOG}")


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
    print("selftest OK")


def main():
    ap = argparse.ArgumentParser(description="IndexNow 送信ヘルパー")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--drain", action="store_true", help="pending を送信")
    ap.add_argument("--urls", help="即送信するパス(カンマ区切り。例 /manga/one-piece,/genre/action)")
    ap.add_argument("--add-keys-file", help="R2キー一覧(1行1キー)を pending に積む")
    ap.add_argument("--clear", action="store_true", help="pending を捨てる")
    ap.add_argument("--dry", action="store_true")
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
        print(drain(dry=a.dry, verify=not a.no_verify)); return
    print(status())


if __name__ == "__main__":
    main()
