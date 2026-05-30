"""v10 を「純粋加算型」に是正(慎重・退行ゼロ保証)。

方針: v9 が確定した S-tier マッチは **そのまま保持**(再スコアで動かさない)。
v9 が拾えなかった entry(NO_MATCH/DISPLACED/REJECT)だけ、 v10 の
著者経由 + N:1 + 改良正規化マッチで **埋める**(=純粋追加)。

→ v9 既存マッチ 0 退行を構造的に保証しつつ、 v10 の recall を上乗せ。

出力: .cache/match-v10-merged-all.tsv + before/after サマリ
"""
import csv, sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
S = {"S180", "S150", "S130", "S100"}


def load(p):
    d = {}
    with open(p, encoding="utf-8") as f:
        rd = csv.DictReader(f, delimiter="\t")
        cols = rd.fieldnames
        for r in rd:
            d[r["s3_key"]] = r
    return d, cols


def main():
    v9, cols = load(".cache/match-v9-all.tsv")
    v10, _ = load(".cache/match-v10-all.tsv")

    merged = {}
    src = Counter()
    for k in v9:
        r9 = v9[k]
        r10 = v10.get(k)
        if r9["verdict"] in S:
            merged[k] = r9          # v9 確定 → 保持(退行ゼロ)
            src["v9保持"] += 1
        elif r10 and r10["verdict"] in S:
            merged[k] = r10          # v9 空白 → v10 で埋める(純粋追加)
            src["v10で新規充填"] += 1
        else:
            merged[k] = r9 if not (r10 and r10["verdict"] in S) else r10
            src["未マッチ継続"] += 1

    # 出力
    with open(".cache/match-v10-merged-all.tsv", "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(cols) + "\n")
        for k in v9:
            r = merged[k]
            f.write("\t".join(str(r.get(c, "")) for c in cols) + "\n")

    # 退行チェック(構造的に0のはずだが検証)
    regress = 0
    for k in v9:
        if v9[k]["verdict"] in S and merged[k]["verdict"] not in S:
            regress += 1
        elif v9[k]["verdict"] in S and merged[k]["a_id"] != v9[k]["a_id"]:
            regress += 1

    cnt = Counter(merged[k]["verdict"] for k in merged)
    n = len(merged)
    accept = sum(cnt[v] for v in S)
    accept9 = sum(1 for k in v9 if v9[k]["verdict"] in S)

    print("=== 純粋加算マージ(v9保持 + v10充填)===")
    print(f"  内訳: {dict(src)}")
    print(f"  ★v9既存マッチの退行: {regress} 件(0 が正)")
    print()
    print(f"  v9  ACCEPT: {accept9:,} ({accept9*100/n:.1f}%)")
    print(f"  v10 merged: {accept:,} ({accept*100/n:.1f}%)  = +{accept-accept9:,}")
    print(f"  S180: {cnt['S180']:,} / S150: {cnt['S150']:,} / S130: {cnt['S130']:,} / S100: {cnt['S100']:,}")
    print(f"  DISPLACED: {cnt['DISPLACED']:,} / REJECT: {cnt['REJECT']:,} / NO_MATCH: {cnt['NO_MATCH']:,}")
    print(f"\nwrote .cache/match-v10-merged-all.tsv")


if __name__ == "__main__":
    main()
