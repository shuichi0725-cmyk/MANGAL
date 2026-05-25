"""うる星やつら関連 series に _promote-bulk-v2.py の filter を 適用 sim。

filter:
  1. KEEP_EDITION_TYPES のみ keep
  2. DROP_IMPRINT_PATTERNS に該当する imprint drop
  3. DROP_IMPRINT_LOWER_PATTERNS / NO_EQ
  4. DROP_TITLE_PREFIX_PATTERNS (= 'テレビアニメ版'/'劇場版' 等)
  5. DROP_TITLE_CONTAINS_PATTERNS (= 'の秘密'/'ガイドブック' 等)

破壊操作なし。 sim だけ。
"""
from __future__ import annotations
import sqlite3
from pathlib import Path

DB = Path(".cache/db-v2.sqlite")

# _promote-bulk-v2.py から 抽出 (= 同期保持)
KEEP_EDITION_TYPES = {"standard", "bunkobon", "wideban", "kanzenban", "shinsoban", "aizoban"}
DROP_IMPRINT_PATTERNS = [
    "My first big", "コンビニ", "増刊", "同人", "ジャンプremix", "フィルムコミック",
    "カッパ・ノベル", "カッパノベル", "カッパ・ホーム", "カッパホーム",
]
DROP_IMPRINT_LOWER_PATTERNS = ["bilingual", "english", "novel", "novels"]
DROP_IMPRINT_LOWER_PATTERNS_NO_EQ = ["complete works"]
DROP_TITLE_PREFIX_PATTERNS = [
    "テレビアニメ版", "TVアニメ版", "TVアニメ", "アニメコミック",
    "劇場版", "映画", "OVA",
    "ノベライズ", "ノベル",
    "英訳・", "英訳",
]
DROP_TITLE_CONTAINS_PATTERNS = [
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


def edition_passes_filter(edition_type: str, imprint: str) -> tuple[bool, str]:
    """edition の keep/drop 判定 + 理由。"""
    if edition_type not in KEEP_EDITION_TYPES:
        return False, f"edition.type={edition_type} not in KEEP"
    imp = (imprint or "")
    imp_l = imp.lower()
    for pat in DROP_IMPRINT_PATTERNS:
        if pat in imp:
            return False, f"imprint contains '{pat}'"
    for pat in DROP_IMPRINT_LOWER_PATTERNS:
        if pat in imp_l:
            return False, f"imprint(lower) contains '{pat}'"
    if "=" not in imp:
        for pat in DROP_IMPRINT_LOWER_PATTERNS_NO_EQ:
            if pat in imp_l:
                return False, f"imprint(lower no-eq) contains '{pat}'"
    return True, "keep"


def title_passes_filter(title: str) -> tuple[bool, str]:
    """series.title の keep/drop 判定 + 理由。"""
    if not title:
        return True, "keep (empty)"
    t = title.strip()
    for pat in DROP_TITLE_PREFIX_PATTERNS:
        if t.startswith(pat):
            return False, f"title starts with '{pat}'"
    for pat in DROP_TITLE_CONTAINS_PATTERNS:
        if pat in t:
            return False, f"title contains '{pat}'"
    return True, "keep"


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    srows = con.execute(
        "SELECT id, qid, title, subtitle FROM series "
        "WHERE title LIKE '%うる星やつら%' ORDER BY id"
    ).fetchall()

    print(f"=== うる星やつら 関連 = {len(srows)} sid に 全 _promote-bulk-v2.py filter 適用 ===\n")

    keep_total_vols = 0
    drop_total_vols = 0
    user_target_keep = 0  # ユーザ採用 (= 通常版 + ワイド + 文庫 + カラー 2)

    for s in srows:
        ok_title, reason_title = title_passes_filter(s["title"])
        sub_marker = f" sub='{s['subtitle']}'" if s["subtitle"] else ""
        print(f"sid={s['id']:>6}, qid={s['qid']!r}, title={s['title']!r}{sub_marker}")
        print(f"  title filter: {'KEEP' if ok_title else 'DROP'}  ({reason_title})")

        if not ok_title:
            # title drop ならば 全 edition drop
            erows = con.execute(
                "SELECT id, type, imprint FROM editions WHERE series_id=?", (s["id"],)
            ).fetchall()
            for e in erows:
                vcount = con.execute(
                    "SELECT COUNT(*) FROM volumes WHERE edition_id=?", (e["id"],)
                ).fetchone()[0]
                drop_total_vols += vcount
                print(f"  └ eid={e['id']}, type={e['type']}, imp={e['imprint']!r}, vols={vcount} → DROP (title)")
            print()
            continue

        erows = con.execute(
            "SELECT id, type, imprint FROM editions WHERE series_id=?", (s["id"],)
        ).fetchall()
        for e in erows:
            ok_ed, reason_ed = edition_passes_filter(e["type"], e["imprint"])
            vcount = con.execute(
                "SELECT COUNT(*) FROM volumes WHERE edition_id=?", (e["id"],)
            ).fetchone()[0]
            mark = "KEEP" if ok_ed else "DROP"
            print(f"  └ eid={e['id']}, type={e['type']:<10}, imp={e['imprint']!r:<50} vols={vcount:>3} → {mark}  ({reason_ed})")
            if ok_ed:
                keep_total_vols += vcount
            else:
                drop_total_vols += vcount
        print()

    print(f"=== sim summary ===")
    print(f"  KEEP 合計 volumes: {keep_total_vols}")
    print(f"  DROP 合計 volumes: {drop_total_vols}")


if __name__ == "__main__":
    main()
