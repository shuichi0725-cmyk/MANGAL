"""[調査] 本番DB(data/manga.v2)でISBN欠落の巻を年代別に集計。
日本のISBNは概ね1981年〜普及 → それ以前は欠落が自然、最近の欠落は異常(取り込み不備)。"""
import glob, yaml, re
from collections import Counter

YEAR_RE = re.compile(r"(\d{4})")
tot = noisbn = 0
by_decade = Counter()
recent_examples = []  # 2015以降の欠落例
no_date = 0

for f in glob.glob("data/manga.v2/*.yml"):
    try:
        d = yaml.safe_load(open(f, encoding="utf-8")) or {}
    except Exception:
        continue
    wy = d.get("year_started")
    for ed in d.get("editions") or []:
        for v in ed.get("volumes") or []:
            tot += 1
            isbn = v.get("isbn13")
            if isbn:
                continue
            noisbn += 1
            rd = v.get("release_date")
            y = None
            if rd:
                m = YEAR_RE.search(str(rd))
                if m:
                    y = int(m.group(1))
            if y is None and wy:
                try:
                    y = int(wy)
                except Exception:
                    y = None
            if y is None:
                no_date += 1
                by_decade["不明"] += 1
            else:
                dec = (y // 10) * 10
                by_decade[f"{dec}s"] += 1
                if y >= 2015 and len(recent_examples) < 15:
                    recent_examples.append((d.get("slug"), v.get("number"), rd))

print(f"総巻数: {tot:,}")
print(f"ISBN欠落: {noisbn:,} ({noisbn*100//max(1,tot)}%)")
print(f"  うち発売日も年も不明: {no_date:,}")
print("--- ISBN欠落の年代別 ---")
def keyf(k):
    return -1 if k == "不明" else int(k[:4])
for k in sorted(by_decade, key=keyf):
    print(f"  {k}: {by_decade[k]:,}")

# 異常域(最近)の小計
def yr(k):
    return None if k == "不明" else int(k[:4])
recent = sum(n for k, n in by_decade.items() if (yr(k) or 0) >= 2000)
recent2010 = sum(n for k, n in by_decade.items() if (yr(k) or 0) >= 2010)
print(f"--- 異常域 ---")
print(f"  2000年代以降の欠落(おかしい): {recent:,}")
print(f"  2010年代以降の欠落(特におかしい): {recent2010:,}")
print("  2015以降の例:", recent_examples)
