"""種2権威ISBN-dedup(慎重版): 共有ISBNを「種2所属series題と一致するページ」のみに残し、
他ページ(誤混入)から除去。種2は各ISBN=1series所属＝正解一意・判断不要・安全。
空になったページはexclude候補に。dry-run既定、--apply で manga.v2 書換(可逆backup)。
種2 read-only。"""
import sqlite3, os, re, json, collections, unicodedata, sys, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
APPLY = "--apply" in sys.argv

def norm(s):
    return re.sub(r"[\s　・･:：、。!！?？\-—–~〜\.]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()

con = sqlite3.connect(f"file:{ROOT}/.cache/db-v2.sqlite?mode=ro", uri=True); con.text_factory = lambda b: b.decode("utf-8","replace")
# ISBN → 種2 series 題(正本題)
isbn_title = {}
for isbn, title in con.execute("SELECT v.isbn13, s.title FROM volumes v JOIN editions e ON e.id=v.edition_id JOIN series s ON s.id=e.series_id WHERE v.isbn13 IS NOT NULL"):
    isbn_title[isbn] = title

# 共有ISBN → 関与ページ
rows = [l.rstrip("\n").split("\t") for l in open(f"{ROOT}/data/seeds/shared-isbn-audit.tsv", encoding="utf-8")][1:]
isbn_pages = {isbn: pages.split(",") for isbn, n, pages in rows}

# 関与ページの題(manga.v2から)
aff = set()
for ps in isbn_pages.values(): aff |= set(ps)
page_title = {}
for slug in aff:
    f = f"{ROOT}/data/manga.v2/{slug}.yml"
    if os.path.exists(f):
        for ln in open(f, encoding="utf-8"):
            if ln.startswith("title:"): page_title[slug] = ln.split(":",1)[1].strip(); break

# 各共有ISBNの正本ページ判定: 種2題と一致するページ
remove = collections.defaultdict(set)  # slug → 除去するISBN集合
unresolved = 0
for isbn, pages in isbn_pages.items():
    s2t = norm(isbn_title.get(isbn, ""))
    if not s2t: unresolved += 1; continue
    rightful = [p for p in pages if norm(page_title.get(p, "")) == s2t]
    # ★安全: 正本が「ちょうど1ページ」(別題で一意)の時だけdedup。
    #   0件=種2題が無題ページ等で保留 / 2件+=同題クラスタ(JOKER/日本の歴史)=ambiguous→保留(triage)。
    if len(rightful) != 1:
        unresolved += 1; continue
    keep = rightful[0]
    for p in pages:
        if p != keep: remove[p].add(isbn)

# ページ別: 除去後に空になるか
page_total = {}
for slug in aff:
    f = f"{ROOT}/data/manga.v2/{slug}.yml"
    if os.path.exists(f):
        page_total[slug] = len(re.findall(r"isbn13:\s*.?\d{13}", open(f, encoding="utf-8").read()))
emptied = [s for s in remove if page_total.get(s, 0) > 0 and len(remove[s]) >= page_total[s]]

print(f"共有ISBN {len(isbn_pages)} / 種2題で正本特定不可(保留): {unresolved}")
print(f"ISBN除去対象ページ: {len(remove)} / 除去ISBN延べ: {sum(len(v) for v in remove.values())}")
print(f"★除去で空になるページ(exclude候補): {len(emptied)}")
print()
print("=== 検証サンプル ===")
for isbn in ["9784063287011"]:  # placeholder
    pass
# zipang/jipang, 雨降り姫系 を確認
for slug in ["jipang", "zipang"]:
    if slug in remove or slug in aff:
        print(f"  {slug}(題={page_title.get(slug)}): 除去{len(remove.get(slug,set()))}/{page_total.get(slug,0)}巻" + (" →空exclude" if slug in emptied else ""))
print()
print("=== 空になるページ(exclude候補)サンプル ===")
for s in emptied[:12]:
    print(f"  {s} (題={page_title.get(s,'')[:18]}) 全{page_total.get(s,0)}巻除去")

json.dump({"remove": {k: sorted(v) for k, v in remove.items()}, "emptied": emptied}, open(f"{ROOT}/.cache/isbn-dedup-plan.json", "w", encoding="utf-8"), ensure_ascii=False)
print(f"\nplan保存: .cache/isbn-dedup-plan.json (apply={'YES' if APPLY else 'NO=dry-run'})")
