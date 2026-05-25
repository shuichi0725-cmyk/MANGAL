"""cluster_key 改善 (= qid + title norm) の dry-run sim。

audit script の cluster_key 生成 を:
  旧: qid:{qid} (= 作家 qid 単独)
  新: qid:{qid}|title:{norm_title} (= 作家 qid + 作品 title)
に変更した場合の 効果を 比較。

audit script は 不変、 種2 sqlite 不変。 純粋 sim のみ。

出力:
  .cache/sim-cluster-diff.csv = cluster 単位 diff 全件
  .cache/sim-cluster-diff-summary.txt = 集計
"""
from __future__ import annotations
import csv
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, "scripts")
import importlib.util
spec = importlib.util.spec_from_file_location("audit", "scripts/_audit-volume-gaps.py")
audit = importlib.util.module_from_spec(spec)
saved = sys.argv[:]
sys.argv = ["_sim", "--no-filter"]
spec.loader.exec_module(audit)
sys.argv = saved

DB = Path(".cache/db-v2.sqlite")
OUT_DIFF = Path(".cache/sim-cluster-diff.csv")
OUT_SUMMARY = Path(".cache/sim-cluster-diff-summary.txt")


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    # 種3 keys
    seed3_keys, seed3_qids = audit.load_seed3_keys()

    # merge.yml
    import yaml
    alias_to_main = {}
    sid_to_forced_cluster = {}
    cluster_merge_editions = set()
    with Path("data/seeds/series-merge.yml").open(encoding="utf-8") as f:
        for entry in (yaml.safe_load(f) or []):
            main = entry.get("main")
            for a in entry.get("aliases", []) or []:
                alias_to_main[a] = main
            for sid in (entry.get("merge_sids") or []):
                ck = f"merge:{main}"
                sid_to_forced_cluster[int(sid)] = ck
                if entry.get("merge_edition_types"):
                    cluster_merge_editions.add(ck)

    print(f"[1/3] load series + cluster_key 計算...")
    series_rows = con.execute(
        "SELECT id, qid, series_key, title, subtitle FROM series"
    ).fetchall()
    seed3_sids = set()
    for r in series_rows:
        if r["series_key"] in seed3_keys: seed3_sids.add(r["id"])
        elif r["qid"] and r["qid"] in seed3_qids: seed3_sids.add(r["id"])

    title_to_qid = {}
    for r in series_rows:
        if r["qid"]:
            t = alias_to_main.get(r["title"], r["title"])
            key = audit.norm_title(t, r["subtitle"])
            title_to_qid.setdefault(key, r["qid"])
    main_to_qid = {}
    for r in series_rows:
        if r["qid"] and r["title"] in alias_to_main:
            main_to_qid.setdefault(alias_to_main[r["title"]], r["qid"])

    # 旧 cluster_key + 新 cluster_key を 各 sid で計算
    old_ckey = {}
    new_ckey = {}
    for r in series_rows:
        sid = r["id"]
        if sid in sid_to_forced_cluster:
            ck = sid_to_forced_cluster[sid]
            old_ckey[sid] = ck
            new_ckey[sid] = ck
            continue
        eff = alias_to_main.get(r["title"], r["title"])
        if r["qid"]:
            old_ck = f"qid:{r['qid']}"
            new_ck = f"qid:{r['qid']}|t:{audit.norm_title(eff, r['subtitle'])}"
        elif eff in main_to_qid:
            old_ck = f"qid:{main_to_qid[eff]}"
            new_ck = f"qid:{main_to_qid[eff]}|t:{audit.norm_title(eff, r['subtitle'])}"
        else:
            norm = audit.norm_title(eff, r["subtitle"])
            if norm in title_to_qid:
                old_ck = f"qid:{title_to_qid[norm]}"
                new_ck = f"qid:{title_to_qid[norm]}|t:{norm}"
            else:
                old_ck = f"title:{norm}"
                new_ck = f"title:{norm}"
        old_ckey[sid] = old_ck
        new_ckey[sid] = new_ck

    print(f"[2/3] volumes 集計 (旧 vs 新)...")
    vrows = con.execute("""
        SELECT v.number, v.is_extra, e.type, e.imprint, s.id AS sid, s.title
        FROM volumes v JOIN editions e ON e.id=v.edition_id JOIN series s ON s.id=e.series_id
    """).fetchall()

    def to_int(s):
        try:
            n = int(s); return n if n > 0 else None
        except (ValueError, TypeError):
            return None

    old_buckets = defaultdict(set)  # (ckey, edt) → numbers
    new_buckets = defaultdict(set)
    old_sids_per = defaultdict(set)
    new_sids_per = defaultdict(set)
    for v in vrows:
        if v["is_extra"]: continue
        if v["sid"] not in seed3_sids: continue  # 種3 紐付き scope filter
        if not audit.edition_passes(v["type"], v["imprint"]): continue
        if not audit.title_passes(v["title"]): continue
        n = to_int(v["number"])
        if n is None: continue
        edt = v["type"] or "standard"
        o_ck = old_ckey.get(v["sid"])
        n_ck = new_ckey.get(v["sid"])
        if not o_ck: continue
        o_edt = "*" if o_ck in cluster_merge_editions else edt
        n_edt = "*" if n_ck in cluster_merge_editions else edt
        old_buckets[(o_ck, o_edt)].add(n)
        new_buckets[(n_ck, n_edt)].add(n)
        old_sids_per[(o_ck, o_edt)].add(v["sid"])
        new_sids_per[(n_ck, n_edt)].add(v["sid"])

    def calc_gap(nums):
        if not nums: return 0, 0
        mx = max(nums)
        if mx < 3 or mx > 300: return mx, 0
        return mx, len(set(range(1, mx+1)) - nums)

    print(f"[3/3] diff 集計 + 出力...")
    # 旧 cluster ごとに、 新 cluster で 何 cluster に分割されたか
    old_to_new_clusters = defaultdict(set)
    for sid, o_ck in old_ckey.items():
        n_ck = new_ckey.get(sid)
        if n_ck:
            old_to_new_clusters[o_ck].add(n_ck)

    # 分類:
    # A. 旧 1 cluster → 新 N cluster (N>1) で 分割
    # B. 旧 cluster の gap と 新 cluster 群の gap 合計を比較
    diff_rows = []
    n_split = 0
    n_unmasked = 0  # 旧 gap=0 → 新 gap>0
    n_new_gap_total = 0
    n_old_gap_total = 0
    for o_ck, new_cks in old_to_new_clusters.items():
        if len(new_cks) <= 1: continue
        # この旧 cluster に対応する 旧 bucket (edition_type 別)
        old_keys = [k for k in old_buckets if k[0] == o_ck]
        new_keys = [k for k in new_buckets if k[0] in new_cks]
        for o_key in old_keys:
            old_nums = old_buckets[o_key]
            old_mx, old_gap = calc_gap(old_nums)
            # 同 edition_type の 新 buckets
            new_edt_keys = [k for k in new_keys if k[1] == o_key[1]]
            new_total_gap = sum(calc_gap(new_buckets[nk])[1] for nk in new_edt_keys)
            new_max_max = max((calc_gap(new_buckets[nk])[0] for nk in new_edt_keys), default=0)
            if old_gap == 0 and new_total_gap > 0:
                n_unmasked += 1
            n_split += 1
            n_old_gap_total += old_gap
            n_new_gap_total += new_total_gap
            diff_rows.append({
                "old_cluster_key": o_ck,
                "edition_type": o_key[1],
                "new_cluster_count": len(new_edt_keys),
                "old_max": old_mx,
                "old_present": len(old_nums),
                "old_gap": old_gap,
                "new_max_max": new_max_max,
                "new_gap_total": new_total_gap,
                "diff_gap": new_total_gap - old_gap,
                "sid_count": len(old_sids_per[o_key]),
            })

    diff_rows.sort(key=lambda x: -x["diff_gap"])

    OUT_DIFF.parent.mkdir(parents=True, exist_ok=True)
    with OUT_DIFF.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(diff_rows[0].keys()) if diff_rows else ["old_cluster_key"])
        w.writeheader()
        w.writerows(diff_rows)

    lines = [
        "=== cluster_key 改善 (= qid + title norm) dry-run sim ===",
        f"",
        f"旧 cluster 数 (= 集計 bucket 数): {len(old_buckets):,}",
        f"新 cluster 数 (= 集計 bucket 数): {len(new_buckets):,}",
        f"diff (= 増加 cluster 数)         : {len(new_buckets) - len(old_buckets):+,}",
        f"",
        f"旧 1 cluster → 新 N cluster 分割: {n_split:,} 件",
        f"  うち 旧 gap=0 → 新 gap>0 (= マスク解除) : {n_unmasked:,} 件",
        f"  旧 gap 合計 : {n_old_gap_total:,}",
        f"  新 gap 合計 : {n_new_gap_total:,}",
        f"  diff (= 新規露出 gap) : {n_new_gap_total - n_old_gap_total:+,}",
        f"",
        f"--- top 20 diff_gap (= 新規露出多い順) ---",
    ]
    for r in diff_rows[:20]:
        lines.append(f"  diff={r['diff_gap']:+>4}  edt={r['edition_type']:<10}  "
                     f"old: max={r['old_max']:>3} pres={r['old_present']:>3} gap={r['old_gap']:>3} | "
                     f"new: max={r['new_max_max']:>3} gap={r['new_gap_total']:>3} "
                     f"split={r['new_cluster_count']:>2}  sids={r['sid_count']:>3}  cluster={r['old_cluster_key']}")
    OUT_SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  {OUT_SUMMARY}")
    print(f"  {OUT_DIFF}")
    print()
    print("\n".join(lines))


if __name__ == "__main__":
    main()
