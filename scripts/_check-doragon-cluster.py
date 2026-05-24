"""series-v2.json で ドラゴンボール cluster の madb_records 詳細表示。"""
import json
from pathlib import Path

with Path(".cache/series-v2.json").open(encoding="utf-8") as f:
    data = json.load(f)

for c in data["clusters"]:
    if c["title"] == "ドラゴンボール" and not c["subtitle"]:
        print(f"series_key: {c['series_key']}")
        print(f"title_kana: '{c['title_kana']}'")
        print(f"creator_name: {c['creator_name']}")
        print(f"qid: {c['qid']}")
        print(f"n_madb_records: {c['n_madb_records']}, n_books: {len(c['books'])}")
        print("=== madb_records ===")
        records_by_date = sorted(c["madb_records"], key=lambda r: r["date_published"] or "9999")
        for r in records_by_date:
            print(f"  [{r['madb_id']}] {r['rdfs_label']}")
            print(f"    date='{r['date_published']}', kana='{r['title_kana']}', brand='{r['brand']}'")
        print()
