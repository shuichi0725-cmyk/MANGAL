"""v9↔v10 差分を「種3 自身の年/巻/著者一致」で再裁定(popularity でなく確実信号)。

気づき: 「本編=高pop」は誤った前提。 種3 entry がどの AniList 作品に対応するかは、
その entry の 種2 年/巻/著者と一致する方で決まる。 popularity は弱い補助に過ぎない。

各 changed(a_id割れ)で v9 の a と v10 の a を、 s3 の (題/年/巻/著者) 一致で採点。
高い方が正。 → どちらのエンジンが本当に正しいかを データ で確定。
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
        for r in csv.DictReader(f, delimiter="\t"):
            d[r["s3_key"]] = r
    return d


def i(x):
    try: return int(x) if x else None
    except: return None


def agree(s3_title, s3y, s3v, s3a, a_native, a_year, a_vols, a_authors):
    """s3 と a の一致度(0-8)。 題/年/巻/著者。 確実信号のみ。"""
    sc = 0; w = []
    tn, an = tnorm(s3_title), tnorm(a_native)
    if tn and an:
        if tn == an: sc += 3; w.append("題完全")
        elif tn in an or an in tn: sc += 1; w.append("題包含")
    ay = i(a_year)
    if s3y and ay:
        if abs(s3y - ay) == 0: sc += 2; w.append("年完全")
        elif abs(s3y - ay) <= 1: sc += 1; w.append("年近")
        elif abs(s3y - ay) >= 5: sc -= 2; w.append("年乖離")
    av = i(a_vols)
    if s3v and av and abs(s3v - av) <= 1: sc += 2; w.append("巻一致")
    sset = set(x for x in (s3a or "").split("|") if x)
    aset = set(x for x in (a_authors or "").split("|") if x)
    if sset and aset and (sset & aset): sc += 2; w.append("著者一致")
    return sc, "/".join(w)


def main():
    v9 = load(".cache/match-v9-all.tsv")
    v10 = load(".cache/match-v10-all.tsv")

    tally = Counter()
    rows = []
    for k, r9 in v9.items():
        r10 = v10.get(k)
        if not r10: continue
        if not (r9["verdict"] in S and r10["verdict"] in S and r9["a_id"] != r10["a_id"]):
            continue
        st = r9["s3_title"]; sy = i(r9["s3_year"]); sv = i(r9["s3_vols"]); sa = r9["s3_authors"]
        g9, w9 = agree(st, sy, sv, sa, r9["a_native"], r9["a_year"], r9["a_vols"], r9["a_authors"])
        g10, w10 = agree(st, sy, sv, sa, r10["a_native"], r10["a_year"], r10["a_vols"], r10["a_authors"])
        if g9 > g10: verdict = "v9正(v10誤)"
        elif g10 > g9: verdict = "v10正(v9誤)"
        else: verdict = "同点(真に曖昧)"
        tally[verdict] += 1
        rows.append((verdict, g9, g10, st, f"v9:{r9['a_native'][:18]}[{w9}]", f"v10:{r10['a_native'][:18]}[{w10}]"))

    print(f"=== 差分 a_id割れ {sum(tally.values())} 件を「種3年/巻/著者一致」で再裁定 ===")
    for v, c in tally.most_common():
        print(f"  {v}: {c}")
    print("\n=== サンプル: v10正(v9誤) 先頭10 ===")
    for r in [r for r in rows if r[0] == "v10正(v9誤)"][:10]:
        print(f"  ({r[1]}vs{r[2]}) {r[3][:18]} | {r[4][:40]} | {r[5][:40]}")
    print("\n=== サンプル: v9正(v10誤) 先頭10 ===")
    for r in [r for r in rows if r[0] == "v9正(v10誤)"][:10]:
        print(f"  ({r[1]}vs{r[2]}) {r[3][:18]} | {r[4][:40]} | {r[5][:40]}")

    with open(".cache/diff-grounded.tsv", "w", encoding="utf-8") as f:
        f.write("verdict\tg9\tg10\ts3_title\tv9\tv10\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")
    print("\nwrote .cache/diff-grounded.tsv")

    # 各版が「接地正解(明確な勝者)」を何件取れたか
    import os
    winners = {}  # key → 正解 a_id (明確な時のみ)
    for k, r9 in v9.items():
        r10 = v10.get(k)
        if not r10: continue
        if not (r9["verdict"] in S and r10["verdict"] in S and r9["a_id"] != r10["a_id"]): continue
        st = r9["s3_title"]; sy = i(r9["s3_year"]); sv = i(r9["s3_vols"]); sa = r9["s3_authors"]
        g9, _ = agree(st, sy, sv, sa, r9["a_native"], r9["a_year"], r9["a_vols"], r9["a_authors"])
        g10, _ = agree(st, sy, sv, sa, r10["a_native"], r10["a_year"], r10["a_vols"], r10["a_authors"])
        if g9 > g10: winners[k] = r9["a_id"]
        elif g10 > g9: winners[k] = r10["a_id"]
    print(f"\n=== 接地正解(明確な勝者 {len(winners)} 件)を各版が取れたか ===")
    for ver, path in [("v9", ".cache/match-v9-all.tsv"), ("v10", ".cache/match-v10-all.tsv"),
                      ("v12", ".cache/match-v12-all.tsv"), ("merged", ".cache/match-v10-merged-all.tsv")]:
        if not os.path.exists(path): continue
        vd = load(path)
        ok = sum(1 for k, aid in winners.items() if vd.get(k) and vd[k]["a_id"] == aid)
        print(f"  {ver}: {ok} / {len(winners)} ({ok*100//len(winners)}%)")


if __name__ == "__main__":
    main()
