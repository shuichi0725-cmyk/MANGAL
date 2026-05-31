"""merge後の残衝突(2,005 base)を merge漏れ vs 真の別作品 に三分類。

著者 canonical 化(mangaka.csv: qid↔name↔alt_names)で、 衝突する別ページが
canonical 著者を共有する=同一作品の merge漏れ。 共有しない=真の別作品。
出力 .cache/slug-collision-triage.tsv + 集計。 ※調査のみ。
"""
import json, csv, sys, re
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
MANGAKA = Path("data/seed/mangaka.csv")
MERGE = Path("data/seeds/series-merge-auto.json")
FINAL = Path(".cache/slug-final.tsv")


def build_resolver():
    by_name = {}
    for r in csv.DictReader(MANGAKA.open(encoding="utf-8")):
        q = r["qid"]
        if r["name"]: by_name[r["name"]] = q
        for alt in (r.get("alt_names") or "").split("|"):
            if alt: by_name.setdefault(alt, q)
    return by_name


def page_authors(merge_keys, by_name):
    """group の全 merge_key から canonical 著者集合を作る。"""
    auth = set()
    for k in merge_keys:
        for p in k.split("|"):
            if p.startswith("qid:"):
                auth.add(p[4:])              # 著者qid(shu2_qid_is_author)
            elif p.startswith("name:"):
                pass
        names = [p[5:] for p in k.split("|") if p.startswith("name:")]
        if len(names) >= 2:                  # name[0]=著者
            a = names[0]
            auth.add(by_name.get(a, a))      # canonical qid or 生name
    return auth


def main():
    by_name = build_resolver()
    mg = json.loads(MERGE.read_text(encoding="utf-8"))["merges"]
    # rep(代表key)→ group の merge_keys
    rep_keys = {}
    key2group = {}
    for g in mg:
        for k in g["merge_keys"]:
            key2group[k] = g["merge_keys"]

    # slug-final: base_slug → set(rep), rep→ (title, vols)
    rows = list(csv.DictReader(FINAL.open(encoding="utf-8"), delimiter="\t"))
    base2reps = defaultdict(set)
    rep_info = {}
    for r in rows:
        base2reps[r["base_slug"]].add(r["rep"])
        rep_info[r["rep"]] = (r["title"], int(r["vols"] or 0), r["year"])

    merge_miss = []; year_suspect = []; diff_works = []
    for base, reps in base2reps.items():
        if len(reps) < 2:
            continue
        ra = {}; ry = {}
        for rep in reps:
            mks = key2group.get(rep, [rep])
            ra[rep] = page_authors(mks, by_name)
            ry[rep] = rep_info[rep][2]
        repl = list(reps)
        shares = False; same_year = False
        for i in range(len(repl)):
            for j in range(i+1, len(repl)):
                if ra[repl[i]] & ra[repl[j]]:
                    shares = True
                yi, yj = ry[repl[i]], ry[repl[j]]
                if yi and yj and abs(int(yi)-int(yj)) <= 1:   # 同年±1=同作の疑い
                    same_year = True
        rec = (base, [(rep_info[r][0], rep_info[r][1], rep_info[r][2], "|".join(sorted(ra[r])[:2])) for r in repl])
        if shares:
            merge_miss.append(rec)
        elif same_year:                  # ★著者非共有でも同年=同作疑い(表記揺れ等)
            year_suspect.append(rec)
        else:
            diff_works.append(rec)

    print(f"=== merge後 残衝突 base: {sum(1 for b,rs in base2reps.items() if len(rs)>=2):,} ===")
    print(f"  ★merge漏れ(著者共有): {len(merge_miss):,}")
    print(f"  ★同年衝突(著者非共有でも同作疑い): {len(year_suspect):,}")
    print(f"  真の別作品(著者非共有・別年): {len(diff_works):,}")

    with open(".cache/slug-collision-triage.tsv", "w", encoding="utf-8") as f:
        f.write("category\tbase\tpages\n")
        for cat, lst in (("merge_miss", merge_miss), ("year_suspect", year_suspect), ("diff_works", diff_works)):
            for base, pages in lst:
                det = " || ".join(f"{t[:16]}(v{v},{y},{a[:14]})" for t, v, y, a in pages)
                f.write(f"{cat}\t{base}\t{det}\n")
    print("wrote .cache/slug-collision-triage.tsv")

    print("\n=== ★同年衝突 サンプル18(別作品と思ったが同年=同作疑い)===")
    for base, pages in year_suspect[:18]:
        det = " | ".join(f"{t[:14]}(v{v},{y},{a[:8]})" for t, v, y, a in pages)
        print(f"  {base[:20]:<20} {det}")
    print("\n=== 真の別作品(別年)サンプル8 ===")
    for base, pages in diff_works[:8]:
        det = " | ".join(f"{t[:12]}(v{v},{y})" for t, v, y, a in pages)
        print(f"  {base[:20]:<20} {det}")


if __name__ == "__main__":
    main()
