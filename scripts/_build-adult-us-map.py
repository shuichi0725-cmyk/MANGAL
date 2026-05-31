"""adult_us マップ生成 = 種a(v14マッチ)isAdult な series_key 集合。

米基準フラグ。 match-v14-all.tsv(series_key→a_id)+ dump(a_id→isAdult)。
出力: .cache/adult-us-map.json = {series_key: true}(isAdultのみ)。
promote が load し、 各本番ページに adult_us フラグを付与(非日本geoで非表示用)。
※種2/adult_score 不変。 純粋に派生マップ。
"""
import csv, gzip, json, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
MATCH = Path(".cache/match-v14-all.tsv")
DUMP = Path(".cache/anilist-manga-dump.jsonl.gz")
OUT = Path(".cache/adult-us-map.json")
S = {"S180", "S150", "S130", "S100"}


def main():
    # series_key → a_id (S-tier)
    sk_aid = {}
    with MATCH.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["verdict"] in S and r["a_id"]:
                sk_aid[r["s3_key"]] = int(r["a_id"])
    # a_id → isAdult
    need = set(sk_aid.values())
    isad = {}
    with gzip.open(DUMP, "rt", encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            if e.get("id") in need:
                isad[e["id"]] = bool(e.get("isAdult"))
    # adult_us 集合
    us = {sk for sk, aid in sk_aid.items() if isad.get(aid, False)}
    OUT.write_text(json.dumps(sorted(us), ensure_ascii=False), encoding="utf-8")
    print(f"v14 S-tier マッチ: {len(sk_aid):,}")
    print(f"★adult_us(種a isAdult)= {len(us):,} series_key")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
