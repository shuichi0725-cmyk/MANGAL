"""v9↔v10 の食い違いを独立信号で裁定し、 問題点を炙り出す(ユーザ案)。

差分 = 「どちらかが誤 or 真に曖昧」の濃縮リスト。 全件監査せず差分だけで
systematic な問題を抽出。 各食い違いを **巻数/年/題/popularity** で裁定:
  - changed(a_id変化): v9 の a と v10 の a、 どちらが s3 に合うか
  - lost(v9 S→v10非S): v9 の a は本当に正しい(=v10退行)か誤(=v10が正しく落とした)か

出力: .cache/v9v10-diff-verdict.tsv(v9優勢/v10優勢/曖昧 + 根拠)
"""
import csv, gzip, json, re, sys, unicodedata
from collections import Counter
from pathlib import Path

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


def main():
    v9 = load(".cache/match-v9-all.tsv")
    v10 = load(".cache/match-v10-all.tsv")

    # v3 dump で id → (native, vols, year, popularity)
    info = {}
    for dump in (".cache/anilist-manga-dump-v3.jsonl.gz", ".cache/anilist-manga-dump.jsonl.gz"):
        if not Path(dump).exists(): continue
        with gzip.open(dump, "rt", encoding="utf-8") as f:
            for line in f:
                m = json.loads(line)
                i = m.get("id")
                if i in info: continue
                t = m.get("title") or {}
                info[i] = {
                    "native": t.get("native") or "", "vols": m.get("volumes"),
                    "year": (m.get("startDate") or {}).get("year"),
                    "pop": m.get("popularity") or 0,
                }

    def s3_int(r, k):
        try: return int(r[k]) if r.get(k) else None
        except: return None

    def judge_side(s3title, s3year, s3vols, aid):
        """a が s3 に合う度合い(0-3)を独立信号で。"""
        a = info.get(int(aid)) if aid else None
        if not a: return -1, "a情報なし"
        sc = 0; why = []
        if tnorm(s3title) and tnorm(s3title) == tnorm(a["native"]):
            sc += 1; why.append("題完全一致")
        elif tnorm(s3title) and (tnorm(s3title) in tnorm(a["native"]) or tnorm(a["native"]) in tnorm(s3title)):
            why.append("題包含")
        if s3year and a["year"] and abs(s3year - a["year"]) <= 1: sc += 1; why.append("年一致")
        if s3vols and a["vols"] and abs(s3vols - a["vols"]) <= 1: sc += 1; why.append("巻一致")
        return sc, f"{'/'.join(why)}(pop={a['pop']})"

    changed = []; lost = []
    for k, r9 in v9.items():
        r10 = v10.get(k)
        if not r10: continue
        if r9["verdict"] in S and r10["verdict"] in S and r9["a_id"] != r10["a_id"]:
            changed.append((k, r9, r10))
        elif r9["verdict"] in S and r10["verdict"] not in S:
            lost.append((k, r9, r10))

    # changed 裁定
    out = []
    tally = Counter()
    for k, r9, r10 in changed:
        st = r9["s3_title"]; sy = s3_int(r9, "s3_year"); sv = s3_int(r9, "s3_vols")
        s9, w9 = judge_side(st, sy, sv, r9["a_id"])
        s10, w10 = judge_side(st, sy, sv, r10["a_id"])
        if s9 > s10: verdict = "v9優勢(v10が改悪)"
        elif s10 > s9: verdict = "v10優勢(v9が誤=v10改善)"
        else: verdict = "曖昧(同点)"
        tally[("changed", verdict)] += 1
        out.append(("changed", verdict, st, f"v9:{r9['a_native'][:20]}[{w9}]", f"v10:{r10['a_native'][:20]}[{w10}]"))

    # lost 裁定: v9 の a は正しいか(=v10退行) / 誤か(=v10が正しく落とした)
    for k, r9, r10 in lost:
        st = r9["s3_title"]; sy = s3_int(r9, "s3_year"); sv = s3_int(r9, "s3_vols")
        s9, w9 = judge_side(st, sy, sv, r9["a_id"])
        verdict = "v9正しい=v10退行" if s9 >= 2 else ("v9怪しい=v10が落として妥当" if s9 <= 0 else "中間")
        tally[("lost", verdict)] += 1
        out.append(("lost", verdict, st, f"v9:{r9['a_native'][:20]}[{w9}]→v10:{r10['verdict']}", ""))

    print(f"=== v9↔v10 食い違い 裁定(changed {len(changed)} / lost {len(lost)})===\n")
    for (cat, v), c in sorted(tally.items()):
        print(f"  [{cat}] {v}: {c}")

    with open(".cache/v9v10-diff-verdict.tsv", "w", encoding="utf-8") as f:
        f.write("category\tverdict\ts3_title\tv9\tv10\n")
        for row in out:
            f.write("\t".join(str(x) for x in row) + "\n")
    print(f"\nwrote .cache/v9v10-diff-verdict.tsv ({len(out)} 行)")


if __name__ == "__main__":
    main()
