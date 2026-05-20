#!/usr/bin/env python3
"""B-2 追加修正: 既存 en 値の書換 + 削除。

修正対象 (= 4件):
- ハイキュー!!: en 'Haikyuu!!' → 'Haikyu!!' (= 公式英題に揃える)
- SPY×FAMILY: en 'SPY×FAMILY' → 'Spy x Family' (= × を 'x' ASCII 化)
- ハンター×ハンター: en 'Hunter × Hunter' → 'Hunter x Hunter'
- らんま1/2: en 'Ranma 1/2' を 削除 (= 純和語ルート復帰、 期待 slug 'ranma-nibun-no-ichi')
"""

import re
import sys
from pathlib import Path

YML = Path("data/seeds/series-supplement-v2.yml")

EN_REWRITE = {
    "qid:Q11411575|name:ハイキュー!!": "Haikyu!!",
    "qid:Q3981526|name:SPY×FAMILY": "Spy x Family",
    "qid:Q550311|name:ハンター×ハンター": "Hunter x Hunter",
}
EN_DELETE = {
    "qid:Q219948|name:らんま1/2",
}


def main():
    with YML.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    out = []
    stats = {"rewrote": 0, "deleted": 0, "missed": 0}
    matched_keys = set()
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        m = re.match(r"^  - key: (.+)$", line)
        if not m:
            out.append(line)
            i += 1
            continue

        key = m.group(1).rstrip()
        j = i + 1
        while j < n and not re.match(r"^  - key: ", lines[j]):
            j += 1
        block = list(lines[i:j])

        if key in EN_REWRITE:
            new_en = EN_REWRITE[key]
            matched = False
            for k, bl in enumerate(block):
                if re.match(r"^      en:\s", bl):
                    block[k] = f"      en: {new_en}\n"
                    matched = True
                    stats["rewrote"] += 1
                    matched_keys.add(key)
                    break
            if not matched:
                stats["missed"] += 1
        elif key in EN_DELETE:
            # en 行 + (空 alternative_titles ブロックなら丸ごと) 削除
            new_block = []
            en_idx = None
            alt_idx = None
            for k, bl in enumerate(block):
                if re.match(r"^      en:\s", bl):
                    en_idx = k
                if re.match(r"^    alternative_titles:\s*$", bl):
                    alt_idx = k
            if en_idx is not None:
                block.pop(en_idx)
                stats["deleted"] += 1
                matched_keys.add(key)
                # alternative_titles が空になったら親も削除
                if alt_idx is not None:
                    # alt_idx の次の行が またインデント深いキーかチェック
                    # 既に en を削除した後の block を見る
                    if alt_idx + 1 >= len(block) or not re.match(r"^      \w", block[alt_idx + 1]):
                        block.pop(alt_idx)
            else:
                stats["missed"] += 1

        out.extend(block)
        i = j

    expected = set(EN_REWRITE.keys()) | EN_DELETE
    missing = expected - matched_keys
    if missing:
        print(f"⚠️ matched 失敗: {missing}", file=sys.stderr)

    print(f"=== 統計 ===", file=sys.stderr)
    for k, v in stats.items():
        print(f"  {k}: {v}", file=sys.stderr)
    print(f"\n  output {len(out)} lines (diff: {len(lines) - len(out):+d})", file=sys.stderr)

    with YML.open("w", encoding="utf-8") as f:
        f.writelines(out)
    print(f"\n✅ written to {YML}", file=sys.stderr)


if __name__ == "__main__":
    main()
