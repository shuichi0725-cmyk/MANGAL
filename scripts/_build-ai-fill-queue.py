"""need_fill 候補から isbn>=2 で filter し、 AI fill candidate yml を生成。

output:
  - data/seeds/_ai-fill-queue.yml: AI fill 対象 entries の list
    各 entry: series_key, title, subtitle, source, n_isbn, sample_isbns
"""

import sqlite3
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
NEW_SEED3 = ROOT / "data" / "seeds" / "series-supplement-v2.yml"
OUT = ROOT / "data" / "seeds" / "_ai-fill-queue.yml"

ISBN_THRESHOLD = 2


def main():
    with NEW_SEED3.open("r", encoding="utf-8") as f:
        new_yml = yaml.safe_load(f)
    migrated_keys = {e["key"] for e in new_yml["series"]}
    print(f"migrated: {len(migrated_keys)}", file=sys.stderr)

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(
        """
        SELECT s.id, s.series_key, s.source, s.qid, s.title, s.subtitle,
               s.title_kana, s.title_official_en,
               (SELECT COUNT(*) FROM volumes v JOIN editions e ON e.id=v.edition_id
                WHERE e.series_id=s.id AND v.isbn13 IS NOT NULL) AS n_isbn
        FROM series s
        WHERE s.adult_score < 3
    """
    )
    all_public = [dict(r) for r in cur.fetchall()]

    need_fill = [s for s in all_public if s["series_key"] not in migrated_keys]
    filtered = [s for s in need_fill if s["n_isbn"] >= ISBN_THRESHOLD]
    print(
        f"total public: {len(all_public)}  need_fill: {len(need_fill)}  "
        f"after isbn>={ISBN_THRESHOLD}: {len(filtered)}",
        file=sys.stderr,
    )

    # sample ISBN 3 件 まで添付
    out_entries = []
    for s in filtered:
        cur.execute(
            """SELECT isbn13, number, release_date FROM volumes v
               JOIN editions e ON e.id = v.edition_id
               WHERE e.series_id = ? AND isbn13 IS NOT NULL
               ORDER BY release_date LIMIT 3""",
            (s["id"],),
        )
        samples = [
            {"isbn": r["isbn13"], "number": r["number"], "date": r["release_date"]}
            for r in cur.fetchall()
        ]
        out_entries.append(
            {
                "key": s["series_key"],
                "title": s["title"],
                "subtitle": s["subtitle"] or "",
                "qid": s["qid"] or "",
                "source": s["source"],
                "n_isbn": s["n_isbn"],
                "title_kana": s["title_kana"] or "",
                "title_official_en": s["title_official_en"] or "",
                "samples": samples,
            }
        )

    # 巻数多い順
    out_entries.sort(key=lambda e: -e["n_isbn"])

    with OUT.open("w", encoding="utf-8") as f:
        yaml.dump(
            {
                "threshold": f"isbn >= {ISBN_THRESHOLD}",
                "total": len(out_entries),
                "entries": out_entries,
            },
            f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )

    print(f"\n=== AI fill queue stats ===", file=sys.stderr)
    print(f"  total entries        : {len(out_entries)}", file=sys.stderr)
    print(f"  batch (= 100/batch) : {(len(out_entries) + 99) // 100}", file=sys.stderr)
    print(f"  概算 cost (= $2.3/batch): ~${((len(out_entries) + 99) // 100) * 2.3:.0f}", file=sys.stderr)

    # source 分布
    from collections import Counter
    src = Counter(e["source"] for e in out_entries)
    print(f"\n  source 分布: {dict(src)}", file=sys.stderr)

    print(f"\nwrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
