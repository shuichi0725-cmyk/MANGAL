"""蒸留試走(NDL+楽天): NDL gap(種1蒸留)を種2(凍結)照合で型分類+scope+holes化。種2/種4不変。
出力: .cache/madb-distill/ndl-manifest.tsv (管理表)。種4登録はしない。"""
import csv, sqlite3, re, unicodedata, collections, sys
ROOT = "C:/Users/shuic/code/MANGAL"
GAP = f"{ROOT}/data/seeds/ndl-2026-gap.tsv"
OUT = f"{ROOT}/.cache/madb-distill/ndl-manifest.tsv"

def norm(s):
    if not s: return ""
    s = unicodedata.normalize("NFKC", str(s))
    return re.sub(r"[\s・･,，\.\-—–:：;；!！?？'\"()（）\[\]【】/／]", "", s).strip().lower()
def base_title(t):
    t = str(t or "")
    t = re.sub(r"\s*=\s*[A-Za-z].*$", "", t)          # = English題 を落とす
    t = re.sub(r"\s*[\.．]?\s*\d+\s*$", "", t)          # 巻番号
    t = re.split(r"[:：]", t)[0]
    return norm(t)
def authors_of(cre):  # "御雲, 推/ヨダカ, ケイ" -> [御雲推, ヨダカケイ]
    out = []
    for a in str(cre or "").split("/"):
        a = re.sub(r",\s*\d{4}-?.*$", "", a)            # 生年除去
        n = norm(a)
        if n: out.append((n, a.strip()))
    return out

# ── 凍結ベースライン(read-only) ──
con = sqlite3.connect(f"file:{ROOT}/.cache/db-v2.sqlite?mode=ro", uri=True)
con.text_factory = lambda b: b.decode("utf-8", "replace")
mangaka = set(norm(r[0]) for r in con.execute("SELECT name FROM mangaka WHERE name IS NOT NULL"))
adult_pub = set(r[0] for r in con.execute("SELECT name FROM adult_publishers"))
work_keys = set()
for title, aname in con.execute("""SELECT s.title, m.name FROM series s
   JOIN series_authors sa ON sa.series_id=s.id JOIN mangaka m ON m.id=sa.mangaka_id"""):
    work_keys.add((norm(aname), base_title(title)))
series_titles = set(base_title(r[0]) for r in con.execute("SELECT title FROM series WHERE title IS NOT NULL"))
con.close()

DROP_KW = ["アンソロジー","ガイド","ファンブック","設定資料","画集","原画集","読本","名鑑","大全","解体新書","攻略","公式コミック","傑作選","総集編","コミックガイド","カレンダー","名作選"]
rows = list(csv.DictReader(open(GAP, encoding="utf-8"), delimiter="\t"))
cat = collections.Counter(); hole_field = collections.Counter()
fo = open(OUT, "w", encoding="utf-8")
fo.write("isbn\tmonth\ttype\tscope\tisbn\ttitle\tauthor\tpublisher\tholes\n")
typ_examples = collections.defaultdict(list)
for r in rows:
    isbn, date, pub, title, cre = r["isbn13"], r["date"], r["publisher"], r["title"], r["creators"]
    mo = (re.match(r"2026[.\-/]?(\d{1,2})", date) or [None, "?"])[1]
    auths = authors_of(cre)
    bt = base_title(title)
    # scope判定
    is_drop = any(k in title for k in DROP_KW)
    is_foreign = bool(re.search(r"=\s*[A-Za-z]", title)) or any(re.search(r"[A-Za-z]{4,}", a[1]) for a in auths)
    is_adult = any(p in pub for p in adult_pub) or pub in ("秋水社","彗星社","プランタン出版","キルタイムコミュニケーション","ワニマガジン社")
    scope = "drop" if is_drop else ("foreign" if is_foreign else ("adult" if is_adult else "in"))
    # 型分類
    if any((an, bt) in work_keys for an, _ in auths) or bt in series_titles:
        typ = "型1_新刊巻"
    elif any(an in mangaka for an, _ in auths):
        typ = "型2_既作者新作"
    else:
        typ = "型3_新作者新作"
    # holes(型1=継承で少, 型2/3=生成要)
    holes = ["cover", "caption→genre/tag/synopsis"]   # 全型: 楽天harvest要
    if typ != "型1_新刊巻":
        holes = ["slug", "kana確認", "genre/tag", "cover", "caption", "synopsis"]
        if typ == "型3_新作者新作": holes.append("著者master登録(NDL読み+QID)")
    for h in holes: hole_field[h] += 1
    key = f"{typ}|{scope}"; cat[key] += 1
    if len(typ_examples[key]) < 4:
        typ_examples[key].append(f"{title[:26]} / {auths[0][1] if auths else '-'} / {pub[:10]}")
    fo.write(f"{isbn}\t2026-{mo}\t{typ}\t{scope}\t{isbn}\t{title[:28]}\t{(auths[0][1] if auths else '')[:14]}\t{pub[:12]}\t{','.join(holes)}\n")
fo.close()
print(f"NDL gap {len(rows)}件 分類完了 → {OUT}\n")
print("=== 型 × scope ===")
for k, v in cat.most_common():
    print(f"  {v:5} {k}")
print("\n=== scope集計 ===")
sc = collections.Counter()
for k, v in cat.items(): sc[k.split("|")[1]] += v
for s, v in sc.most_common(): print(f"  {v:5} {s}")
print("\n=== 管理表 holes(在庫=要埋め) ===")
for h, v in hole_field.most_common(): print(f"  {v:5} {h}")
print("\n=== 型1新刊巻(in scope) サンプル ===")
for ex in typ_examples.get("型1_新刊巻|in", [])[:4]: print("  ", ex)
print("=== 型2/型3(in scope) サンプル ===")
for k in ["型2_既作者新作|in", "型3_新作者新作|in"]:
    for ex in typ_examples.get(k, [])[:3]: print(f"  [{k.split('|')[0]}] {ex}")
