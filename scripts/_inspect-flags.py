import os, glob, re, unicodedata, yaml, io, sys
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
PROD = "data/manga.v2"


def norm(t):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", t or "")).lower()


rows = [l.rstrip("\n").split("\t") for l in open("data/seeds/slug-final-integrated.tsv", encoding="utf-8")][1:]
by_base = defaultdict(list)
for r in rows:
    if len(r) > 6:
        by_base[r[4]].append(r)
prodset = set(os.path.basename(p)[:-4] for p in glob.glob(f"{PROD}/*.yml"))

flags = []
for base, grp in by_base.items():
    if base in prodset:
        continue
    primary = [r for r in grp if r[6] == base]
    suffixed_present = [r for r in grp if r[6] != base and r[6] in prodset]
    if not primary or not suffixed_present or len(grp) < 2:
        continue
    p = primary[0]
    cands = []
    for fp in glob.glob(f"{PROD}/{base}-*.yml"):
        slug = os.path.basename(fp)[:-4]
        d = yaml.safe_load(open(fp, encoding="utf-8")) or {}
        nv = sum(len(e.get("volumes", [])) for e in d.get("editions", []))
        cands.append((slug, d.get("title"), nv, "/".join(a.get("name", "") for a in d.get("authors", []))))
    match = [c for c in cands if norm(c[1]) == norm(p[1])]
    if len(match) == 1:
        continue  # Type A(別スクリプトで適用済)
    flags.append((base, p[1], p[2], sorted(cands, key=lambda c: -c[2])))

print(f"flag {len(flags)} 件の候補:")
for base, ptitle, pvols, cands in sorted(flags):
    print(f"\n■ base={base} (提案主版題={ptitle} 提案巻{pvols})")
    for slug, t, nv, au in cands:
        print(f"    {slug:<46} | 題={(t or '')[:24]:<24} | 巻{nv:>3} | 著={au[:30]}")
