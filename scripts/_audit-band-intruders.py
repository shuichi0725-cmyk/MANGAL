#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""帯断絶×日付逆行の混入検出 (= 激マン型: 別版/コンビニ再録が本編巻枠に居座る。2026-07-04 ユーザ発見)

シグネチャ: 同一edition内で
  ①ISBN帯(先頭7桁)が少数派(minority) ②その巻の発売日が「より大きい巻番号のmajority帯巻」より後
= 廉価再録・別編・別版の混入疑い。titleキャッシュがあれば実題も添える。
出力: docs/production-diagnostics/band-intruders.tsv
"""
import glob, json, os, re, sys
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try:
    from yaml import CSafeLoader as L
except ImportError:
    from yaml import SafeLoader as L
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

tm_p = os.path.join(ROOT, ".cache", "isbn-title-map.json")
tm = json.load(open(tm_p, encoding="utf-8")) if os.path.exists(tm_p) else {}

def months(s):
    m = re.match(r"^(\d{4})-(\d{2})", str(s or ""))
    return int(m.group(1)) * 12 + int(m.group(2)) if m else None

KEEP = {"standard", "bunkobon", "wideban", "kanzenban", "shinsoban", "aizoban"}
rows = []
n = 0
for p in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
    n += 1
    try:
        d = yaml.load(open(p, encoding="utf-8"), Loader=L)
    except Exception:
        continue
    if not d:
        continue
    slug = os.path.basename(p)[:-4]
    for e in d.get("editions") or []:
        if e.get("type") not in KEEP:
            continue
        vols = [v for v in (e.get("volumes") or []) if v.get("isbn13") and v.get("number")]
        if len(vols) < 3:
            continue
        bands = Counter(str(v["isbn13"])[:7] for v in vols)
        if len(bands) < 2:
            continue
        maj, majn = bands.most_common(1)[0]
        if majn < len(vols) * 0.5:
            continue  # 過半数帯が無い=別問題(多版混在)
        # majority帯の (number → months)
        mj = {v["number"]: months(v.get("release_date")) for v in vols if str(v["isbn13"])[:7] == maj}
        for v in vols:
            b = str(v["isbn13"])[:7]
            if b == maj:
                continue
            mm = months(v.get("release_date"))
            if mm is None:
                continue
            later_major = [k for k, m2 in mj.items() if k > v["number"] and m2 is not None and mm > m2]
            if later_major:
                ib = str(v["isbn13"])
                rows.append((slug, e.get("type"), str(v["number"]), ib,
                             str(v.get("release_date"))[:7], str(tm.get(ib, ""))[:34],
                             f"majority帯{maj}に対し後発({len(later_major)}巻より後)"))
c = Counter(r[0] for r in rows)
out = os.path.join(ROOT, "docs", "production-diagnostics", "band-intruders.tsv")
with open(out, "w", encoding="utf-8") as f:
    f.write("slug\tedition\tvol\tisbn\tdate\tcache_title\tnote\n")
    for r in sorted(rows):
        f.write("\t".join(r) + "\n")
print(f"走査{n}頁 → 混入疑い巻 {len(rows)} / 頁数 {len(c)}")
print("→", out)
for s, k in c.most_common(12):
    print(f"  {k:3} {s}")
