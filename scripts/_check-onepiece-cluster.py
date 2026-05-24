"""series-v2.json で ONE PIECE 本編 cluster の title_kana を確認。"""
import json
from pathlib import Path

with Path(".cache/series-v2.json").open(encoding="utf-8") as f:
    data = json.load(f)

for c in data["clusters"]:
    if c["title"] == "ONE PIECE" and not c["subtitle"]:
        print(f"series_key: {c['series_key']}")
        print(f"title: {c['title']}")
        print(f"title_kana: '{c['title_kana']}'")
        print(f"title_official_en: '{c['title_official_en']}'")
        print(f"n_madb_records: {c['n_madb_records']}")
        print(f"n_books: {len(c['books'])}")
        print(f"is_adult: {c['is_adult']}")
        print(f"creator_name: {c['creator_name']}")
        print(f"qid: {c['qid']}")
        print(f"source: {c['source']}")
        print("=== madb_records ===")
        for r in c["madb_records"]:
            print(f"  [{r['madb_id']}] {r['rdfs_label']}")
            print(f"    date: {r['date_published']}, kana: '{r['title_kana']}'")
        print()
