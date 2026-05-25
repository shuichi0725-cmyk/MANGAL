"""metadata101.json から 「改題」 含む 行 を 文脈付きで 抽出。

目的: 種1 raw 上で 改題情報が どの field に格納されているか 特定。
JSON-LD ファイルは entity 毎にインデント表記、 1 entity 数十行。
「改題」 を含む 行を 検出し、 直前の field 名 (= "schema:xxx") を 表示。
"""
from __future__ import annotations
from pathlib import Path

SRC = Path(".cache/madb/metadata101.json")
LIMIT = 30  # 最大 30 件 sample

count = 0
field_counter: dict[str, int] = {}

with SRC.open("r", encoding="utf-8") as f:
    for line in f:
        if "改題" in line and count < LIMIT:
            count += 1
            # 行の 「"field": "..."」 から field 名 抽出
            stripped = line.strip()
            if ":" in stripped:
                key = stripped.split(":", 1)[0].strip().strip(",").strip('"')
            else:
                key = "?"
            field_counter[key] = field_counter.get(key, 0) + 1
            print(f"[{count}] field={key}")
            print(f"    {stripped[:200]}")

# 全件 (= sample limit なし) で field 集計
print("\n=== 全行 集計 (= 「改題」 を含む 行 の field 分布) ===")
field_total: dict[str, int] = {}
with SRC.open("r", encoding="utf-8") as f:
    for line in f:
        if "改題" not in line:
            continue
        stripped = line.strip()
        if ":" in stripped:
            key = stripped.split(":", 1)[0].strip().strip(",").strip('"')
        else:
            key = "?"
        field_total[key] = field_total.get(key, 0) + 1

for k, v in sorted(field_total.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")
print(f"  --- total: {sum(field_total.values())} ---")
