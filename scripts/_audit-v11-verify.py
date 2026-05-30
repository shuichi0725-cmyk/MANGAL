"""v11 検証(慎重)= v9/v10/v11 三者比較。

核心指標: v9↔v10 で a_id が割れた「本編vs派生版」ケースで、
本編(=高popularity)を v11 が選べたか。 + v9退行チェック。
"""
import csv, gzip, json, re, sys, unicodedata
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
S = {"S180", "S150", "S130", "S100"}


def load(p):
    d = {}
    with open(p, encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            d[r["s3_key"]] = r
    return d


def main():
    v9 = load(".cache/match-v9-all.tsv")
    v10 = load(".cache/match-v10-all.tsv")
    v11 = load(".cache/match-v11-all.tsv")
    pop = {}
    with gzip.open(".cache/anilist-manga-dump-v3.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            m = json.loads(line); pop[m.get("id")] = m.get("popularity") or 0

    def P(aid):
        try: return pop.get(int(aid), 0) if aid else -1
        except: return -1

    # 既知ケース追跡
    known = ["Q.E.D.", "ウマ娘シンデレラグレイ", "かしこまりました、デスティニー",
             "変身忍者嵐", "今日から俺は!!", "カリギュラの恋"]
    print("=== 既知ケース v9/v10/v11 (pop) ===")
    for k, r in list(v9.items()):
        if r["s3_title"] in known:
            r10 = v10.get(k, {}); r11 = v11.get(k, {})
            print(f"  {r['s3_title'][:18]}: v9={r['a_native'][:22]}({P(r['a_id'])}) | v10={r10.get('a_native','')[:22]}({P(r10.get('a_id'))}) | v11={r11.get('a_native','')[:22]}({P(r11.get('a_id'))})")
            known.remove(r["s3_title"])

    # 本編選択: v9↔v10 changed で 高pid を v11 が選べたか
    pick_main = pick_sub = pick_other = 0
    for k, r9 in v9.items():
        r10 = v10.get(k); r11 = v11.get(k)
        if not r10 or not r11: continue
        if not (r9["verdict"] in S and r10["verdict"] in S and r9["a_id"] != r10["a_id"]): continue
        p9, p10 = P(r9["a_id"]), P(r10["a_id"])
        main_id = r9["a_id"] if p9 >= p10 else r10["a_id"]   # 高pop = 本編
        if r11["a_id"] == main_id: pick_main += 1
        elif r11["a_id"] in (r9["a_id"], r10["a_id"]): pick_sub += 1
        else: pick_other += 1
    print(f"\n=== 本編vs派生版(v9↔v10割れ)で v11 が高pop本編を選んだか ===")
    print(f"  本編(高pop)選択: {pick_main}  / 派生版選択: {pick_sub}  / 別: {pick_other}")

    # v11 vs v9 退行
    new = changed = lost = stable = 0
    for k, r9 in v9.items():
        r11 = v11.get(k)
        if not r11: continue
        in9 = r9["verdict"] in S; in11 = r11["verdict"] in S
        if in11 and not in9: new += 1
        elif in9 and in11:
            stable += 1 if r9["a_id"] == r11["a_id"] else 0
            changed += 0 if r9["a_id"] == r11["a_id"] else 1
        elif in9 and not in11: lost += 1
    print(f"\n=== v11 vs v9 ===  ACCEPT v9={sum(1 for r in v9.values() if r['verdict'] in S):,} / v11={sum(1 for r in v11.values() if r['verdict'] in S):,}")
    print(f"  新規:{new:,} / a_id変化:{changed:,} / 喪失:{lost:,} / 安定:{stable:,}")


if __name__ == "__main__":
    main()
