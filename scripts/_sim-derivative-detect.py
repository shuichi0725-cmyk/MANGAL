"""派生本 候補 自動検出 sim。

logic:
1. 全 qid 紐付き series を 走査
2. 同 qid 内で 巻数 多い sid を 「メイン」 判定
3. メイン title を **prefix として含む 別 title** の sid = 「派生本候補」
4. 派生 title から メイン title を 削除 → 残り word を 統計集計
5. 頻度高い word = drop pattern 追加候補

加えて 「全 series 横断 = 同 word が 多数 cluster に 出現」 する word が
true positive (= 派生本専用 word) で 「漫画作品名としても 使われる word」 が
false positive リスク。

出力:
  .cache/sim-derivative-candidates.csv = 派生本候補 全件
  .cache/sim-derivative-words.txt = 残り word 頻度 top
"""
from __future__ import annotations
import csv
import re
import sqlite3
import sys
from collections import defaultdict, Counter
from pathlib import Path
sys.path.insert(0, "scripts")
import importlib.util
spec = importlib.util.spec_from_file_location("audit", "scripts/_audit-volume-gaps.py")
audit = importlib.util.module_from_spec(spec)
saved = sys.argv[:]; sys.argv = ["_", "--no-filter"]
spec.loader.exec_module(audit); sys.argv = saved

DB = Path(".cache/db-v2.sqlite")
OUT_CSV = Path(".cache/sim-derivative-candidates.csv")
OUT_WORDS = Path(".cache/sim-derivative-words.txt")


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # qid 紐付き 全 series + 各 sid の standard 巻数
    rows = con.execute("""
        SELECT s.id, s.qid, s.title, s.subtitle,
               COALESCE(MAX(CAST(v.number AS INTEGER)), 0) AS max_n,
               COUNT(DISTINCT v.id) AS vol_count
        FROM series s
        LEFT JOIN editions e ON e.series_id=s.id AND e.type='standard'
        LEFT JOIN volumes v ON v.edition_id=e.id AND v.is_extra=0
        WHERE s.qid IS NOT NULL
        GROUP BY s.id
    """).fetchall()

    # qid → list of (sid, title, max_n, vol_count)
    by_qid = defaultdict(list)
    for r in rows:
        by_qid[r["qid"]].append((r["id"], r["title"] or "", r["max_n"], r["vol_count"]))

    candidates = []
    word_counter = Counter()
    word_cluster_counter = Counter()  # word が 何 cluster に出るか

    for qid, sids in by_qid.items():
        if len(sids) < 2: continue
        # main = 最大 vol_count sid
        main_sid, main_title, main_max, main_vc = max(sids, key=lambda x: x[3])
        if main_vc < 5: continue  # メイン本人が 5 vol 未満 = メイン不確定
        words_in_cluster = set()
        for sid, title, max_n, vc in sids:
            if sid == main_sid: continue
            if not title.startswith(main_title): continue
            if len(title) <= len(main_title): continue
            remainder = title[len(main_title):].strip()
            if not remainder: continue
            # 既存 filter で 既に drop されるものは 除外
            if not audit.title_passes(title): continue
            candidates.append({
                "qid": qid,
                "main_sid": main_sid,
                "main_title": main_title,
                "main_vol_count": main_vc,
                "derivative_sid": sid,
                "derivative_title": title,
                "derivative_vol_count": vc,
                "remainder_word": remainder,
            })
            word_counter[remainder] += 1
            words_in_cluster.add(remainder)
        for w in words_in_cluster:
            word_cluster_counter[w] += 1

    candidates.sort(key=lambda x: -x["main_vol_count"])
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(candidates[0].keys()) if candidates else ["qid"])
        w.writeheader()
        w.writerows(candidates)

    # word 統計
    lines = [
        f"=== 派生本 候補 検出 sim ===",
        f"",
        f"対象 qid 数 (= 2+ sid): {sum(1 for s in by_qid.values() if len(s) >= 2):,}",
        f"派生本候補 件数: {len(candidates):,}",
        f"unique remainder word 数: {len(word_counter):,}",
        f"",
        f"--- 全 word 出現数 top 50 (= 同 word が 何 cluster で 派生候補に現れるか) ---",
    ]
    for w, count in word_cluster_counter.most_common(50):
        # この word を 持つ 派生 candidate 例 3 つ表示
        examples = [c for c in candidates if c["remainder_word"] == w][:3]
        ex_str = "; ".join(f"'{c['derivative_title']}'" for c in examples)
        lines.append(f"  {count:>4} clusters | word='{w}' | 例: {ex_str}")
    OUT_WORDS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  {OUT_CSV} ({len(candidates)} rows)")
    print(f"  {OUT_WORDS}")
    print()
    print("\n".join(lines[:30]))


if __name__ == "__main__":
    main()
