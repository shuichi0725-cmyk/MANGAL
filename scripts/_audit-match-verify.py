"""汎用 matcher 検証(v12/v13… 使い回し)。 引数 = 検証する版の番号(例 12)。

核心: v9↔v10 で割れた「本編vs派生版」156件で 本編(=高popularity)を選べたか、
+ v9 退行(喪失/a_id変化)、 + 既知ケース追跡。

使い方: python _audit-match-verify.py 12
"""
import csv, gzip, json, re, sys, unicodedata

sys.stdout.reconfigure(encoding="utf-8")
S = {"S180", "S150", "S130", "S100"}
VER = sys.argv[1] if len(sys.argv) > 1 else "12"


def load(p):
    d = {}
    with open(p, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            d[r["s3_key"]] = r
    return d


def main():
    v9 = load(".cache/match-v9-all.tsv")
    v10 = load(".cache/match-v10-all.tsv")
    vN = load(f".cache/match-v{VER}-all.tsv")
    pop = {}
    with gzip.open(".cache/anilist-manga-dump-v3.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            m = json.loads(line); pop[m.get("id")] = m.get("popularity") or 0

    def P(aid):
        try: return pop.get(int(aid), -1) if aid else -1
        except: return -1

    known = ["Q.E.D.", "ウマ娘シンデレラグレイ", "かしこまりました、デスティニー",
             "変身忍者嵐", "今日から俺は!!", "カリギュラの恋", "SHAMAN KING", "COBRA"]
    print(f"=== 既知ケース v9/v10/v{VER} (pop) ===")
    for k, r in list(v9.items()):
        if r["s3_title"] in known:
            r10 = v10.get(k, {}); rN = vN.get(k, {})
            print(f"  {r['s3_title'][:16]}: v9={r['a_native'][:20]}({P(r['a_id'])}) | v10={r10.get('a_native','')[:20]}({P(r10.get('a_id'))}) | v{VER}={rN.get('a_native','')[:20]}({P(rN.get('a_id'))})")
            known.remove(r["s3_title"])

    # 本編選択率(v9↔v10割れで 高pop を vN が選んだか)
    main_pick = sub_pick = other = 0
    for k, r9 in v9.items():
        r10 = v10.get(k); rN = vN.get(k)
        if not r10 or not rN: continue
        if not (r9["verdict"] in S and r10["verdict"] in S and r9["a_id"] != r10["a_id"]): continue
        main_id = r9["a_id"] if P(r9["a_id"]) >= P(r10["a_id"]) else r10["a_id"]
        if rN["a_id"] == main_id: main_pick += 1
        elif rN["a_id"] in (r9["a_id"], r10["a_id"]): sub_pick += 1
        else: other += 1
    tot = main_pick + sub_pick + other
    print(f"\n=== 本編vs派生版 解決率(v9↔v10割れ {tot}件)===")
    print(f"  本編(高pop)選択: {main_pick} ({main_pick*100//max(tot,1)}%) / 派生版: {sub_pick} / 別: {other}")

    # vN vs v9 退行
    new = changed = lost = stable = 0
    for k, r9 in v9.items():
        rN = vN.get(k)
        if not rN: continue
        in9 = r9["verdict"] in S; inN = rN["verdict"] in S
        if inN and not in9: new += 1
        elif in9 and inN:
            if r9["a_id"] == rN["a_id"]: stable += 1
            else: changed += 1
        elif in9 and not inN: lost += 1
    av9 = sum(1 for r in v9.values() if r["verdict"] in S)
    avN = sum(1 for r in vN.values() if r["verdict"] in S)
    print(f"\n=== v{VER} vs v9 ===  ACCEPT v9={av9:,} / v{VER}={avN:,}")
    print(f"  新規:{new:,} / a_id変化:{changed:,} / 喪失:{lost:,} / 安定:{stable:,}")


if __name__ == "__main__":
    main()
