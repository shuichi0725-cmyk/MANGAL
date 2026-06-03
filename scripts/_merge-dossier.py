"""指定slug(衝突群)の merge判定用 証拠 dossier を出力 (read-only)。
種2の物的証拠(出版社imprint/年/巻数/ISBN/著者qid)+ AniList(aid/relations/巻数/status)。
[[merge-needs-external-proof]]: 別雑誌・別年・別出版社・relations=PARENT/SPIN_OFF → 分離の証拠。

使い方: python scripts/_merge-dossier.py <slug> [<slug2> ...]
        python scripts/_merge-dossier.py --top N   (worklist WIKI_NEEDED 上位N群)
"""
import json
import sys
import gzip
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def title_of(key):
    names = [s[5:] for s in key.split("|") if s.startswith("name:")]
    return names[-1] if names else key


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    wl = json.load((ROOT / ".cache/merge-worklist.json").open(encoding="utf-8"))
    col = {c["slug"]: c for c in json.load((ROOT / ".cache/final-slug-collisions.json").open(encoding="utf-8"))}
    if args and args[0] == "--top":
        n = int(args[1])
        slugs = [r["slug"] for r in wl["WIKI_NEEDED"][:n]]
    else:
        slugs = args

    en = json.load((ROOT / ".cache/anilist-enrich-map.json").open(encoding="utf-8"))
    con = sqlite3.connect(ROOT / ".cache/db-v2.sqlite")
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    key2sid = {k: s for s, k in con.execute("SELECT id, series_key FROM series")}

    # 必要aidのrelationsを引く
    want_aids = set()
    for s in slugs:
        for k in col.get(s, {}).get("pages", []):
            a = (en.get(k) or {}).get("anilist_id")
            if a:
                want_aids.add(a)
    relmap = {}
    if want_aids:
        for line in gzip.open(ROOT / ".cache/anilist-manga-dump-v3.jsonl.gz", "rt", encoding="utf-8"):
            d = json.loads(line)
            if d.get("id") in want_aids:
                rels = [(e.get("relationType"), (e.get("node", {}).get("title") or {}).get("native"),
                         e.get("node", {}).get("type"))
                        for e in (d.get("relations") or {}).get("edges", [])]
                relmap[d["id"]] = {"vols": d.get("volumes"), "status": d.get("status"),
                                   "rels": [r for r in rels if r[2] == "MANGA"]}

    for s in slugs:
        pages = col.get(s, {}).get("pages", [])
        print(f"\n{'='*70}\n■ [{s}] ×{len(pages)}")
        for k in pages:
            sid = key2sid.get(k)
            aid = (en.get(k) or {}).get("anilist_id")
            imprint = vols = yrs = isbn = au = ""
            if sid:
                rows = con.execute(
                    "SELECT ed.imprint, v.number, v.release_date, v.isbn13 "
                    "FROM editions ed JOIN volumes v ON v.edition_id=ed.id "
                    "WHERE ed.series_id=? AND v.isbn13!=''", (sid,)).fetchall()
                imps = sorted({r[0] for r in rows if r[0]})
                nums = sorted({r[1] for r in rows if r[1] and r[1] < 400})
                years = sorted({(r[2] or "")[:4] for r in rows if r[2]})
                isbns = [r[3] for r in rows]
                aql = [q for (q,) in con.execute(
                    "SELECT m.name FROM series_authors sa JOIN mangaka m ON m.id=sa.mangaka_id WHERE sa.series_id=?", (sid,))]
                imprint = "/".join(imps)[:30]
                vols = f"{min(nums)}-{max(nums)}" if nums else "?"
                yrs = f"{years[0]}-{years[-1]}" if years else "?"
                isbn = isbns[0] if isbns else ""
                au = ",".join(aql[:2])
            print(f"  「{title_of(k)[:30]}」")
            print(f"      著者={au} 出版={imprint} 巻={vols} 年={yrs} ISBN={isbn} aid={aid}")
            if aid in relmap:
                r = relmap[aid]
                rel_s = "; ".join(f"{rt}:{rn[:14]}" for rt, rn, _ in r["rels"][:4])
                print(f"      aid{aid}: vols={r['vols']} {r['status']} rel[{rel_s}]")


if __name__ == "__main__":
    main()
