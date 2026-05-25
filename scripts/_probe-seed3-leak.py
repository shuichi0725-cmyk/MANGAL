"""種3 ↔ 種2 紐付け 漏れ 調査。

問題: 種2 で 同一作品が 複数 sid に分裂している場合、
種3 1 entry が series_key 一致で 紐付くのは その中の 1 sid のみ。
残り sid は 「種2 にあるが 種3 から見えない」 = 紐付き 漏れ。

検出:
  1. 種2 全 series を cluster_key (= qid あれば qid、 なければ title norm)
     で 集約
  2. 各 cluster ごとに「種3 紐付き sid」 と 「種3 紐付き なし sid」 を 数える
  3. 「種3 紐付きあり 1+、 紐付き なし 1+」 cluster = **漏れあり** = 救済対象
  4. 「種3 紐付き 0」 cluster = 種3 未登録 = scope 外
  5. 「全 sid 種3 紐付き」 cluster = 完全紐付き = 救済不要

出力:
  .cache/seed3-leak.csv = 漏れあり cluster 全件
  .cache/seed3-leak-summary.txt = 集計
"""
from __future__ import annotations
import csv
import re
import sqlite3
import unicodedata
from collections import defaultdict
from pathlib import Path
import yaml

SEED3 = Path("data/seeds/series-supplement-v2.yml")
DB = Path(".cache/db-v2.sqlite")
MERGE_YML = Path("data/seeds/series-merge.yml")
OUT_CSV = Path(".cache/seed3-leak.csv")
OUT_SUMMARY = Path(".cache/seed3-leak-summary.txt")


def _clean(s):
    if not s:
        return ""
    out = []
    for ch in s:
        cat = unicodedata.category(ch)
        if cat[0] in ("P", "Z"):
            continue
        if ch in "ー―~〜":
            continue
        out.append(ch.lower())
    return "".join(out)


def norm_title(t, sub):
    return _clean(t) + "|" + _clean(sub)


def main():
    print(f"[1/4] load 種3 = {SEED3}...")
    with SEED3.open("r", encoding="utf-8") as f:
        seed3_data = yaml.safe_load(f)
    seed3_keys = {e["key"] for e in seed3_data["series"]}
    seed3_qids = set()
    for e in seed3_data["series"]:
        k = e["key"]
        if k.startswith("qid:"):
            seed3_qids.add(k.split("|", 1)[0][4:])
    print(f"  seed3 entries: {len(seed3_keys):,} (= keys), qid 持ち: {len(seed3_qids):,}")

    print(f"[2/4] load merge yml + DB...")
    alias_to_main = {}
    if MERGE_YML.exists():
        with MERGE_YML.open("r", encoding="utf-8") as f:
            merge_data = yaml.safe_load(f) or []
        for entry in merge_data:
            main = entry.get("main")
            for alias in entry.get("aliases", []) or []:
                alias_to_main[alias] = main

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    series_rows = con.execute(
        "SELECT id, qid, series_key, title, subtitle FROM series"
    ).fetchall()
    print(f"  series 総数: {len(series_rows):,}")

    # 種3 紐付き sid set (= series_key 一致 or qid 一致)
    seed3_sids = set()
    for r in series_rows:
        if r["series_key"] in seed3_keys:
            seed3_sids.add(r["id"])
        elif r["qid"] and r["qid"] in seed3_qids:
            seed3_sids.add(r["id"])
    print(f"  種3 紐付き 種2 sid: {len(seed3_sids):,}")

    print(f"[3/4] cluster_key で 集約 + 漏れ検出...")
    # cluster_key 計算 (= audit script と同 logic)
    title_to_qid = {}
    for r in series_rows:
        if r["qid"]:
            t = alias_to_main.get(r["title"], r["title"])
            key = norm_title(t, r["subtitle"])
            title_to_qid.setdefault(key, r["qid"])

    main_to_qid = {}
    for r in series_rows:
        if r["qid"] and r["title"] in alias_to_main:
            main_t = alias_to_main[r["title"]]
            main_to_qid.setdefault(main_t, r["qid"])

    cluster_total = defaultdict(set)    # ckey -> set of all sids
    cluster_in_seed3 = defaultdict(set) # ckey -> set of seed3-linked sids
    cluster_display = {}                # ckey -> representative title

    for r in series_rows:
        effective_title = alias_to_main.get(r["title"], r["title"])
        if r["qid"]:
            ckey = f"qid:{r['qid']}"
        elif effective_title in main_to_qid:
            ckey = f"qid:{main_to_qid[effective_title]}"
        else:
            norm = norm_title(effective_title, r["subtitle"])
            if norm in title_to_qid:
                ckey = f"qid:{title_to_qid[norm]}"
            else:
                ckey = f"title:{norm}"

        cluster_total[ckey].add(r["id"])
        if r["id"] in seed3_sids:
            cluster_in_seed3[ckey].add(r["id"])
        cluster_display.setdefault(ckey, effective_title or r["title"] or "")

    # 分類
    fully_linked = 0   # 全 sid 種3 紐付き
    partial_leak = 0   # 一部紐付き = 漏れあり
    no_link = 0        # 種3 紐付き ゼロ
    leak_rows = []
    for ckey, total_sids in cluster_total.items():
        in_seed3 = cluster_in_seed3.get(ckey, set())
        if not in_seed3:
            no_link += 1
            continue
        if in_seed3 == total_sids:
            fully_linked += 1
        else:
            partial_leak += 1
            missing_sids = total_sids - in_seed3
            # 漏れ sid の title sample 取得
            missing_titles = []
            for sid in list(missing_sids)[:5]:
                row = next(r for r in series_rows if r["id"] == sid)
                missing_titles.append(f"{sid}:'{row['title']}'/sub='{row['subtitle']}'")
            leak_rows.append({
                "cluster_key": ckey,
                "display_title": cluster_display[ckey],
                "total_sids": len(total_sids),
                "seed3_linked_sids": len(in_seed3),
                "missing_sids": len(missing_sids),
                "missing_sid_examples": " | ".join(missing_titles),
            })

    leak_rows.sort(key=lambda x: -x["missing_sids"])

    print(f"[4/4] write outputs...")
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(leak_rows[0].keys()) if leak_rows else
                           ["cluster_key", "display_title", "total_sids",
                            "seed3_linked_sids", "missing_sids", "missing_sid_examples"])
        w.writeheader()
        w.writerows(leak_rows)

    lines = [
        f"=== 種3 ↔ 種2 紐付け 漏れ 調査 ===",
        f"",
        f"種3 entries     : {len(seed3_keys):,}",
        f"種2 series 総数  : {len(series_rows):,}",
        f"種3 紐付き 種2 sid: {len(seed3_sids):,}",
        f"",
        f"--- cluster 単位 分類 ---",
        f"全 sid 種3 紐付き (= 完全紐付き)        : {fully_linked:,} cluster",
        f"一部 紐付き 一部 漏れ (= 救済対象)      : {partial_leak:,} cluster",
        f"種3 紐付き ゼロ (= scope 外)            : {no_link:,} cluster",
        f"--- ---",
        f"合計 cluster                            : {fully_linked + partial_leak + no_link:,}",
        f"",
        f"--- 漏れ sid 数 合計 ---",
        f"救済対象 = 種2 内 同 cluster なのに 種3 から見えない sid:",
        f"  合計 {sum(r['missing_sids'] for r in leak_rows):,} sid (= {partial_leak:,} cluster に 散在)",
        f"",
        f"--- top 20 漏れ cluster (= missing_sids 多い順) ---",
    ]
    for i, r in enumerate(leak_rows[:20], 1):
        lines.append(f"  {i:>3}. missing={r['missing_sids']:>3}, total={r['total_sids']:>3}, "
                     f"linked={r['seed3_linked_sids']:>3}  title='{r['display_title']}'")
    OUT_SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  {OUT_CSV}")
    print(f"  {OUT_SUMMARY}")
    print()
    print("\n".join(lines))


if __name__ == "__main__":
    main()
