"""v14 = 退行0版 = v9 と v13 の grounded-best マージ。

各 entry で v9 のマッチと v13 のマッチを「種3 自身の年/巻/著者一致(grounded)」で
比較し、 **高い方を採用**(同点は v9 優先=安定)。
→ v9 が grounded で勝つ所は必ず保持(退行0)、 v13 が勝つ所だけ改善取込。
→ v13 の新規マッチ(v9 に無い)はそのまま採用(純粋追加)。

出力: .cache/match-v14-all.tsv + 検証(退行0 / 接地精度)
"""
import csv, re, sys, unicodedata
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
S = {"S180", "S150", "S130", "S100"}


def tnorm(s):
    if not s: return ""
    s = re.split(r"[:：]", s, 1)[0]
    s = re.sub(r"[（(【\[].*?[）)】\]]", "", s)
    s = "".join(ch for ch in s if unicodedata.category(ch)[0] != "P" and ch not in "ー―~〜")
    return re.sub(r"[\s　・]+", "", s).lower()


def load(p):
    d = {}
    with open(p, encoding="utf-8") as f:
        cols = None
        rd = csv.DictReader(f, delimiter="\t"); cols = rd.fieldnames
        for r in rd: d[r["s3_key"]] = r
    return d, cols


def I(x):
    try: return int(x) if x else None
    except: return None


def agree(r):
    """マッチ行 r の grounded 一致度(種3年/巻/著者 vs a)。 非Sは -999。"""
    if r["verdict"] not in S: return -999
    sy, sv = I(r["s3_year"]), I(r["s3_vols"])
    sa = set(x for x in (r["s3_authors"] or "").split("|") if x)
    sc = 0
    tn, an = tnorm(r["s3_title"]), tnorm(r["a_native"])
    if tn and an:
        if tn == an: sc += 3
        elif tn in an or an in tn: sc += 1
    ay, av = I(r["a_year"]), I(r["a_vols"])
    if sy and ay:
        d = abs(sy - ay); sc += 2 if d == 0 else (1 if d <= 1 else (-2 if d >= 5 else 0))
    if sv and av and abs(sv - av) <= 1: sc += 2
    aa = set(x for x in (r["a_authors"] or "").split("|") if x)
    if sa and aa and (sa & aa): sc += 2
    return sc


def main():
    v9, cols = load(".cache/match-v9-all.tsv")
    v13, _ = load(".cache/match-v13-all.tsv")

    merged = {}
    src = Counter()
    for k, r9 in v9.items():
        r13 = v13.get(k, r9)
        g9, g13 = agree(r9), agree(r13)
        if g9 >= g13:                 # 同点含め v9 優先(退行0・安定)
            merged[k] = r9; src["v9採用" if r9["verdict"] in S else "非マッチ"] += 1
        else:
            merged[k] = r13; src["v13採用(改善)"] += 1

    with open(".cache/match-v14-all.tsv", "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(cols) + "\n")
        for k in v9:
            r = merged[k]
            f.write("\t".join(str(r.get(c, "")) for c in cols) + "\n")

    # 退行検証: v9 の S-tier が v14 で 喪失/grounded悪化 してないか
    regress = 0
    for k, r9 in v9.items():
        if r9["verdict"] not in S: continue
        rm = merged[k]
        if rm["verdict"] not in S: regress += 1
        elif agree(rm) < agree(r9): regress += 1
    av9 = sum(1 for r in v9.values() if r["verdict"] in S)
    av14 = sum(1 for r in merged.values() if r["verdict"] in S)
    print("=== v14 = v9⊕v13 grounded-best ===")
    print(f"  内訳: {dict(src)}")
    print(f"  ★v9比 退行(喪失 or grounded悪化): {regress} 件(0 が目標)")
    print(f"  ACCEPT: v9={av9:,} → v14={av14:,} (+{av14-av9:,})")


if __name__ == "__main__":
    main()
