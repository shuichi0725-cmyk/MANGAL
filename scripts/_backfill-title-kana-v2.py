"""種2 (= db-v2.sqlite) の title_kana NULL series に
madb-enrich.json から title_kana_correct を backfill。

種3 fill 前の prep work (= 課題 A):
- orphan101 source 等で title_kana が 空 (= 41,108 件) で 種3 AI が context 不足
- madb-enrich.json (= 145,281 entries) に title→title_kana_correct map あり
- title 一致 で 37,034 件 (= 90.1%) 補完可能

副次効果: subtitle_kana / title_official_en も 同 cache に あれば backfill。
"""

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
ENRICH = ROOT / ".cache" / "madb-enrich.json"


def main() -> None:
    print(f"loading {ENRICH} ...", file=sys.stderr)
    with ENRICH.open("r", encoding="utf-8") as f:
        enrich = json.load(f)
    print(f"  entries: {len(enrich):,}", file=sys.stderr)

    con = sqlite3.connect(DB)
    cur = con.cursor()

    cur.execute("SELECT COUNT(*) FROM series WHERE title_kana IS NULL OR title_kana = ''")
    before_null = cur.fetchone()[0]
    print(f"\n種2 で kana NULL series (before): {before_null:,}", file=sys.stderr)

    cur.execute("SELECT id, title FROM series WHERE title_kana IS NULL OR title_kana = ''")
    rows = cur.fetchall()

    stats = {"updated": 0, "subtitle_kana_updated": 0,
             "title_official_en_updated": 0, "miss": 0}
    for sid, title in rows:
        if not title or title not in enrich:
            stats["miss"] += 1
            continue
        e = enrich[title]
        kana = e.get("title_kana_correct")
        if not kana:
            stats["miss"] += 1
            continue
        cur.execute("UPDATE series SET title_kana=? WHERE id=?", (kana, sid))
        stats["updated"] += 1
        # 同 enrich entry に subtitle_kana / title_official_en あれば 補完
        sub_kana = e.get("subtitle_kana")
        if sub_kana:
            cur.execute(
                "UPDATE series SET subtitle_kana=? WHERE id=? AND (subtitle_kana IS NULL OR subtitle_kana='')",
                (sub_kana, sid),
            )
            if cur.rowcount:
                stats["subtitle_kana_updated"] += 1
        en = e.get("title_official_en")
        if en:
            cur.execute(
                "UPDATE series SET title_official_en=? WHERE id=? AND (title_official_en IS NULL OR title_official_en='')",
                (en, sid),
            )
            if cur.rowcount:
                stats["title_official_en_updated"] += 1

    con.commit()

    cur.execute("SELECT COUNT(*) FROM series WHERE title_kana IS NULL OR title_kana = ''")
    after_null = cur.fetchone()[0]

    print(f"\n=== stats ===", file=sys.stderr)
    print(f"  updated title_kana: {stats['updated']:,}", file=sys.stderr)
    print(f"  updated subtitle_kana: {stats['subtitle_kana_updated']:,}", file=sys.stderr)
    print(f"  updated title_official_en: {stats['title_official_en_updated']:,}", file=sys.stderr)
    print(f"  miss (= cache 不一致): {stats['miss']:,}", file=sys.stderr)
    print(f"\n  kana NULL: {before_null:,} → {after_null:,} (= {before_null - after_null:,} 救済)", file=sys.stderr)


if __name__ == "__main__":
    main()
