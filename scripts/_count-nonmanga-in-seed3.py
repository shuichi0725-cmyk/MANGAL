"""種3 yml 内の 非漫画 patterns 件数 を カウント (= 案 B の事前調査)。

CLAUDE.md の MANGAL 掲載対象 protocol に従い、 以下を非漫画として count:
- series-level: テレビアニメ版 / TVアニメ版 / アニメコミック / 劇場版 / 映画 / OVA / ノベライズ / ノベル / 小説
- title contains: ガイドブック / ファンブック / 設定資料集 / 等
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED3 = ROOT / "data" / "seeds" / "series-supplement-v2.yml"

DROP_TITLE_PATTERNS = [
    "テレビアニメ版", "TVアニメ版", "TVアニメ", "アニメコミック",
    "劇場版", "映画", "OVA",
    "ノベライズ", "ノベル", "小説",
]

DROP_TITLE_CONTAINS = [
    "ガイドブック", "ファンブック", "設定資料集",
    "公式図録", "公式読本", "公式ファン", "公式コミックガイド",
    "アンソロジー",
    "キャラクター名鑑", "人物名鑑",
    "心理分析", "心理解析", "完全解析", "完全攻略", "攻略本",
    "解析書", "解体新書", "解体全書",
    "大研究", "最終研究", "超研究", "大事典", "大百科", "大解剖",
    "パーフェクトガイド", "完全読本", "完全ガイド", "必勝法",
    "の秘密", "の謎", "コミック大全", "コミックスペシャル",
    "ナビゲーション", "考察",
]

# 例外 (= 主作品 compilation で keep)
KEEP_OVERRIDE = ["大全集"]


text = SEED3.read_text(encoding="utf-8")
lines = text.splitlines()

total = 0
prefix_hit = 0
contains_hit = 0
both_hit = 0
hit_by_pattern = {}

# parse key lines
for line in lines:
    m = re.match(r'^  - key:\s*(.+)$', line)
    if not m:
        continue
    key = m.group(1).strip()
    # name の最後を取る (= sub: の前 / | 区切りで最後の name)
    # 例: qid:Q123|name:title or qid:Q123|name:title|sub:subtitle
    name_parts = re.findall(r'name:([^|]+?)(?:\|sub:|\||$)', key)
    if not name_parts:
        continue
    title = name_parts[-1]  # last name part = title
    sub = ""
    sub_m = re.search(r'\|sub:(.+)$', key)
    if sub_m:
        sub = sub_m.group(1)

    total += 1
    full_text = title + " " + sub

    # 例外 check: 大全集 含む = skip (= keep)
    if any(kw in full_text for kw in KEEP_OVERRIDE):
        continue

    has_prefix = False
    has_contains = False
    for p in DROP_TITLE_PATTERNS:
        if title.startswith(p) or sub.startswith(p):
            has_prefix = True
            hit_by_pattern[p] = hit_by_pattern.get(p, 0) + 1
            break

    for p in DROP_TITLE_CONTAINS:
        if p in full_text:
            has_contains = True
            hit_by_pattern[p] = hit_by_pattern.get(p, 0) + 1
            break

    if has_prefix:
        prefix_hit += 1
    if has_contains:
        contains_hit += 1
    if has_prefix and has_contains:
        both_hit += 1

union = prefix_hit + contains_hit - both_hit

print(f"total entries: {total}")
print(f"prefix patterns hit: {prefix_hit}")
print(f"contains patterns hit: {contains_hit}")
print(f"both hit (重複): {both_hit}")
print(f"UNION (= 非漫画 candidate 合計): {union}")
print(f"\n=== top 20 patterns by hit ===")
for p, c in sorted(hit_by_pattern.items(), key=lambda x: -x[1])[:20]:
    print(f"  {c:6}  {p}")
