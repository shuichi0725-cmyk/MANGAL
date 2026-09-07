#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""マンバ蒸留の台帳 → 試し読みアンカー seed へ反映 (2026-09-07 新設)

  data/seeds/manba-titleid.jsonl (result:"hit" のみ)
    → data/seeds/tameshiyomi-booklive.jsonl へ純粋追加
    → 続けて scripts/_gen-tameshiyomi-map.py で data/tameshiyomi-map.json を再生成

★入れないもの: hit_edition_suspect(版違い=別商品) / ambiguous / no_match / gate_ng / no_store。
★既に anchor seed に在る slug は skip(重複させない)。
★著者overlapが無く「巻数±3」だけで通った hit は --report で別掲(目視してから入れる作法)。

usage:
  python scripts/_apply-manba-titleid.py --report            # 読むだけ
  python scripts/_apply-manba-titleid.py --apply [--skip <slug,...>]
"""
import argparse, io, json, os, re, sys, unicodedata

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "data", "seeds", "manba-titleid.jsonl")
ANCHOR = os.path.join(ROOT, "data", "seeds", "tameshiyomi-booklive.jsonl")
INDEX = os.path.join(ROOT, "data", "manga-list-index.json")


def akey(s):
    return re.sub(r"[\s\u3000・,]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--skip", default="", help="除外slug(カンマ区切り)= 目視で弾いたもの")
    a = ap.parse_args()
    skip = {s for s in a.skip.split(",") if s}

    last = {}
    for ln in io.open(LEDGER, encoding="utf-8"):
        ln = ln.strip()
        if ln:
            d = json.loads(ln)
            last[d["slug"]] = d
    hits = {s: d for s, d in last.items() if d.get("result") == "hit" and d.get("title_id")}

    have = set()
    for ln in io.open(ANCHOR, encoding="utf-8"):
        ln = ln.strip()
        if ln:
            have.add(json.loads(ln)["slug"])

    idx = json.load(io.open(INDEX, encoding="utf-8"))
    F = {n: i for i, n in enumerate(idx["f"])}
    by_slug = {r[F["slug"]]: r for r in idx["d"]}

    new, dup, gone, volonly = [], [], [], []
    for slug, d in sorted(hits.items()):
        if slug in have:
            dup.append(slug); continue
        row = by_slug.get(slug)
        if not row:
            gone.append(slug); continue
        ours = {akey(str(x).split("\t")[0]) for x in (row[F["authors"]] or [])}
        ours |= {akey(str(x).split("\t")[0]) for x in (row[F["original_authors"]] or [])}
        overlap = bool({akey(x) for x in (d.get("manba_authors") or [])} & ours)
        rec = {"slug": slug, "title": d["title"], "title_id": str(d["title_id"]),
               "cid1": f"{d['title_id']}_001", "verified": "manba302",
               "evidence": f"manba board={d.get('board')} 「{d.get('manba_title')}」"
                           f" 著者={'/'.join(d.get('manba_authors') or []) or '-'}"
                           f" 巻{d.get('manba_vols')}/我々{d.get('ours_vols')}"
                           f" tier={d.get('tier', 'T1')}",
               "at": d.get("at")}
        if not overlap:
            volonly.append((slug, d, rec))
        new.append((slug, overlap, rec))

    print(f"台帳 hit {len(hits)} 件 → 追加可 {len(new)} / 既済skip {len(dup)} / 索引消失 {len(gone)}")
    print(f"  うち著者overlap有 {sum(1 for _, o, _ in new if o)} / "
          f"★巻数のみで通った(目視対象) {len(volonly)}")
    if a.report:
        if volonly:
            print("\n--- 巻数一致のみ(著者overlap無し)= 目視対象 ---")
            for slug, d, _ in volonly:
                row = by_slug[slug]
                ours_a = [str(x).split("\t")[0] for x in (row[F["authors"]] or [])]
                ours_a += [str(x).split("\t")[0] for x in (row[F["original_authors"]] or [])]
                print(f"  {slug}\n    我々: 「{d['title']}」 著者={'/'.join(ours_a) or '-'} 巻{d.get('ours_vols')}"
                      f"\n    manba: 「{d.get('manba_title')}」 著者={'/'.join(d.get('manba_authors') or []) or '-'}"
                      f" 巻{d.get('manba_vols')} board={d.get('board')} tid={d.get('title_id')}")
        if gone:
            print("\n索引に無いslug(頁改名/drop?):", ", ".join(gone))
        return

    if not a.apply:
        print("\n(--report か --apply を指定)"); return

    add = [rec for slug, _, rec in new if slug not in skip]
    with io.open(ANCHOR, "a", encoding="utf-8", newline="\n") as f:
        for rec in add:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"\n★追加 {len(add)} 件 → {ANCHOR}"
          + (f" (目視で除外 {len(new) - len(add)} 件: {', '.join(sorted(skip))})" if skip else ""))
    print("次: python scripts/_gen-tameshiyomi-map.py")


if __name__ == "__main__":
    main()
