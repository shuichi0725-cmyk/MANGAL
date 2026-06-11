"""Stage F 個別確証: 候補ペアの ISBN 出版社帯(978-4-XXXX)+巻番号+年を db-v2 から突合。
判定材料を出すのみ(裁定は人/会話で)。 [[collision_slug_investigation]] の uncertain30 方式。
"""
import csv
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**7)
ROOT = Path(__file__).resolve().parent.parent

mg = json.loads((ROOT / "data/seeds/series-merge-auto.json").read_text(encoding="utf-8"))["merges"]
key2group = {}
for g in mg:
    for k in g["merge_keys"]:
        key2group[k] = g["merge_keys"]

con = sqlite3.connect(ROOT / ".cache/db-v2.sqlite")
con.text_factory = lambda b: b.decode("utf-8", "replace")


def page_isbn_info(rep):
    """ページ(merge群束ね)の ISBN prefix 構成と巻番号レンジ。"""
    keys = key2group.get(rep, [rep])
    ph = "?" + ",?" * (len(keys) - 1)
    rows = con.execute(
        f"""SELECT v.isbn13, v.number, v.release_date FROM series s
            JOIN editions e ON e.series_id=s.id JOIN volumes v ON v.edition_id=e.id
            WHERE s.series_key IN ({ph})""", keys).fetchall()
    pref = defaultdict(int)
    nums = []
    years = set()
    for isbn, num, rd in rows:
        i = str(isbn or "").replace("-", "")
        if len(i) == 13:
            pref[i[:8]] += 1
        if num is not None:
            nums.append(num)
        if rd:
            years.add(str(rd)[:4])
    return dict(pref), (min(nums) if nums else None, max(nums) if nums else None, len(nums)), sorted(years)


def show(label, rep_a, rep_b):
    pa, na, ya = page_isbn_info(rep_a)
    pb, nb, yb = page_isbn_info(rep_b)
    shared = set(pa) & set(pb)
    print(f"\n=== {label} ===")
    print(f"  A {rep_a[:58]}")
    print(f"    prefix={pa} vols(min,max,n)={na} years={ya[:6]}")
    print(f"  B {rep_b[:58]}")
    print(f"    prefix={pb} vols={nb} years={yb[:6]}")
    print(f"  ★prefix共有: {sorted(shared) if shared else 'なし'}")


def main():
    pairs = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    for p in pairs:
        show(p["label"], p["a"], p["b"])


if __name__ == "__main__":
    main()
