"""C-2a 候補抽出: draft 2000-5000 範囲、 カタカナ含む title、 en 未 fill。

draft-2000 と 同 scoring (= qid bonus 100 + vol_count) で 5000 件 抽出、
- 先頭 2000 = draft-2000 で C-1 済み → skip
- 2001-5000 = 今回対象 (= 約 3000 件)
- カタカナ含む title のみ
- series-supplement-v2.yml で en 未 fill のみ

出力: .cache/c2a/input.json (= [{slug, title, key}, ...])
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
SEED3 = ROOT / "data" / "seeds" / "series-supplement-v2.yml"
DRAFT_DIR = ROOT / "data" / "manga.draft-2000"
OUT = ROOT / ".cache" / "c2a" / "input.json"

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


def title_passes_filter(title: str) -> bool:
    if not title:
        return False
    for p in DROP_TITLE_PATTERNS:
        if title.startswith(p):
            return False
    for p in DROP_TITLE_CONTAINS:
        if p in title:
            return False
    return True


def extract_title_suffix(title: str) -> str | None:
    m = re.search(r"(第[一二三四五六七八九十百\d]+部|[IVX]+$)", title)
    return m.group(1) if m else None


def main():
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
    limit = 5000
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
        LIMIT ?
        """,
        list(KEEP_EDITION_TYPES) + [cutoff_date, limit * 5],
    ).fetchall()

    # Dedup by (kana_norm, part_suffix)、 take top 5000
    seen = set()
    top5000 = []
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
        top5000.append(dict(r))
        if len(top5000) >= 5000:
            break

    # Rank 2001-5000 → 残 3000
    rest = top5000[2000:]

    # Foreign-origin filter: title contains katakana
    foreign = []
    for r in rest:
        title = r["title"] or ""
        if KATA.search(title):
            foreign.append(r)

    # Load seed3 yml and find which ones have en already
    # Simple line-based scan: for each key (= series_key), check if en: present in its block
    text = SEED3.read_text(encoding="utf-8")
    # Map series_key → has_en
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

    # For each foreign candidate, check if en is missing
    candidates = []
    for r in foreign:
        skey = r["series_key"]
        if not skey:
            continue
        # series_key might be partial; check map
        has_en = has_en_map.get(skey, False)
        if has_en:
            continue
        candidates.append({
            "slug": None,  # not needed for fill
            "title": r["title"],
            "key": skey,
            "vol_count": r["vol_count"],
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"top5000 dedup: {len(top5000)}")
    print(f"rest (2001-5000): {len(rest)}")
    print(f"foreign (katakana含む): {len(foreign)}")
    print(f"foreign + en未fill: {len(candidates)}")
    print(f"wrote: {OUT}")


if __name__ == "__main__":
    main()
