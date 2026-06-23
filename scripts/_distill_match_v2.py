"""蒸留 統合マッチャ v2(慎重版): 種2(凍結・権威)照合で新刊の統合先を決め、管理表(台帳)に記入。
3点: ①既存題の最長一致 ②出版社ガード(別社選集の誤統合防止) ③vol≥2未マッチ→NDL vol1→種2 ISBN照合。
over-merge回避: 確証無ければ統合せず別扱い。種2 read-only。出力: .cache/madb-distill/ledger.tsv
usage: python _distill_match_v2.py [--ndl]  (--ndlでvol1照合実行、無で保留)"""
import sqlite3, re, unicodedata, csv, sys, json, urllib.request, urllib.parse, html, time, collections
ROOT = "C:/Users/shuic/code/MANGAL"
USE_NDL = "--ndl" in sys.argv
LEDGER = f"{ROOT}/.cache/madb-distill/ledger.tsv"

def norm(s):
    if not s: return ""
    s = unicodedata.normalize("NFKC", str(s))
    return re.sub(r"[\s・･,，\.\-—–:：;；!！?？'\"()（）\[\]【】/／=]", "", s).strip().lower()
def volnum(t):
    m = re.search(r"[\.．]\s*(\d+)\s*$", str(t or "")) or re.search(r"\s+第?(\d+)巻?\s*$", str(t or ""))
    return int(m.group(1)) if m else 1
def cand_prefixes(t):
    """新刊題の候補prefix(長→短): 巻番号除去→副題段階除去→base"""
    t = re.sub(r"[\.．]\s*\d+\s*$", "", str(t or "")); t = re.sub(r"\s+第?\d+巻?\s*$", "", t)
    t = re.sub(r"\s*=\s*[A-Za-z].*$", "", t)  # = 英題
    out = [t]
    parts = re.split(r"[:：]", t)
    for i in range(len(parts)-1, 0, -1): out.append("".join(parts[:i]))
    return [norm(x) for x in out if norm(x)]
def pref(i):
    i = re.sub(r"\D", "", str(i or ""))
    return i[:7] if len(i) >= 7 else (i or "?")

con = sqlite3.connect(f"file:{ROOT}/.cache/db-v2.sqlite?mode=ro", uri=True); con.text_factory = lambda b: b.decode("utf-8","replace")
print("種2索引構築中...", flush=True)
# norm題 → [(sid, raw, nvol, prefset)]  (最大巻を統合先に選ぶ)
sid_info = {}
for sid, t in con.execute("SELECT id,title FROM series WHERE title IS NOT NULL"):
    sid_info[sid] = {"title": t, "ntitle": norm(t), "prefs": set(), "nvol": 0}
for sid, isbn in con.execute("SELECT e.series_id, v.isbn13 FROM volumes v JOIN editions e ON e.id=v.edition_id WHERE v.isbn13 IS NOT NULL"):
    if sid in sid_info: sid_info[sid]["prefs"].add(pref(isbn)); sid_info[sid]["nvol"] += 1
title2sids = collections.defaultdict(list)
for sid, info in sid_info.items():
    if info["ntitle"]: title2sids[info["ntitle"]].append(sid)
isbn2sid = {re.sub(r"\D","",i): s for i, s in con.execute("SELECT isbn13, e.series_id FROM volumes v JOIN editions e ON e.id=v.edition_id WHERE isbn13 IS NOT NULL") if i}
print(f"種2: series {len(sid_info):,} / 題key {len(title2sids):,}", flush=True)

def best_sid(sids):  # 同題複数→最大巻
    return max(sids, key=lambda s: sid_info[s]["nvol"])
def match(title, gap_pref):
    """候補prefix(長→短)で種2題に最長一致。出版社ガードで別社選集を弾く。"""
    for cp in cand_prefixes(title):  # 長い順
        if cp in title2sids:
            sid = best_sid(title2sids[cp]); info = sid_info[sid]
            # 出版社ガード: gapのISBN社が統合先の社集合に在る(or統合先が単一巻=本体らしい)なら採用
            if gap_pref in info["prefs"] or info["nvol"] >= 5:
                return sid, info, "完全題一致" if cp == norm(re.sub(r"[\.．]\s*\d+\s*$","",title)) else f"最長一致"
            else:
                return None, None, f"題一致だが別社ガード"  # 別社選集の疑い→統合せず
    return None, None, "一致なし"

def ndl_vol1_isbn(base, author):
    """NDLで base題の vol1 ISBN を引く(著者で絞る)"""
    q = f'title="{base}"' + (f' AND creator="{author}"' if author else "")
    url = "https://ndlsearch.ndl.go.jp/api/sru?" + urllib.parse.urlencode({"operation":"searchRetrieve","query":q,"recordSchema":"dcndl","maximumRecords":"20"})
    try:
        x = html.unescape(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"}), timeout=20).read().decode("utf-8","replace"))
    except: return None
    best = None
    for rec in re.findall(r"<recordData>(.*?)</recordData>", x, re.S):
        t = re.search(r"<dcterms:title>([^<]+)", rec); ib = re.search(r'terms/ISBN">([0-9\-]+)', rec)
        if not ib: continue
        vn = volnum(t.group(1)) if t else 1
        if vn == 1: return re.sub(r"\D","",ib.group(1))
        if best is None: best = re.sub(r"\D","",ib.group(1))
    return best

rows = [r for r in csv.DictReader(open(f"{ROOT}/.cache/madb-distill/ndl-manifest.tsv", encoding="utf-8"), delimiter="\t") if r["scope"] == "in"]
gap = list(csv.DictReader(open(f"{ROOT}/data/seeds/ndl-2026-gap.tsv", encoding="utf-8"), delimiter="\t"))
isbn2cre = {r["isbn13"]: r["creators"] for r in gap}
cat = collections.Counter()
fo = open(LEDGER, "w", encoding="utf-8")
fo.write("isbn\tmonth\ttitle\tauthor\tpublisher\ttype\tintegrate_to\tmethod\tholes\tverified\n")
ndl_n = 0
for r in rows:
    isbn, title, pubn = r["isbn"], r["title"], r["publisher"]
    cre = isbn2cre.get(isbn, ""); a0 = re.sub(r",.*$", "", cre.split("/")[0]).strip() if cre else ""
    gp = pref(isbn); vn = volnum(title)
    sid, info, method = match(title, gp)
    verified = "-"
    if sid is None and vn >= 2 and USE_NDL:  # ③ vol≥2未マッチ→NDL vol1照合
        base = re.sub(r"\s*=.*$","", re.sub(r"[:：].*$","", re.sub(r"[\.．]\s*\d+\s*$","",title))).strip()
        v1 = ndl_vol1_isbn(base, a0); ndl_n += 1; time.sleep(0.3)
        if v1 and v1 in isbn2sid:
            sid = isbn2sid[v1]; info = sid_info.get(sid); method = "vol1-ISBN照合で発見"; verified = f"vol1={v1}"
        else:
            verified = f"vol1={'無' if not v1 else v1+'は種2外'}"
    if sid is not None:
        typ = "型1_統合"; dest = f"sid{sid}:{info['title'][:18]}({info['nvol']}巻)"
        holes = "cover,caption→genre/tag"
    else:
        typ = "型3_新規" if (a0 and norm(a0) not in {norm(x['title']) for x in []}) else "型2/3_新規"
        # 著者が種2に在れば型2、無ければ型3 (簡易)
        dest = "新規ページ"; holes = "slug,kana,genre/tag,cover,caption,synopsis"
    cat[f"{typ}|{method}"] += 1
    fo.write(f"{isbn}\t{r['month']}\t{title[:26]}\t{a0[:14]}\t{pubn[:12]}\t{typ}\t{dest}\t{method}\t{holes}\t{verified}\n")
fo.close()
print(f"\n台帳記入完了 → {LEDGER} (NDL照会 {ndl_n}件)\n=== 集計(type|method) ===")
for k, v in cat.most_common(): print(f"  {v:5} {k}")
