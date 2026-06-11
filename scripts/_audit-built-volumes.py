"""ビルド出力(data/manga.v2)の巻整合監査。
Tier1 = 編集内 重複番号 (= ミスマッチ signal、 最優先)
Tier2 = 内部 巻抜け (= 1..max の途中欠番。 trailing lag とは区別)
出力: .cache/audit-built.txt にソート済 offender list。
"""
import sys, os, glob, yaml
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
OUT = "data/manga.v2"

dup_hits = []      # (slug, edtype, dup_numbers, n)
gap_hits = []      # (slug, edtype, gaps, max, n)
multi_ed = 0
total_eds = 0
total_pages = 0

files = glob.glob(os.path.join(OUT, "*.yml"))
for fp in files:
    total_pages += 1
    try:
        d = yaml.safe_load(open(fp, encoding="utf-8"))
    except Exception:
        continue
    if not d:
        continue
    slug = os.path.splitext(os.path.basename(fp))[0]
    eds = d.get("editions", [])
    if len(eds) > 1:
        multi_ed += 1
    for ed in eds:
        total_eds += 1
        nums = [v.get("number") for v in ed.get("volumes", []) if v.get("number") is not None]
        if not nums:
            continue
        c = Counter(nums)
        dups = sorted(n for n, k in c.items() if k > 1)
        if dups:
            dup_hits.append((slug, ed.get("type", "?"), dups, len(nums)))
        mx = max(nums)
        present = set(nums)
        gaps = [i for i in range(1, mx + 1) if i not in present]
        # 内部gap のみ (= max まで埋まってない穴)。 単巻や0は除外。
        if gaps and mx >= 2:
            gap_hits.append((slug, ed.get("type", "?"), gaps, mx, len(nums)))

# Tier2 を 重大度で再分類:
#   outlier = 巻数 n に対し max が異常に大きい (= 誤parse番号 or 断片混入)。 coverage=n/max が低い。
#   single_outlier = max値を1つ除くと連続 (= 番号1個だけ飛び値。 最も是正容易)。
#   minor_gap = ほぼ揃って数巻欠け (coverage>=0.85)。 本当の巻抜け/最新lag。
#   mid_gap = その中間。
outlier, single_out, minor_gap, mid_gap = [], [], [], []
for slug, et, gaps, mx, n in gap_hits:
    cov = n / mx if mx else 1.0
    # single outlier 判定: gap を埋めるのに必要な「欠け」が (mx - n) と一致し、
    # 実在番号のうち最大だけが飛び抜けている(= 2位番号 +1 以降が全部欠け)
    is_single = (len(gaps) == mx - n) and (mx - 1 in gaps)  # max直前が欠け = maxが孤立
    if cov < 0.5:
        (single_out if is_single else outlier).append((slug, et, gaps, mx, n, cov))
    elif cov >= 0.85:
        minor_gap.append((slug, et, gaps, mx, n, cov))
    else:
        mid_gap.append((slug, et, gaps, mx, n, cov))
for L in (outlier, single_out, minor_gap, mid_gap):
    L.sort(key=lambda x: (x[5], -x[3]))
dup_hits.sort(key=lambda x: (-len(x[2]), -x[3]))

def fmt_band(name, L, limit):
    out = [f"■ {name}: {len(L)} edition"]
    for slug, et, gaps, mx, n, cov in L[:limit]:
        gs = ",".join(map(str, gaps[:14])) + ("..." if len(gaps) > 14 else "")
        out.append(f"   {slug} [{et}] n={n} max={mx} cov={cov:.2f} 欠={gs}")
    return out

lines = []
lines.append("=== ビルド出力 巻整合監査 ===")
lines.append(f"総ページ: {total_pages}  総edition: {total_eds}  multi-edition: {multi_ed}")
lines.append("")
lines.append(f"■ Tier1 編集内重複番号 (ミスマッチ): {len(dup_hits)} edition")
for slug, et, dups, n in dup_hits[:80]:
    ds = ",".join(map(str, dups[:12])) + ("..." if len(dups) > 12 else "")
    lines.append(f"   {slug} [{et}] n={n} 重複番号={ds}")
lines.append("")
lines += fmt_band("Tier2a 番号異常 outlier (cov<0.5, max孤立でない=断片混入/誤parse)", outlier, 200)
lines.append("")
lines += fmt_band("Tier2b 単一飛び値 single-outlier (cov<0.5, max1個だけ孤立=是正容易)", single_out, 120)
lines.append("")
lines += fmt_band("Tier2c 中間gap (0.5<=cov<0.85)", mid_gap, 200)
lines.append("")
lines += fmt_band("Tier2d 軽微gap (cov>=0.85, 数巻欠け=本当の巻抜け/最新lag)", minor_gap, 300)

txt = "\n".join(lines)
open(".cache/audit-built.txt", "w", encoding="utf-8").write(txt)
print(f"総ページ {total_pages} / Tier1重複 {len(dup_hits)}")
print(f"Tier2a 番号異常 {len(outlier)} / 2b 単一飛び値 {len(single_out)} / 2c 中間gap {len(mid_gap)} / 2d 軽微gap {len(minor_gap)}")
print("\n--- 2a 番号異常 上位12 ---")
for r in outlier[:12]: print(f"   {r[0]} [{r[1]}] n={r[4]} max={r[3]} cov={r[5]:.2f} 欠={r[2][:8]}")
print("--- 2d 軽微gap 上位12 (本当の巻抜け候補) ---")
for r in minor_gap[:12]: print(f"   {r[0]} [{r[1]}] n={r[4]} max={r[3]} cov={r[5]:.2f} 欠={r[2][:8]}")
print("\n全文: .cache/audit-built.txt")
