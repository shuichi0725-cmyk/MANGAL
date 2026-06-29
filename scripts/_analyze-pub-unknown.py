"""出版社unknown作を切り分け: ①種2に社名あるがキー未登録(岩波型→キー追加で一括解決) ②種2にISBN→社名無し(NDL+楽天で確認) ③ISBN無し(難=skip)。
ISBN→社名=metadata101-clean.json(promote resolverと同源)。"""
import json, re, os, glob, unicodedata, collections, yaml

ROOT = "C:/Users/shuic/code/MANGAL"

def to13(s):
    s = re.sub(r"[^0-9X]", "", str(s or "").upper())
    if len(s) == 13: return s
    if len(s) == 10:
        c = "978" + s[:9]
        t = sum((1 if i % 2 == 0 else 3) * int(d) for i, d in enumerate(c))
        return c + str((10 - t % 10) % 10)
    return None

def norm(s):
    return re.sub(r"[\s　・,，\.。、:：;!！?？()（）株式会社有限\-]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()

# ISBN→社名
isbn2pub = {}
meta = f"{ROOT}/.cache/madb/metadata101-clean.json"
g = json.load(open(meta, encoding="utf-8"))
rows = g.get("@graph", g) if isinstance(g, dict) else g
for r in rows:
    p = r.get("schema:publisher") or r.get("publisher")
    if isinstance(p, list): p = p[0] if p else None
    if isinstance(p, dict): p = p.get("@value") or p.get("name")
    i = r.get("schema:isbn") or r.get("isbn")
    if isinstance(i, list): i = i[0] if i else None
    if not p or not i: continue
    k = to13(i)
    if k: isbn2pub[k] = p
print("ISBN→社名:", len(isbn2pub), flush=True)

# publishers.yml キー
pub = yaml.safe_load(open(f"{ROOT}/data/publishers.yml", encoding="utf-8")) or {}
keys = {norm(v["name"]) for v in pub.values()}
ali = f"{ROOT}/data/publisher-aliases.yml"
if os.path.exists(ali):
    for nm in (yaml.safe_load(open(ali, encoding="utf-8")) or {}):
        keys.add(norm(nm))

slugs = [l.rstrip("\n").split("\t")[0] for l in open(f"{ROOT}/docs/production-diagnostics/pub_unknown.tsv", encoding="utf-8")][1:]
unkeyed = collections.Counter()   # 種2社名あるがキー無し → 社名→作数
unkeyed_ex = {}
need_ndl = []      # 種2にISBN→社名無し(ISBN有り)
no_isbn = 0
for sl in slugs:
    p = f"{ROOT}/data/manga.v2/{sl}.yml"
    if not os.path.exists(p): continue
    try: d = yaml.safe_load(open(p, encoding="utf-8"))
    except: continue
    isbns = [to13(v.get("isbn13")) for e in d.get("editions", []) for v in e.get("volumes", []) if v.get("isbn13")]
    isbns = [i for i in isbns if i]
    if not isbns:
        no_isbn += 1; continue
    names = collections.Counter(isbn2pub[i] for i in isbns if i in isbn2pub)
    if names:
        nm = names.most_common(1)[0][0]
        if norm(nm) not in keys:
            unkeyed[nm] += 1
            unkeyed_ex.setdefault(nm, []).append(sl)
        # else: キー有るのにunknown=別要因(稀)
    else:
        need_ndl.append((sl, d.get("title", "")[:24], isbns[0]))

print(f"\n出版社unknown {len(slugs)} 切り分け:")
print(f"  ①種2に社名あるがキー未登録: {sum(unkeyed.values())}作 / {len(unkeyed)}社")
print(f"  ②種2にISBN→社名無し(NDL+楽天確認候補): {len(need_ndl)}作")
print(f"  ③ISBN無し(難=skip): {no_isbn}作")
print("\n=== ①未登録の主要出版社(作数順・キー追加候補) ===")
for nm, n in unkeyed.most_common(30):
    print(f"  {n:>4}作  {nm}")
json.dump({"unkeyed": dict(unkeyed), "unkeyed_ex": {k: v[:5] for k, v in unkeyed_ex.items()}, "need_ndl": need_ndl}, open(f"{ROOT}/.cache/pub-unknown-analysis.json", "w", encoding="utf-8"), ensure_ascii=False)
