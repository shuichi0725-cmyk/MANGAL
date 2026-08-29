# -*- coding: utf-8 -*-
"""コミック頁に**別物の巻**(原作ラノベ/本編/旧作)が混入している型の検出 (2026-08-29 新設)。

きっかけ: 「断罪された悪役令嬢は、逆行して完璧な悪女を目指す」の9巻枠に**原作ラノベ**が入っていた
  (ユーザ報告「9巻だけラノベ汚染」)。追跡すると入口は種4(volumes-supplement)の
  `source: rakuten-trailing` = 柱⑨「続巻逆照合(連載中頁→楽天題検索)」で、**題が同じ小説を拾って**いた。

判定 (= ローカル楽天キャッシュ1パスのみ。live は叩かない):
  対象 = 種4で足した巻のうち、**原作(original_authors)と作画(authors)が別人**の頁に属するもの。
  ★signal = その巻の楽天 author に **原作者は居るが作画者が居ない**。
    コミックなら作画者が必ずクレジットされるので、原作者名義だけの巻は
    「原作小説」か「別作画の別作品」の可能性が高い。
  ★実測(2026-08-29 初回): 候補27件/19頁 → 実害は3頁5巻だった。残りは
    楽天の著者欄が片方しか埋まっていないだけの偽陽性なので、**必ず1件ずつ楽天/NDLで裏取りすること**。

初回で見つかった実害 (すべて是正済):
  - danzai-…-akujo-o-mezasu 9巻 = 原作ラノベ(楢山幕府・1399円)
  - tate-no-yuusha-…-girls-side-story 26/29巻 = **本編**(藍屋球作画)がスピンオフ頁に混入
  - bird-black-maaketto 1/2巻 = 2000年の別作品『バード』(青山広美単独)が混入

是正: data/seeds/volume-exclude.yml に slug+isbn13 で登録し、真の巻は 種4 で補う。
出力: docs/production-diagnostics/novel-in-manga-page.tsv

  python scripts/_audit-novel-in-manga-page.py
"""
import io, json, os, re, sys, unicodedata
import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "novel-in-manga-page.tsv")
# 人名の異体字(楽天とMADBで揺れる)。 これを畳まないと偽陽性が出る(濵﨑真代=濱﨑真代)
VARIANT = str.maketrans("﨑濵髙德凜栁邊嶋", "崎浜高徳凛柳辺島")


def nm(s):
    s = unicodedata.normalize("NFKC", str(s or "")).lower().translate(VARIANT)
    return re.sub(r"[\s　・･,，/／、。\.\-（）()【】\[\]]", "", s)


def main():
    docs = []
    for f in ("volumes-supplement.yml", "volumes-supplement-auto.yml"):
        p = os.path.join(ROOT, "data", "seeds", f)
        if not os.path.exists(p):
            continue
        d = yaml.safe_load(io.open(p, encoding="utf-8")) or {}
        for v in (d.get("volumes") or []):
            v["_seed"] = f
            docs.append(v)
    want = {}
    for v in docs:
        if v.get("isbn13"):
            want.setdefault(str(v["isbn13"]), []).append(v)
    print("種4 全巻 %d / ISBN %d" % (len(docs), len(want)), flush=True)

    idx = json.load(io.open(os.path.join(ROOT, ".cache", "isbn-page-index.json"), encoding="utf-8"))
    items = {}
    with io.open(os.path.join(ROOT, ".cache", "rakuten-isbn-delta.jsonl"),
                 encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                o = json.loads(line)
            except Exception:
                continue
            i = str(o.get("isbn") or "")
            if i in want and i not in items:
                it = o.get("item") or {}
                items[i] = (it.get("title") or "", it.get("author") or "", it.get("itemPrice") or 0,
                            it.get("seriesName") or "", it.get("salesDate") or "", it.get("size") or "")
    print("楽天キャッシュ ヒット %d" % len(items), flush=True)

    pages, rows = {}, []
    for i, vs in want.items():
        it = items.get(i)
        if not it:
            continue
        title, author, price, series, date, size = it
        a = nm(author)
        if not a:
            continue
        for slug in (idx.get(i) or []):
            p = os.path.join(ROOT, "data", "manga.v2", slug + ".yml")
            if slug not in pages:
                pages[slug] = yaml.safe_load(io.open(p, encoding="utf-8")) if os.path.exists(p) else None
            d = pages[slug]
            if not d:
                continue
            arts = [nm(x.get("name")) for x in (d.get("authors") or [])]
            wrs = [nm(x.get("name")) for x in (d.get("original_authors") or [])]
            if not arts or not wrs:
                continue
            if any(x and x in a for x in arts):
                continue                    # 作画者が載っている = 正常
            if not any(w and w in a for w in wrs):
                continue                    # 原作者も居ない = 別型(ここでは扱わない)
            rows.append((slug, vs[0].get("number"), i, date, price, series, size,
                         author, title[:44], vs[0].get("source"), vs[0]["_seed"]))
    rows.sort(key=lambda r: (r[0], r[1] or 0))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("slug\t巻\tisbn13\t発売日\t価格\tseriesName\tsize\t楽天author\t楽天title\t種4source\tseed\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")
    print("★原作者名義のみ(別物の疑い): %d 件 / %d 頁 → %s"
          % (len(rows), len({r[0] for r in rows}), os.path.relpath(OUT, ROOT)))
    print("  ★偽陽性が多い(楽天の著者欄が片方しか無いだけ)。1件ずつ裏取りしてから volume-exclude へ。")
    for r in rows:
        print("  %-46s v%-4s %s %s %s円 %s | %s | %s"
              % (r[0], r[1], r[2], r[3], r[4], r[6], r[7], r[8]))


if __name__ == "__main__":
    main()
