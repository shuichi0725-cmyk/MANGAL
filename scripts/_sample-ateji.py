"""ateji_kata の random 100 サンプルを md table に。"""
import random
import re
from pathlib import Path

SRC = Path(".cache/audit-kanji-loanword-ateji.txt")
OUT = Path(".cache/ateji-sample-100.md")

text = SRC.read_text(encoding="utf-8")
sec = text.split("## ateji_kata (= 漢字 → カタカナ外来語当て字、 本命) 全件", 1)[1]
sec = sec.split("## ateji_mixed", 1)[0]

entries = []
cur = {}
for line in sec.splitlines():
    m = re.match(r"^  \[(M\d+)\] (.+)$", line)
    if m:
        if cur:
            entries.append(cur)
        cur = {"id": m.group(1), "title": m.group(2)}
        continue
    m = re.match(r"^    predicted: (.+)$", line)
    if m and cur:
        cur["predicted"] = m.group(1)
        continue
    m = re.match(r"^    actual:    (.+)$", line)
    if m and cur:
        cur["actual"] = m.group(1)
        continue
if cur:
    entries.append(cur)

print(f"total ateji_kata entries: {len(entries)}")

random.seed(42)
sample = random.sample(entries, min(100, len(entries)))

out_lines = []
out_lines.append("# ateji_kata ランダム 100 サンプル (= 目視判定用)")
out_lines.append("")
out_lines.append(f"母集団: {len(entries):,} 件 / 抽出: {len(sample)} 件 (= seed=42)")
out_lines.append("")
out_lines.append("判定凡例:")
out_lines.append("- ★ = 真の 外来語当て字 (= mini 辞書候補)")
out_lines.append("- ☓ = false positive (= 助詞 / 連濁 / 訓読み揺れ)")
out_lines.append("- ? = 判別困難")
out_lines.append("")
out_lines.append("| # | MADB ID | title | 標準読み | 実フリガナ | 判定 |")
out_lines.append("|---|---|---|---|---|---|")
for i, e in enumerate(sample, 1):
    t = e.get("title", "")[:35]
    p = e.get("predicted", "")[:35]
    a = e.get("actual", "")[:35]
    out_lines.append(f"| {i} | {e['id']} | {t} | {p} | {a} |   |")

OUT.write_text("\n".join(out_lines), encoding="utf-8")
print(f"wrote: {OUT}")
