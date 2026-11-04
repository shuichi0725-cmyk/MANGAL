import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from wiki_mag_lib import *
sys.stdout.reconfigure(encoding="utf-8")
rows = json.load(open(os.path.join(ROOT, ".cache/magazine-lists/madb-decision.json"), encoding="utf-8"))
cand = [r for r in rows if r[0] in ("未解決表", "その他") and r[1] in ("食い違い", "空欄→埋められる", "マスタに無い誌")]
hits = json.load(open(os.path.join(ROOT, ".cache/jawiki-title-hits.json"), encoding="utf-8"))
by_stem = {}; by_title = {}
for stem, title, n, w in hits:
    by_stem.setdefault(stem, []).append(w); by_title.setdefault(norm(title), []).append(w)
have = miss = 0; need = []
for r in cand:
    ws = by_stem.get(r[2], []) + by_title.get(norm(r[3]), [])
    ws = [w for w in dict.fromkeys(ws) if os.path.exists(os.path.join(ROOT, ".cache/wiki-sweep", safe_key(w) + ".txt"))]
    if ws: have += 1
    else: miss += 1; need.append(r[3])
print("候補", len(cand), "記事キャッシュあり", have, "無し", miss)
json.dump(sorted(set(need)), open(os.path.join(ROOT, ".cache/magazine-lists/wiki-need-titles.json"), "w", encoding="utf-8"), ensure_ascii=False)
