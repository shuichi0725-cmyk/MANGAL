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

## 同定ゲート(★誤同定は別作品のリンクを焼くので厳しく)
  正規化題が完全一致 かつ (著者overlap または 巻数が我々の値と ±3以内)。
  候補が複数残ったら採らずに `ambiguous` で保留(偽採用より偽保留)。

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

LEDGER = os.path.join(ROOT, ".cache", "manba-titleid.jsonl")
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
                    help="no-tameshiyomi-active.tsv のうち試し読み未検査(recheck-attempted に無い)分")
    ap.add_argument("--sleep", type=float, default=5.0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--vol-tol", type=int, default=3, help="巻数一致の許容差")
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
        want = [r[ci] for r in rows[1:] if r[ci] not in tried]
    else:
        sys.exit("--slugs-file か --from-list が要る")

    done = set()
    if os.path.exists(LEDGER):
        for l in io.open(LEDGER, encoding="utf-8"):
            try:
                done.add(json.loads(l)["slug"])
            except Exception:
                pass
    todo = [s for s in want if s not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f"対象 {len(todo)} 作品(既済 {len(want) - len(todo)} skip) / 間隔 {a.sleep}s / "
          f"2req/作品 ≈ {len(todo) * 2 * a.sleep / 60:.0f}分", flush=True)

    n_hit = n_amb = n_none = n_nostore = 0
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
            exact = [c for c in cands if nk(c["title"]) == nk(title)]
            ok = [c for c in exact
                  if ({akey(x) for x in c["authors"]} & ours_a)
                  or (c["vols"] is not None and abs(c["vols"] - ours_v) <= a.vol_tol)]
            rec = {"slug": slug, "title": title, "ours_vols": ours_v,
                   "cands": len(cands), "exact": len(exact), "at": time.strftime("%Y-%m-%d")}
            if len(ok) != 1:
                rec["result"] = "ambiguous" if len(ok) > 1 else ("no_match" if not exact else "gate_ng")
                rec["detail"] = [{"b": c["board"], "t": c["title"], "a": c["authors"], "v": c["vols"]}
                                 for c in exact[:4]]
                n_amb += 1 if len(ok) > 1 else 0
                n_none += 1 if len(ok) == 0 else 0
                print(f"[{i}/{len(todo)}] {slug}: {rec['result']} (候補{len(cands)}/完全一致{len(exact)}) {title}", flush=True)
            else:
                c = ok[0]
                tid, note = booklive_title_id(c["board"], a.sleep)
                rec.update({"board": c["board"], "manba_title": c["title"],
                            "manba_authors": c["authors"], "manba_vols": c["vols"],
                            "title_id": tid, "result": "hit" if tid else "no_store", "note": note})
                if tid:
                    n_hit += 1
                else:
                    n_nostore += 1
                print(f"[{i}/{len(todo)}] {slug}: {'title_id=' + tid if tid else note} "
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
