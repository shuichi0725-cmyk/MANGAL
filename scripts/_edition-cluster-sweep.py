"""Stage F: 版クラスタ分裂(同一作の新装/完全版/文庫等が別ページ)のスイープ候補抽出。 ★抽出のみ。

検出: rep ページ間で
  1. ★版マーカーを剥いだコア題が一致(新装再編版/新装版/完全版/愛蔵版/文庫版/ワイド版/カラー版 等)
  2. ★作者 qid を共有(merge群全key + mangaka.csv 解決)
  3. 副題(sub:)が異ならない
→ ユーザ8/6裁定「冊数/サイズ違い=版タブ=1ページ」により merge 対象。
マーカー無し同題ペア(別クラスタ分裂)は year差のみ表示し held(個別確証へ)。
魔法科(mahouka)は Stage E の map 適用領域 = 除外。
"""
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**7)
ROOT = Path(__file__).resolve().parent.parent

MARKER = re.compile(
    r"(新装再編版|新装版|完全版|愛蔵版|文庫版|ワイド版|カラー版|フルカラー版|新装|"
    r"パーフェクト版|豪華版|決定版|完全復刻版|復刻版|廉価版|総集編版|ディレクターズカット版)"
)


def core_title(t):
    c = MARKER.sub("", t)
    c = re.sub(r"[\s　☆★・×/／\-‐【】\[\]()（）「」『』]+", "", c)
    return c.upper()


def main():
    by_name = {}
    for r in csv.DictReader((ROOT / "data/seed/mangaka.csv").open(encoding="utf-8")):
        if r["name"]:
            by_name[r["name"]] = r["qid"]
        for alt in (r.get("alt_names") or "").split("|"):
            if alt:
                by_name.setdefault(alt, r["qid"])
    mg = json.loads((ROOT / "data/seeds/series-merge-auto.json").read_text(encoding="utf-8"))["merges"]
    key2group = {}
    for g in mg:
        for k in g["merge_keys"]:
            key2group[k] = g["merge_keys"]

    def sub_of(key):
        s = [p[4:] for p in key.split("|") if p.startswith("sub:")]
        return s[0] if s else ""

    def authors(rep):
        qs = set()
        for k in key2group.get(rep, [rep]):
            for p in k.split("|"):
                if p.startswith("qid:"):
                    qs.add(p[4:])
            ns = [p[5:] for p in k.split("|") if p.startswith("name:")]
            if len(ns) >= 2 and ns[0] in by_name:
                qs.add(by_name[ns[0]])
        return qs

    reps = {}
    with (ROOT / ".cache/slug-final.tsv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["rep"] not in reps:
                reps[r["rep"]] = (r["title"], int(r["vols"] or 0), r["year"], r["final_slug"])

    # コア題 → reps
    core2 = defaultdict(list)
    for rep, (t, v, y, s) in reps.items():
        if "mahouka" in s or "魔法科" in t:
            continue
        core2[core_title(t)].append(rep)

    def is_marked(rep):
        """題 or 副題キーが版マーカーを含む(SLAM DUNK|sub:新装再編版 型を捕捉)。"""
        t, _, _, _ = reps[rep]
        if MARKER.search(t):
            return True
        sb = sub_of(rep)
        return bool(sb) and bool(MARKER.search(sb)) and len(MARKER.sub("", re.sub(r"[\s　]", "", sb))) <= 2

    cands = []
    review = []
    for core, ms in core2.items():
        if len(ms) < 2 or not core:
            continue
        marked = [m for m in ms if is_marked(m)]
        plain = [m for m in ms if not is_marked(m)]
        if marked and plain:
            for pm in marked:
                best = None
                for rm in plain:
                    share = authors(pm) & authors(rm)
                    if not share:
                        continue
                    if sub_of(rm):     # 本編側に真の副題がある=別シリーズの可能性 → 除外
                        continue
                    if best is None or reps[rm][1] > reps[best[0]][1]:
                        best = (rm, share)
                if best:
                    rm, share = best
                    cands.append({
                        "core": core[:30], "main": rm, "ed_page": pm,
                        "main_t": reps[rm][0], "ed_t": reps[pm][0] + ("|sub:" + sub_of(pm) if sub_of(pm) else ""),
                        "main_v": reps[rm][1], "ed_v": reps[pm][1],
                        "main_slug": reps[rm][3], "ed_slug": reps[pm][3],
                        "qid": sorted(share),
                    })
        elif len(plain) >= 2:
            # ★マーカー無し同題・qid共有 = 版クラスタ疑い(tokyo-ghoul-2012型)→ 個別確証行き
            for i in range(len(plain)):
                for j in range(i + 1, len(plain)):
                    a, b = plain[i], plain[j]
                    share = authors(a) & authors(b)
                    if share and not sub_of(a) and not sub_of(b):
                        review.append((reps[a][0][:20], reps[a][3], reps[a][1], reps[a][2],
                                       reps[b][3], reps[b][1], reps[b][2], sorted(share)))

    print(f"版クラスタ候補(マーカー∧qid共有): {len(cands)}")
    for c in sorted(cands, key=lambda x: -x["ed_v"]):
        print(f"  [{c['main_t'][:18]}] v{c['main_v']} {c['main_slug'][:30]}  ←merge← "
              f"[{c['ed_t'][:30]}] v{c['ed_v']} {c['ed_slug'][:36]} qid={c['qid']}")
    print(f"\n★REVIEW(マーカー無し同題qid共有ペア=個別確証要): {len(review)}")
    for t, s1, v1_, y1, s2, v2_, y2, q in sorted(review, key=lambda x: -(x[2] + x[5]))[:25]:
        print(f"  {t:<20} {s1}(v{v1_},{y1}) || {s2}(v{v2_},{y2}) qid={q}")
    json.dump({"cands": cands, "review": review},
              (ROOT / ".cache/edition-sweep-candidates.json").open("w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("-> .cache/edition-sweep-candidates.json")


if __name__ == "__main__":
    main()
