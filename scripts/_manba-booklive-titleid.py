#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""manba経由で BookLive! の title_id を得る (2026-09-07 新設・試験採取)

★狙い: 2026-08-29の規制事故以降、試し読みの新規取得手段が絶えていた([[booklive_access_incident]])。
  我々に必要なのは **title_id だけ**(URLは title_id+巻番号3桁 から**構築**する
  = [[tameshiyomi_url_is_constructed]])。manba.co.jp の作品ページは各ストアへの
  自サイト内リンク `/boards/<id>/stores/booklive` を持ち、その **302 Location** に
  `...vc_url=https%3A%2F%2Fbooklive.jp%2Fproduct%2Findex%2Ftitle_id%2F<ID>%2Fvol_no%2F001...`
  が入っている。**Locationを読むだけでリダイレクトは追わない**ので booklive.jp には
  1リクエストも出さない = 停止札(BOOKLIVE-BLOCKED.md)を破らない。

★実証(2026-09-07): チェンソーマン board=97981 → title_id=582763 = 我々のマップの値と完全一致。

## 取得は2リクエスト/作品
  ① GET /search?q=<題>                   … サーバ描画。board id / 題 / 著者 / 「N巻まで刊行」が取れる
  ② GET /boards/<id>/stores/booklive     … 302 の Location から title_id

## 同定ゲート(★誤同定は別作品のリンクを焼くので厳しく。2段)
  T1: 正規化題が**完全一致** かつ (著者overlap **または** 巻数が我々の値と ±3以内)
  T2: 正規化題が**包含一致**(どちらかがどちらかを含む) かつ 著者overlap **かつ** 巻数±3
      ★T2で and を要求するのは、manbaが正式題(親題+外伝+副題)を使うため包含が緩いから。
        例= 我々「とある科学の超電磁砲」/ manba「とある魔術の禁書目録外伝 とある科学の超電磁砲」。
        片側だけだと同題アンソロジー/外伝(別作画)を掴む(2026-09-07 実測で確認)。
  どちらの段でも **候補が1件に絞れた時だけ採用**。複数なら `ambiguous` で保留(偽採用より偽保留)。

## 事故則(= BookLive事故の教訓をそのまま適用)
  - **直列のみ・並列禁止**。`_rate_gate.wait("manba", --sleep)` で他柱と合算直列化。
  - **失敗を否定記録にしない**: 429/403/5xx/timeout は**即中断**して何も書かない
    ([[feedback_no_negative_record_on_failure]])。書くのは想定内の応答だけ。
  - 台帳は追記のみ・再開可能(既に結果のある slug は skip)。

usage:
  python scripts/_manba-booklive-titleid.py --slugs-file <file> [--sleep 5] [--limit 0]
  python scripts/_manba-booklive-titleid.py --from-list   # no-tameshiyomi-active.tsv の未検査分
出力: .cache/manba-titleid.jsonl (1行1作品) / 標準出力にサマリ
"""
import argparse, gzip, io, json, os, re, sys, time, unicodedata
import urllib.error, urllib.parse, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import _rate_gate

# ★台帳は git追跡の seed に置く(.cache だと /clear・PC移行・掃除で消える。
#   CLAUDE.md「holes等の成果は .cache 置きっぱにせず永続化」と同じ理由)。追記のみ・純粋追加。
LEDGER = os.path.join(ROOT, "data", "seeds", "manba-titleid.jsonl")
_OLD_LEDGER = os.path.join(ROOT, ".cache", "manba-titleid.jsonl")
if not os.path.exists(LEDGER) and os.path.exists(_OLD_LEDGER):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    import shutil as _sh
    _sh.copy(_OLD_LEDGER, LEDGER)          # 旧置き場からの一度きりの移行
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """★リダイレクトを追わない = booklive.jp / valuecommerce へ1リクエストも出さない。"""

    def redirect_request(self, *a, **k):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


class Abort(Exception):
    """規制/障害の疑い= 即中断。何も台帳に書かない。"""


def _get(url, sleep, allow_redirect_status=False):
    _rate_gate.wait("manba", sleep)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "ja,en;q=0.8", "Accept-Encoding": "gzip"})
    try:
        r = _OPENER.open(req, timeout=30)
        body = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
        return r.status, dict(r.headers), body.decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308) and allow_redirect_status:
            return e.code, dict(e.headers), ""
        if e.code == 404:
            return 404, {}, ""
        raise Abort(f"HTTP {e.code} at {url}")   # 429/403/5xx = 規制/障害 → 即中断
    except Exception as e:
        raise Abort(f"{type(e).__name__} at {url}: {e}")


def nk(s):
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = re.sub(r"[（(][^）)]{0,20}[）)]", "", s)
    s = re.sub(r"[\s　・,.。、!！?？:：;；'\"“”‘’〜~\-−ー―_/\\|]", "", s)
    return s.lower()


def akey(s):
    return re.sub(r"[\s　・,]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()


_CARD = re.compile(
    r'data-tracking-on-view="board_(?P<id>\d+)".*?'
    r'<h3 class="title"><a href="/boards/(?P=id)">(?P<title>[^<]*)</a></h3>'
    r'(?P<rest>.*?)(?=data-tracking-on-view="board_|\Z)', re.S)
_AUTHORS = re.compile(r'<a href="/authors/\d+">([^<]+)</a>')
_VOLS = re.compile(r'>(\d+)巻まで刊行<')

# ★版違いboard(2026-09-07 実測): manbaは同一作でも版/形態ごとに別boardを立てる。
#   包含一致(T2)は題の尻に付くこの手の版表記を吸収してしまうので、**我々の題に無いのに
#   manba側にだけ在る**時は採用せず flag する(その title_id は別商品を指す)。
#   実害候補= 「終の退魔師 ―エンダーガイスター―＜無修正ver.＞」(我々は通常版)
#            「結婚商売［完全版］【特装版】」(manba4巻/我々7巻)
_EDITION = re.compile(r"無修正|完全版|特装版|限定版|合冊版|分冊版|新装版|愛蔵版|フルカラー版|カラー版|"
                      r"コミックス版|単行本版|連載版|マイクロ|【電子|オリジナル版", re.I)


def search_boards(title, sleep):
    st, _h, html = _get("https://manba.co.jp/search?q=" + urllib.parse.quote(title), sleep)
    if st != 200:
        raise Abort(f"search status {st}")
    out = []
    for m in _CARD.finditer(html):
        rest = m.group("rest")
        out.append({"board": m.group("id"), "title": m.group("title"),
                    "authors": _AUTHORS.findall(rest),
                    "vols": int(_VOLS.search(rest).group(1)) if _VOLS.search(rest) else None})
    return out


def booklive_title_id(board, sleep):
    """→ (title_id|None, note)。302 Location を読むだけ(追わない)。"""
    st, hdr, _b = _get(f"https://manba.co.jp/boards/{board}/stores/booklive", sleep,
                       allow_redirect_status=True)
    if st == 404:
        return None, "no_store(404)"
    if st == 200:
        return None, "no_store(200=遷移先なし)"
    loc = urllib.parse.unquote(hdr.get("Location") or "")
    m = re.search(r"booklive\.jp/product/index/title_id/(\d+)", loc)
    if m:
        return m.group(1), ""
    return None, f"location解析不能: {loc[:120]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs-file")
    ap.add_argument("--from-list", action="store_true",
                    help="no-tameshiyomi-active.tsv 由来(既定=試し読み未検査分のみ。--all で全件)")
    ap.add_argument("--sleep", type=float, default=5.0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--vol-tol", type=int, default=3, help="巻数一致の許容差")
    ap.add_argument("--redo", help="台帳の指定resultを再走(既定語 nonhit = no_match,gate_ng,ambiguous,no_store)")
    ap.add_argument("--status", action="store_true", help="現在地(台帳の内訳と残件)を出して終了。★再開時はまずこれ")
    ap.add_argument("--all", action="store_true",
                    help="no-tameshiyomi-active.tsv の**全件**を対象(既定の--from-listは未検査分だけ)")
    a = ap.parse_args()

    idx = json.load(io.open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    F = {n: i for i, n in enumerate(idx["f"])}
    by_slug = {r[F["slug"]]: r for r in idx["d"]}

    if a.slugs_file:
        want = [l.strip() for l in io.open(a.slugs_file, encoding="utf-8") if l.strip()]
    elif a.from_list:
        p = os.path.join(ROOT, "docs", "production-diagnostics", "no-tameshiyomi-active.tsv")
        rows = [l.rstrip("\n").split("\t") for l in io.open(p, encoding="utf-8")]
        hdr = rows[0]; ci = hdr.index("slug")
        tried = set()
        tp = os.path.join(ROOT, ".cache", "tameshiyomi", "recheck-attempted.txt")
        if os.path.exists(tp):
            tried = {l.strip() for l in io.open(tp, encoding="utf-8") if l.strip()}
        want = [r[ci] for r in rows[1:]] if a.all else [r[ci] for r in rows[1:] if r[ci] not in tried]
    else:
        sys.exit("--slugs-file か --from-list が要る")

    if a.status:
        last = {}
        if os.path.exists(LEDGER):
            for l in io.open(LEDGER, encoding="utf-8"):
                try:
                    r = json.loads(l); last[r["slug"]] = r
                except Exception:
                    pass
        from collections import Counter
        c = Counter(r.get("result") for r in last.values())
        print(f"台帳 {LEDGER}\n  記録済み {len(last)} 作品: " +
              " / ".join(f"{k} {v}" for k, v in c.most_common()))
        tgt = [s for s in want if s not in last]
        redoable = [s for s, r in last.items()
                    if r.get("result") in ("no_match", "gate_ng", "ambiguous", "no_store")]
        print(f"  今の対象リスト {len(want)} 件のうち **未採取 {len(tgt)}**"
              f"  (2req×5秒 ≈ {len(tgt) * 2 * a.sleep / 60:.0f}分)")
        print(f"  再走可(非hit) {len(redoable)} 件 … --redo nonhit")
        print(f"  ★適用可 = result:hit の {c.get('hit', 0)} 件"
              f"(hit_edition_suspect {c.get('hit_edition_suspect', 0)} 件は版違い=適用しない)")
        return

    # ★台帳は追記式=同一slugは**最終行勝ち**で読む(再走で結果が更新される)
    last = {}
    if os.path.exists(LEDGER):
        for l in io.open(LEDGER, encoding="utf-8"):
            try:
                r = json.loads(l)
                last[r["slug"]] = r
            except Exception:
                pass
    if a.redo:
        redo = set(a.redo.split(",")) if a.redo != "nonhit" else {
            "no_match", "gate_ng", "ambiguous", "no_store"}
        done = {s for s, r in last.items() if r.get("result") not in redo}
        print(f"--redo {sorted(redo)}: 再走対象 {len(last) - len(done)} 件")
    else:
        done = set(last)
    todo = [s for s in want if s not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f"対象 {len(todo)} 作品(既済 {len(want) - len(todo)} skip) / 間隔 {a.sleep}s / "
          f"2req/作品 ≈ {len(todo) * 2 * a.sleep / 60:.0f}分", flush=True)

    n_hit = n_amb = n_none = n_nostore = n_ed = 0
    out = io.open(LEDGER, "a", encoding="utf-8", newline="\n")
    try:
        for i, slug in enumerate(todo, 1):
            row = by_slug.get(slug)
            if not row:
                print(f"[{i}/{len(todo)}] {slug}: 索引に無い=skip"); continue
            title = row[F["title"]]
            ours_v = row[F["max_edition_volumes"]] or 0
            ours_a = {akey(str(x).split("\t")[0]) for x in (row[F["authors"]] or [])}
            ours_a |= {akey(str(x).split("\t")[0]) for x in (row[F["original_authors"]] or [])}
            cands = search_boards(title, a.sleep)
            nt = nk(title)

            def _au(c):
                return bool({akey(x) for x in c["authors"]} & ours_a)

            def _vo(c):
                return c["vols"] is not None and abs(c["vols"] - ours_v) <= a.vol_tol

            exact = [c for c in cands if nk(c["title"]) == nt]
            ok = [c for c in exact if _au(c) or _vo(c)]
            tier = "T1"
            if len(ok) != 1 and not exact:
                # ★T2: 包含一致(著者 and 巻の両方を要求)
                part = [c for c in cands if nt and (nt in nk(c["title"]) or nk(c["title"]) in nt)]
                ok2 = [c for c in part if _au(c) and _vo(c)]
                if len(ok2) == 1:
                    ok, exact, tier = ok2, part, "T2"
                elif ok2:
                    exact, tier = ok2, "T2"          # 複数 = ambiguous として記録
                    ok = []
            rec = {"slug": slug, "title": title, "ours_vols": ours_v, "tier": tier,
                   "cands": len(cands), "exact": len(exact), "at": time.strftime("%Y-%m-%d")}
            if len(ok) != 1:
                rec["result"] = "ambiguous" if len(ok) > 1 else ("no_match" if not exact else "gate_ng")
                rec["detail"] = [{"b": c["board"], "t": c["title"], "a": c["authors"], "v": c["vols"]}
                                 for c in (exact or cands)[:5]]   # ★一致0でも上位候補を残す(再走無しで診断)
                n_amb += 1 if len(ok) > 1 else 0
                n_none += 1 if len(ok) == 0 else 0
                print(f"[{i}/{len(todo)}] {slug}: {rec['result']} (候補{len(cands)}/完全一致{len(exact)}) {title}", flush=True)
            else:
                c = ok[0]
                # ★版違いガード: manba題にだけ版表記が在る = 別商品のtitle_id
                ed = _EDITION.search(c["title"]) and not _EDITION.search(title)
                tid, note = booklive_title_id(c["board"], a.sleep)
                if tid and ed:
                    rec["edition_flag"] = _EDITION.search(c["title"]).group(0)
                rec.update({"board": c["board"], "manba_title": c["title"],
                            "manba_authors": c["authors"], "manba_vols": c["vols"],
                            "title_id": tid, "note": note,
                            "result": ("hit_edition_suspect" if (tid and rec.get("edition_flag"))
                                       else ("hit" if tid else "no_store"))})
                if tid and rec.get("edition_flag"):
                    n_ed += 1
                elif tid:
                    n_hit += 1
                else:
                    n_nostore += 1
                print(f"[{i}/{len(todo)}] {slug}: {('★版違い疑い(' + rec['edition_flag'] + ') title_id=' + tid) if (tid and rec.get('edition_flag')) else ('title_id=' + tid if tid else note)} "
                      f"(board={c['board']} 巻{c['vols']}/我々{ours_v}) {title}", flush=True)
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
    except Abort as e:
        print(f"\n★中断(規制/障害の疑い): {e}\n  = 否定記録は一切書いていない。時間を置いて再開(台帳から再開可)。")
        out.close()
        sys.exit(2)
    except KeyboardInterrupt:
        print("\n中断(ユーザ)。台帳から再開可。")
    out.close()
    print(f"\n=== 結果 === hit {n_hit} / 取扱なし {n_nostore} / 同定不能(複数) {n_amb} / 一致なし {n_none}")
    print(f"台帳: {LEDGER}")


if __name__ == "__main__":
    main()
