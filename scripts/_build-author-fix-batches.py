"""著者不一致(docs/author-mismatch-vs-rakuten.tsv)を高確度崩れに絞り、分散WF用バッチを作る。
高確度=現著者が[fragment/単字/会社/編集部/pub.年/(unknown)/全latin] かつ 楽天に綺麗な人物名。
低確度(表記揺れ/別版/共著の差)は対象外(触らない=慎重)。"""
import csv, re, json, os, unicodedata

ROOT = "C:/Users/shuic/code/MANGAL"
rows = list(csv.DictReader(open(f"{ROOT}/docs/author-mismatch-vs-rakuten.tsv", encoding="utf-8"), delimiter="\t"))

CORRUPT = re.compile(r"pub\.\s*(?:19|20)\d\d|株式会社|出版|編集部|Pictures|工房|Elements|ANYCOLOR|ネットワークス|企画室|^\(unknown\)$", re.I)

def is_fragment(name):
    n = name.strip()
    if not n:
        return True
    if n == "(unknown)":
        return True
    # 単字 or 全部latin小文字短い(ハンドル断片) or 数字始まり
    if len(re.sub(r"[\s　]", "", n)) <= 1:
        return True
    return False

def clean_person(rk):
    # 楽天著者が会社/編集部でなく、 1名以上の人物名
    if not rk:
        return False
    if re.search(r"株式会社|出版|編集部|Pictures|Ylab|Inc\b|アンソロジー", rk):
        return False
    return True

hi = []
for r in rows:
    cur = r["current_authors"]; rk = r["rakuten_author"]
    cur_names = [x for x in cur.split("|") if x]
    corrupt = bool(CORRUPT.search(cur)) or any(is_fragment(n) for n in cur_names) or (cur_names and all(re.fullmatch(r"[A-Za-z0-9\.\- ]+", n) for n in cur_names))
    if corrupt and clean_person(rk):
        hi.append({"slug": r["slug"], "current": cur, "rakuten_author": rk})

print(f"全不一致 {len(rows)} / 高確度崩れ(要回収) {len(hi)}")
os.makedirs(f"{ROOT}/.cache/authorfix-batches", exist_ok=True)
for f in os.listdir(f"{ROOT}/.cache/authorfix-batches"):
    os.remove(f"{ROOT}/.cache/authorfix-batches/{f}")
B = 40
for i in range(0, len(hi), B):
    json.dump(hi[i:i + B], open(f"{ROOT}/.cache/authorfix-batches/batch-{i//B:03d}.json", "w", encoding="utf-8"), ensure_ascii=False)
print(f"バッチ {(len(hi)+B-1)//B} 個 (40/batch)")
# サンプル
for h in hi[:12]:
    print(f"  {h['slug'][:26]:28} [{h['current'][:18]}] → 楽天[{h['rakuten_author'][:24]}]")
