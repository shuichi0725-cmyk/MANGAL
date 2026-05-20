"""C-2c 候補件数 を 推定 (= draft 10000+ の 外来語 + en未fill)。"""
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
SEED3 = ROOT / "data" / "seeds" / "series-supplement-v2.yml"

KEEP_EDITION_TYPES = {"standard", "bunkobon", "wideban", "kanzenban", "shinsoban", "aizoban"}
KATA = re.compile(r"[゠-ヿㇰ-ㇿ]")

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


def title_passes_filter(title):
    if not title:
        return False
    for p in DROP_TITLE_PATTERNS:
        if title.startswith(p):
            return False
    for p in DROP_TITLE_CONTAINS:
        if p in title:
            return False
    return True


def extract_title_suffix(title):
    m = re.search(r"(第[一二三四五六七八九十百\d]+部|[IVX]+$)", title)
    return m.group(1) if m else None


cutoff_date = "2020-12-31"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

filter_clause = f"""
    e.type IN ({','.join('?' * len(KEEP_EDITION_TYPES))})
    AND LOWER(COALESCE(e.imprint, '')) NOT LIKE '%english%'
    AND (LOWER(COALESCE(e.imprint, '')) NOT LIKE '%complete works%' OR e.imprint LIKE '%=%')
    AND v.number > 0
    AND v.release_date IS NOT NULL
"""

# Full rank: take ALL series passing filter, no limit
rows = con.execute(
    f"""
    WITH per_vol AS (
        SELECT e.series_id, v.number, MIN(v.release_date) AS first_release
        FROM editions e JOIN volumes v ON v.edition_id=e.id
        WHERE {filter_clause}
        GROUP BY e.series_id, v.number
    )
    SELECT s.id, s.title, s.subtitle, s.title_kana, s.qid,
           s.series_key,
           MAX(pv.first_release) AS filtered_last,
           COUNT(pv.number) AS vol_count
    FROM series s
    JOIN per_vol pv ON pv.series_id = s.id
    WHERE s.adult_score < 3
    GROUP BY s.id
    HAVING vol_count >= 5
       AND filtered_last <= ?
    ORDER BY (CASE WHEN s.qid IS NOT NULL THEN 100 ELSE 0 END) + vol_count DESC
    """,
    list(KEEP_EDITION_TYPES) + [cutoff_date],
).fetchall()

seen = set()
allcand = []
for r in rows:
    if not title_passes_filter(r["title"]):
        continue
    if not r["title_kana"]:
        continue
    kana_norm = re.sub(r"[\s　]", "", r["title_kana"] or "")
    part = extract_title_suffix(r["title"] or "") or "main"
    key = (kana_norm, part)
    if key in seen:
        continue
    seen.add(key)
    allcand.append(dict(r))

print(f"全 dedup 候補: {len(allcand)}")
print(f"  rank 1-2000 (= C-1): {len(allcand[:2000])}")
print(f"  rank 2001-5000 (= C-2a): {len(allcand[2000:5000])}")
print(f"  rank 5001-10000 (= C-2b): {len(allcand[5000:10000])}")
print(f"  rank 10001+ (= C-2c): {len(allcand[10000:])}")

# Now: C-2c subset, foreign + no en
text = SEED3.read_text(encoding="utf-8")
has_en_map = {}
cur_key = None
cur_has_en = False

for line in text.splitlines():
    m = re.match(r'^  - key:\s*(.+)$', line)
    if m:
        if cur_key is not None:
            has_en_map[cur_key] = cur_has_en
        cur_key = m.group(1).strip()
        cur_has_en = False
    elif cur_key is not None:
        if re.match(r'^\s+en:\s', line):
            cur_has_en = True
if cur_key is not None:
    has_en_map[cur_key] = cur_has_en

c2c_pool = allcand[10000:]
foreign = [r for r in c2c_pool if KATA.search(r["title"] or "")]
print(f"\nC-2c pool: {len(c2c_pool)}")
print(f"  foreign (katakana含む): {len(foreign)}")

no_en = [r for r in foreign if r["series_key"] and not has_en_map.get(r["series_key"], False)]
print(f"  foreign + en未fill: {len(no_en)}")
