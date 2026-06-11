"""文庫版二重ページのスイープ候補抽出(幽☆遊☆白書型)。 ★抽出のみ・適用なし。

型: 同一作品なのに「版元クレジットが著者欄に入った記録」(ホーム社/編集部等)が別クラスタ化し、
本編ページと文庫(等)ページの2フォルダに割れているもの。

三条件(全て機械検証可能):
  1. 同一 base(=読みが同一。 続編/外伝は読みが違うので入らない)
  2. 作者 qid を共有(merge群全key + mangaka.csv name→qid 解決で判定)
  3. 片側のページ著者に版元クレジット名(ホーム社/編集部/コミックス/文庫 等)

副題(sub:)が異なるペアは保留(= 夫婦愛結び型スピンオフを誤併合しない)。
出力 .cache/bunko-sweep-candidates.json + 保留リスト。
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

PUB = re.compile(r"(ホーム社|編集部$|編集$|書店$|出版$|コミックス$|文庫$)")

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


def page_info(rep):
    qs, pubnames = set(), set()
    for k in key2group.get(rep, [rep]):
        for p in k.split("|"):
            if p.startswith("qid:"):
                qs.add(p[4:])
        ns = [p[5:] for p in k.split("|") if p.startswith("name:")]
        if len(ns) >= 2:
            a = ns[0]
            q = by_name.get(a)
            if q:
                qs.add(q)
            if PUB.search(a):
                pubnames.add(a)
    return qs, pubnames


def main():
    reps = {}
    with (ROOT / ".cache/slug-final.tsv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["rep"] not in reps:
                reps[r["rep"]] = (r["title"], int(r["vols"] or 0), r["year"], r["base_slug"], r["final_slug"])
    base2 = defaultdict(list)
    for rep, v in reps.items():
        base2[v[3]].append(rep)

    cands, held = [], []
    with (ROOT / ".cache/slug-collision-triage.tsv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["category"] != "merge_miss":
                continue
            members = base2.get(r["base"], [])
            if len(members) < 2:
                continue
            infos = {m: page_info(m) for m in members}
            for pm in members:
                pq, ppub = infos[pm]
                if not ppub:
                    continue
                for rm in members:
                    if rm == pm:
                        continue
                    rq, _ = infos[rm]
                    share = pq & rq
                    if not share:
                        continue
                    if sub_of(pm) != sub_of(rm):
                        held.append((r["base"], reps[rm][0][:24], reps[pm][0][:24], "SUB_DIFF"))
                        continue
                    cands.append({
                        "base": r["base"], "main": rm, "pub_page": pm,
                        "main_t": reps[rm][0], "pub_t": reps[pm][0],
                        "main_v": reps[rm][1], "pub_v": reps[pm][1],
                        "pub_names": sorted(ppub), "qid": sorted(share),
                    })
                    break

    print(f"候補: {len(cands)}")
    for c in cands:
        pn = "/".join(c["pub_names"])[:20]
        print(f"  {c['base'][:34]:<34} 本編[{c['main_t'][:18]}]v{c['main_v']} + [{pn}]{c['pub_t'][:18]}v{c['pub_v']} qid={c['qid']}")
    print(f"保留(副題差): {len(held)}")
    for h in held[:10]:
        print("  HELD:", h)
    json.dump(cands, (ROOT / ".cache/bunko-sweep-candidates.json").open("w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("-> .cache/bunko-sweep-candidates.json")


if __name__ == "__main__":
    main()
