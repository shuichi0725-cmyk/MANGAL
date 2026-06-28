"""過剰統合検出: 1つの作品(標準版)の巻ISBNに複数の出版社prefixが混在=別シリーズ混入の疑い。
ISBN-13 978-4-{registrant} の registrant(出版社記号)を範囲規則で抽出し、 1作で複数なら flag。
少数派prefix巻=intruder候補。 確証は別途(WF/手動)。 [[fragmentation_overmerge_cleanup]]"""
import glob, os, re, json, collections

ROOT = "C:/Users/shuic/code/MANGAL"

def registrant(isbn):
    # 978-4-{registrant}. 日本ISBNの registrant 範囲で桁数決定(標準ISBN-13規則)
    if not isbn.startswith("9784") or len(isbn) != 13:
        return None
    body = isbn[4:12]  # registrant+publication(8桁)
    n2 = int(body[:2])
    if n2 <= 19:
        return body[:2]
    if n2 <= 69:
        return body[:3]
    if n2 <= 84:
        return body[:4]
    if n2 <= 89:
        return body[:5]
    if n2 <= 94:
        return body[:6]
    return body[:7]

ISBN_RE = re.compile(r"isbn13:\s*'?(\d{13})'?")
flags = []
n = 0
for p in glob.glob(f"{ROOT}/data/manga.v2/*.yml"):
    n += 1
    try:
        txt = open(p, encoding="utf-8").read()
    except Exception:
        continue
    # 標準版巻の (number, isbn, date) を粗抽出: yaml読まず軽量に全ISBN取得 → registrant集計
    isbns = ISBN_RE.findall(txt)
    if len(isbns) < 3:
        continue
    regs = collections.Counter(r for r in (registrant(i) for i in isbns) if r)
    if len(regs) <= 1:
        continue
    # 少数派(intruder候補)= 最多以外。 最多が全体の過半 かつ 少数派が小さい時に強い signal
    top, topn = regs.most_common(1)[0]
    minority = {r: c for r, c in regs.items() if r != top}
    total = sum(regs.values())
    if topn / total < 0.5:
        continue  # 主prefixが過半でない=版違い/共著等の可能性 → 弱いのでskip(誤検出回避)
    title = ""
    m = re.search(r"^title:\s*(.+)$", txt, re.M)
    if m:
        title = m.group(1).strip().strip("'\"")
    slug = os.path.basename(p)[:-4]
    flags.append({"slug": slug, "title": title, "top": top, "topn": topn,
                  "minority": minority, "total": total})

print(f"全{n} / prefix混在(主prefix過半)作 {len(flags)}", flush=True)
flags.sort(key=lambda x: (-sum(x["minority"].values()), x["title"]))
json.dump(flags, open(f"{ROOT}/.cache/overmerge-prefix-flags.json", "w", encoding="utf-8"), ensure_ascii=False)
import csv
with open(f"{ROOT}/docs/overmerge-prefix-candidates.tsv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t"); w.writerow(["slug", "title", "top_prefix", "top_n", "minority", "total"])
    for x in flags:
        w.writerow([x["slug"], x["title"], x["top"], x["topn"], json.dumps(x["minority"], ensure_ascii=False), x["total"]])
print("→ docs/overmerge-prefix-candidates.tsv", flush=True)
print("=== 少数派が小さい(intruder強疑い) top20 ===", flush=True)
for x in flags[:20]:
    mn = sum(x["minority"].values())
    print(f"  {x['title'][:26]:28} 主{x['top']}×{x['topn']} / 混入{x['minority']} (計{x['total']})")
