"""月次蒸留 試走: 種1蒸留(delta抽出)→型分類→管理表(holes)。種2はread-onlyのみ(凍結保証)。
出力: .cache/madb-distill/delta-<tag>.jsonl (種1蒸留) + manifest-<tag>.tsv (管理表)。種4登録はしない。"""
import sqlite3, ijson, json, re, unicodedata, sys, time, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
TAG = sys.argv[1] if len(sys.argv) > 1 else "1.2.17"
SRC = f"{ROOT}/.cache/madb-distill/metadata101.json"
DELTA = f"{ROOT}/.cache/madb-distill/delta-{TAG}.jsonl"
MANI = f"{ROOT}/.cache/madb-distill/manifest-{TAG}.tsv"

def norm(s):
    if not s: return ""
    s = unicodedata.normalize("NFKC", str(s))
    return re.sub(r"[\s・･,，\.\-—–:：;；!！?？'\"()（）\[\]【】]", "", s).strip().lower()
def base_title(t):  # 巻番号/副題を落とす
    t = re.sub(r"\s*[\.．]?\s*\d+\s*$", "", str(t or ""))
    t = re.split(r"[:：]", t)[0]
    return norm(t)
def first_str(v):  # schema:name/creator は [str, {@value,@language}] 形式
    if isinstance(v, list): v = v[0] if v else ""
    if isinstance(v, dict): v = v.get("@value", "")
    return str(v or "")
def kana_of(v):
    if isinstance(v, list):
        for x in v:
            if isinstance(x, dict) and "hrkt" in str(x.get("@language", "")): return x.get("@value", "")
    return ""

# ── 凍結ベースライン索引 (read-only) ──
con = sqlite3.connect(f"file:{ROOT}/.cache/db-v2.sqlite?mode=ro", uri=True)
con.text_factory = lambda b: b.decode("utf-8", "replace")
print("baseline索引構築中...", flush=True)
isbn_set = set(r[0] for r in con.execute("SELECT isbn13 FROM volumes WHERE isbn13 IS NOT NULL AND isbn13!=''"))
author_set = set(norm(r[0]) for r in con.execute("SELECT name FROM mangaka WHERE name IS NOT NULL"))
# work cluster: (著者norm, base題) -> 在
work_keys = set()
rows = con.execute("""SELECT s.title, m.name FROM series s
   JOIN series_authors sa ON sa.series_id=s.id JOIN mangaka m ON m.id=sa.mangaka_id""").fetchall()
for title, aname in rows:
    work_keys.add((norm(aname), base_title(title)))
con.close()
print(f"baseline: ISBN={len(isbn_set):,} author={len(author_set):,} work_keys={len(work_keys):,}", flush=True)

# ── 1.2.17 stream → delta抽出 + 型分類 + holes ──
import collections
by_type = collections.Counter(); by_year = collections.Counter(); adult_n = 0
hole_stats = collections.Counter()
fo = open(DELTA, "w", encoding="utf-8"); fm = open(MANI, "w", encoding="utf-8")
fm.write("madb_id\ttype\tyear\tisbn\ttitle\tauthor\tpublisher\tadult\thas_kana\thas_desc\tholes\n")
n_total = n_delta = 0; t0 = time.time()
f = open(SRC, "rb")
for r in ijson.items(f, "@graph.item"):
    n_total += 1
    if n_total % 50000 == 0:
        print(f"  scan {n_total:,} / delta {n_delta:,} ({time.time()-t0:.0f}s)", flush=True)
    isbn = re.sub(r"\D", "", str(r.get("schema:isbn", "")))
    if len(isbn) != 13: continue
    ndc = str(r.get("ma:ndc", "") or "")
    if ndc and not ndc.startswith("726"): continue  # 漫画NDCのみ(ndc無しはcm101既定で通す)
    if isbn in isbn_set: continue                      # 既取込=delta外
    n_delta += 1
    title = first_str(r.get("schema:name"))
    kana = kana_of(r.get("schema:name"))
    author = first_str(r.get("schema:creator"))
    publisher = str(r.get("schema:publisher", "") or "")
    date = str(r.get("schema:datePublished", "") or "")
    desc = r.get("schema:description", "")
    adult = "成年" in str(r.get("schema:contentRating", "")) or "成年" in str(desc)
    yr = (re.match(r"(\d{4})", date) or [None, "?"])[1]
    # 型分類
    an, bt = norm(author), base_title(title)
    if (an, bt) in work_keys: typ = "型1_新刊巻"
    elif an in author_set: typ = "型2_既作者新作"
    else: typ = "型3_新作者新作"
    # holes (型1は継承で穴少、型2/3は新規生成要)
    holes = []
    if typ != "型1_新刊巻":
        if not bt: holes.append("title")
        if not kana: holes.append("kana")
        holes.append("slug"); holes.append("genre/tag")  # 新規=生成要
    holes.append("cover")            # 全型=楽天harvest要
    if not desc: holes.append("synopsis")
    for h in holes: hole_stats[h] += 1
    by_type[typ] += 1; by_year[yr] += 1; adult_n += int(adult)
    rec = {"madb_id": r.get("@id", "").split("/")[-1], "isbn13": isbn, "title": title, "kana": kana,
           "author": author, "publisher": publisher, "date": date, "adult": adult,
           "type": typ, "ndc": ndc, "has_desc": bool(desc)}
    fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
    fm.write(f"{rec['madb_id']}\t{typ}\t{yr}\t{isbn}\t{title[:30]}\t{author[:16]}\t{publisher[:14]}\t{int(adult)}\t{int(bool(kana))}\t{int(bool(desc))}\t{','.join(holes)}\n")
f.close(); fo.close(); fm.close()
print(f"\n==== 種1蒸留 完了: 全{n_total:,}件scan / delta(新規){n_delta:,}件 ====", flush=True)
print("型別:", dict(by_type))
print("成年:", adult_n)
print("年別(上位):", dict(sorted(by_year.items(), key=lambda x: -x[1])[:8]))
print("管理表 holes:", dict(hole_stats))
print(f"出力: {DELTA} / {MANI}")
