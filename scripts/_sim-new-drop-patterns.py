"""新 DROP_TITLE_CONTAINS_PATTERNS 追加 (= 10 word) で drop される sid を 全件 dry-run 出力。

既存 patternで keep されているが、 新 patternで drop になる sid のみ列挙。
副作用確認用 = 「漫画作品 巻き添え 0」 を ユーザ verify。
"""
from __future__ import annotations
import csv
import sqlite3
from pathlib import Path

DB = Path(".cache/db-v2.sqlite")
OUT = Path(".cache/sim-new-drops.csv")

# 追加候補 10 word
NEW_PATTERNS = [
    "傑作選", "傑作集", "ベストセレクション", "特集号", "特別総集編",
    "原画集", "画集", "キャラクターブック", "ポケット画廊", "うちあけ話",
]

# 既存 (= _promote-bulk-v2.py から)
EXISTING_PATTERNS = [
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


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, qid, title FROM series WHERE title IS NOT NULL"
    ).fetchall()
    new_drops = []
    for r in rows:
        t = (r["title"] or "").strip()
        if not t: continue
        # 既存 patternで 既に drop なら skip
        if any(p in t for p in EXISTING_PATTERNS):
            continue
        # 新 patternで hit?
        matched = [p for p in NEW_PATTERNS if p in t]
        if matched:
            # 巻数取得
            vc = con.execute(
                "SELECT COUNT(*) FROM volumes v JOIN editions e ON e.id=v.edition_id "
                "WHERE e.series_id=?", (r["id"],)
            ).fetchone()[0]
            new_drops.append({
                "sid": r["id"],
                "qid": r["qid"] or "",
                "title": t,
                "matched_word": ",".join(matched),
                "vol_count": vc,
            })

    new_drops.sort(key=lambda x: (x["matched_word"], -x["vol_count"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(new_drops[0].keys()) if new_drops else ["sid"])
        w.writeheader()
        w.writerows(new_drops)

    # 集計
    from collections import Counter
    by_word = Counter(d["matched_word"].split(",")[0] for d in new_drops)
    print(f"=== 新 pattern 追加で 新規 drop sid: {len(new_drops)} ===")
    print()
    print("--- word 別件数 + 各 word の volume 数合計 ---")
    for w in NEW_PATTERNS:
        ds = [d for d in new_drops if w in d["matched_word"]]
        total_vc = sum(d["vol_count"] for d in ds)
        print(f"  {w:<25}: {len(ds):>3} sid / {total_vc:>4} volumes")
    print()
    print(f"--- 巻数 多い順 top 30 (= 巻き添えリスクチェック) ---")
    by_vc = sorted(new_drops, key=lambda x: -x["vol_count"])
    for d in by_vc[:30]:
        print(f"  vol={d['vol_count']:>3}, word='{d['matched_word']:<20}', title={d['title']!r}")
    print()
    print(f"  → CSV: {OUT}")


if __name__ == "__main__":
    main()
