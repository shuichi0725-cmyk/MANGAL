"""著者ヨミ(50音索引用)seed 生成 = MADB metadata504(作者master)公式ヨミ + カナ名。
name→カタカナ読み。 ground-truth(504のja-hrkt)。 残=B2(ma:ndla NDL典拠ID直引き)/AniList。
純粋追加で data/seeds/author-yomi.yml へ。
"""
import json, sys, re, sqlite3, yaml
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding="utf-8")
ROOT = "C:/Users/shuic/code/MANGAL"

# 504 作者master: name(漢字) → yomi(ja-hrkt) majority
g = json.load(open(ROOT + "/.cache/madb/metadata504.json", encoding="utf-8"))
rows = g.get("@graph", g) if isinstance(g, dict) else g
n2y = defaultdict(Counter)
for r in rows:
    nm = r.get("schema:name")
    if not isinstance(nm, list):
        nm = [nm] if nm else []
    kanji = [x for x in nm if isinstance(x, str)]
    yomi = [x.get("@value") for x in nm if isinstance(x, dict) and x.get("@language") == "ja-hrkt"]
    if kanji and yomi:
        n2y[kanji[0]][yomi[0]] += 1

# DB 実使用著者(series_authors に紐づく mangaka)
con = sqlite3.connect(ROOT + "/.cache/db-v2.sqlite")
used = {r[0] for r in con.execute("SELECT DISTINCT mangaka_id FROM series_authors")}
id2 = dict(con.execute("SELECT id,name FROM mangaka"))

def is_kana(s):
    return bool(re.fullmatch(r"[ぁ-んァ-ヶー゠・\s]+", s or ""))

seed = {}
for i in used:
    nm = id2.get(i)
    if not nm:
        continue
    if nm in n2y:
        seed[nm] = n2y[nm].most_common(1)[0][0]
    elif is_kana(nm):
        seed[nm] = re.sub(r"[\s・]", "", nm)  # カナ名はそのまま(カタカナ化はpromote)

# 既存 seed と merge(純粋追加・既存は保持)
import os
path = ROOT + "/data/seeds/author-yomi.yml"
old = {}
if os.path.exists(path):
    old = (yaml.safe_load(open(path, encoding="utf-8")) or {}).get("yomi", {})
add = 0
for k, v in seed.items():
    if k not in old:
        old[k] = v; add += 1
with open(path, "w", encoding="utf-8") as f:
    f.write("# 著者ヨミ(50音索引用)= MADB metadata504作者master公式ヨミ + カナ名。 name→カタカナ読み。\n")
    f.write("# 純粋追加。 残=B2(ma:ndla NDL典拠ID直引き)/AniList。 scripts/_gen-author-yomi.py\n")
    yaml.safe_dump({"yomi": old}, f, allow_unicode=True, sort_keys=True)
print("author-yomi.yml: %d著者 (新規追加 %d)" % (len(old), add))
