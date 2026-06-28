"""本番manga.v2から「会社/編集部が著者」の作を抽出し、分散WF用バッチを作る。
各作: slug/title/current_authors/rakuten_author/caption。 WFが drop(非漫画)/fix(著者是正)/keep を判定。"""
import glob, os, re, json, gzip

ROOT = "C:/Users/shuic/code/MANGAL"
amap = json.load(open(f"{ROOT}/.cache/isbn-author-map.json", encoding="utf-8"))
# caption seed
cap = {}
for line in gzip.open(f"{ROOT}/data/seeds/rakuten-captions.jsonl.gz", "rt", encoding="utf-8"):
    try:
        o = json.loads(line)
    except Exception:
        continue
    ib = re.sub(r"\D", "", str(o.get("isbn") or o.get("isbn13") or ""))
    c = o.get("caption") or o.get("itemCaption") or ""
    if ib and c:
        cap[ib] = c

CO = re.compile(r"株式会社|出版|編集部|Pictures|工房|Elements|ANYCOLOR|企画室|ネットワークス|Cygames|出版部|出版局|書籍編集")
ISBN_RE = re.compile(r"isbn13:\s*'?(\d{13})'?")

works = []
n = 0
for p in glob.glob(f"{ROOT}/data/manga.v2/*.yml"):
    n += 1
    try:
        txt = open(p, encoding="utf-8").read()
    except Exception:
        continue
    head = txt[:1500]
    names, in_auth = [], False
    title = ""
    for line in head.splitlines():
        if line.startswith("title:") and not title:
            title = line.split(":", 1)[1].strip().strip("'\"")
        if line.startswith("authors:"):
            in_auth = True; continue
        if in_auth:
            if re.match(r"^[a-z_]+:", line):
                break
            m = re.search(r"name:\s*(.+?)\s*$", line)
            if m:
                names.append(m.group(1).strip().strip("'\""))
    if not any(CO.search(nm) for nm in names):
        continue
    ib = ISBN_RE.search(txt)
    ibn = ib.group(1) if ib else ""
    slug = os.path.basename(p)[:-4]
    works.append({"slug": slug, "title": title, "current": "|".join(names),
                  "rakuten_author": amap.get(ibn, ""), "caption": cap.get(ibn, "")[:80]})

print(f"全{n} / 会社著者作 {len(works)}")
os.makedirs(f"{ROOT}/.cache/company-batches", exist_ok=True)
for f in os.listdir(f"{ROOT}/.cache/company-batches"):
    os.remove(f"{ROOT}/.cache/company-batches/{f}")
B = 40
for i in range(0, len(works), B):
    json.dump(works[i:i + B], open(f"{ROOT}/.cache/company-batches/batch-{i//B:03d}.json", "w", encoding="utf-8"), ensure_ascii=False)
print(f"バッチ {(len(works)+B-1)//B} 個")
for w in works[:10]:
    print(f"  {w['slug'][:24]:26} [{w['current'][:20]}] 楽天[{w['rakuten_author'][:18]}]")
