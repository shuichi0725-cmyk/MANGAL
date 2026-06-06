"""slug適用: 合成ソース(data/manga)生成。 ★冪等。 promote入力。
recluster元base除外(Stage D)・drop除外。 ★長すぎslug(>100字)はハイフン境界cap+dedup。
usage: python _slug-apply-build.py [--limit N]
"""
import sys, csv, sqlite3, re
from pathlib import Path
import yaml
sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**7)
ROOT = Path(__file__).resolve().parent.parent
A = ROOT / ".cache" / "apply"
SRC = ROOT / "data" / "manga"

key2slug = {r["key"]: r["slug"] for r in csv.DictReader((A/"key2slug.tsv").open(encoding="utf-8"), delimiter="\t")}
drop = set((A/"drop-keys.txt").read_text(encoding="utf-8").split("\n")) - {""}
# Stage D recluster で作り直した源キーを除外(git追跡seed・コメント行#は無視)
_xtra = ROOT/"data/seeds/recluster-drop-source-keys.txt"
if _xtra.exists():
    drop |= {l.strip() for l in _xtra.read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.startswith("#")}
recl_full_bases = set(r["base"] for r in csv.DictReader((ROOT/"data/seeds/slug-recluster-candidates.tsv").open(encoding="utf-8"), delimiter="\t"))
con = sqlite3.connect(ROOT/".cache"/"db-v2.sqlite"); con.text_factory = lambda b: b.decode("utf-8","replace")
k2tq = {sk: (t, q) for sk, t, q in con.execute("SELECT series_key,title,qid FROM series")}

def cap(s, n=100):
    if len(s) <= n: return s
    cut = s[:n].rsplit("-", 1)[0]
    return cut or s[:n]

# slug→代表key(merge群1ページ・recluster元除外・cap+dedup)
slug2key = {}; used = set()
order = sorted(key2slug.items())  # 決定的
for k, s in order:
    if k in drop or s in recl_full_bases or k not in k2tq: continue
    s = cap(s)
    if s in used and slug2key.get(s) is not None:  # 既に別keyが取得済(merge群=同slug)→skip
        # merge群は同slugで1ページ、 cap衝突(別作)は -2
        if key2slug.get(slug2key[s]) and cap(key2slug[slug2key[s]]) == s and slug2key[s] != k:
            # 同cap基底だが別key=別作(cap衝突) → suffix
            c = s; i = 2
            while c in used: c = f"{s}-{i}"; i += 1
            s = c
        else:
            continue
    if s in used: 
        continue
    used.add(s); slug2key[s] = k

for f in SRC.glob("*.yml"): f.unlink()
limit = int(sys.argv[sys.argv.index("--limit")+1]) if "--limit" in sys.argv else None
n = 0; capped = 0
for s, k in slug2key.items():
    if limit and n >= limit: break
    t, q = k2tq[k]
    if len(key2slug[k]) > 100: capped += 1
    y = {"slug": s, "title": t, "wikidata_qid": q, "_skey": k, "title_romaji": ""}
    (SRC/(s+".yml")).write_text(yaml.safe_dump(y, allow_unicode=True, sort_keys=False), encoding="utf-8")
    n += 1
print(f"合成ソース: {n:,} 件(cap適用 {capped} / drop {len(drop)} / recluster元 {len(recl_full_bases)} 除外)")
