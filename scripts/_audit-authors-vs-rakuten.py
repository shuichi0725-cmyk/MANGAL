"""本番manga.v2の著者を楽天harvest著者(ISBN→author)と突合し、不一致(corruption)を検出。
各作のvol1 ISBNで楽天著者を引き、現著者名と1つも重ならなければ mismatch(=要確認)。"""
import glob, os, re, json, unicodedata

ROOT = "C:/Users/shuic/code/MANGAL"
amap = json.load(open(f"{ROOT}/.cache/isbn-author-map.json", encoding="utf-8"))

def norm(s):
    return re.sub(r"[\s　・,，\.。、:：;/／\(\)（）]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()

# 現著者名(text抽出: name: 行) + vol1 ISBN(最初のisbn13)
NAME_RE = re.compile(r"^\s*-?\s*name:\s*(.+?)\s*$")
ISBN_RE = re.compile(r"isbn13:\s*'?(\d{13})'?")

mismatch = []
no_rk = same = 0
n = 0
for p in glob.glob(f"{ROOT}/data/manga.v2/*.yml"):
    n += 1
    try:
        txt = open(p, encoding="utf-8").read()
    except Exception:
        continue
    # authors セクションの name(先頭のauthorsブロック)
    head = txt[:1500]
    names = []
    in_auth = False
    for line in head.splitlines():
        if line.startswith("authors:"):
            in_auth = True; continue
        if in_auth:
            if re.match(r"^[a-z_]+:", line):  # 次のトップキー
                break
            m = re.search(r"name:\s*(.+?)\s*$", line)
            if m:
                names.append(m.group(1).strip().strip("'\""))
    ib = ISBN_RE.search(txt)
    if not ib:
        continue
    rk = amap.get(ib.group(1))
    if not rk:
        no_rk += 1; continue
    rk_norm = norm(rk)
    if any(norm(nm) and norm(nm) in rk_norm for nm in names):
        same += 1
    else:
        slug = os.path.basename(p)[:-4]
        mismatch.append((slug, "|".join(names)[:40], rk[:40]))

print(f"全{n} / 楽天著者一致{same} / 不一致{len(mismatch)} / 楽天無{no_rk}", flush=True)
import csv
with open(f"{ROOT}/docs/author-mismatch-vs-rakuten.tsv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t"); w.writerow(["slug", "current_authors", "rakuten_author"])
    for r in sorted(mismatch): w.writerow(r)
print("→ docs/author-mismatch-vs-rakuten.tsv", flush=True)
# 崩れ型の内訳
import collections
PUB = re.compile(r"pub\.\s*(?:19|20)\d\d", re.I)
CO = re.compile(r"株式会社|出版|編集部|Pictures|工房|Elements|ANYCOLOR")
c = collections.Counter()
for sl, cur, rk in mismatch:
    if PUB.search(cur): c["pub.年型"] += 1
    elif CO.search(cur): c["会社/編集部型"] += 1
    else: c["その他不一致"] += 1
print("不一致の型:", dict(c), flush=True)
