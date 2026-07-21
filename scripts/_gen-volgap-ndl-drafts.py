"""巻抜け作の欠番巻を NDL title検索で発見し seed4-drafts.yml を生成(→ _register-seed4-ndl.py が検証登録)。
NDL先(楽天でない)・出版社prefix制約で別作混入防止。 既存ISBN→db-v2 series_key で種4 bind。
使用: _gen-volgap-ndl-drafts.py [--limit N] [--offset M]"""
import sys, os, re, json, time, html, sqlite3, urllib.parse, urllib.request, yaml
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
DB = f"{ROOT}/.cache/db-v2.sqlite"
SRU = "https://ndlsearch.ndl.go.jp/api/sru"
LIMIT = int(sys.argv[sys.argv.index("--limit")+1]) if "--limit" in sys.argv else 40
OFFSET = int(sys.argv[sys.argv.index("--offset")+1]) if "--offset" in sys.argv else 0

def reg(ib):
    ib = re.sub(r"\D", "", str(ib or ""))
    if not ib.startswith("9784") or len(ib) != 13: return None
    b = ib[4:12]; n = int(b[:2])
    return b[:2] if n<=19 else b[:3] if n<=69 else b[:4] if n<=84 else b[:5] if n<=89 else b[:6] if n<=94 else b[:7]

con = sqlite3.connect(DB); cur = con.cursor()
def series_keys_for_isbns(isbns):
    s = set()
    for ib in isbns:
        for r in cur.execute("SELECT se.series_key FROM volumes v JOIN editions e ON e.id=v.edition_id JOIN series se ON se.id=e.series_id WHERE v.isbn13=?", (ib,)):
            s.add(r[0])
    return sorted(s)

rows = [l.rstrip("\n").split("\t") for l in open(f"{ROOT}/docs/production-diagnostics/vol_gap.tsv", encoding="utf-8")][1:]
slugs = [r[0] for r in rows][OFFSET:OFFSET+LIMIT]

def ndl_volumes(title):
    out = {}  # number -> (isbn, issued, pubprefix)
    start = 1
    for _ in range(6):
        q = {"operation":"searchRetrieve","query":f'title="{title}"',"recordSchema":"dcndl","maximumRecords":"100","startRecord":str(start)}
        req = urllib.request.Request(SRU+"?"+urllib.parse.urlencode(q)); req.add_header("User-Agent","Mozilla/5.0")
        try: xml = html.unescape(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
        except Exception: break
        recs = re.split(r"<recordData", xml)[1:]
        if not recs: break
        for r in recs:
            isbns = [re.sub(r"\D","",i) for i in re.findall(r"(97[89][\d\-]{9,16})", r)]
            isbns = [i for i in isbns if len(i)==13 and i.startswith("9784")]
            if not isbns: continue
            ib = isbns[0]
            mv = re.search(r"<dcndl:volume>.*?<rdf:value>([^<]+)</rdf:value>", r, re.S) or re.search(r"<dcndl:volume>\s*([^<]+?)\s*</dcndl:volume>", r)
            vol = None
            if mv:
                mn = re.search(r"\d+", mv.group(1)); vol = int(mn.group()) if mn else None
            if vol is None: continue
            iss = ""
            md = re.search(r"<dcterms:(?:issued|date)[^>]*>([^<]+)<", r) or re.search(r"<dc:date>([^<]+)<", r)
            if md:
                import unicodedata
                m2 = re.search(r"([0-9]{4})(?:[-.]([0-9]{1,2}))?", unicodedata.normalize("NFKC", md.group(1)))
                if m2: iss = m2.group(1) + (f"-{int(m2.group(2)):02d}" if m2.group(2) else "")
            if vol not in out: out[vol] = (ib, iss, reg(ib))
        if len(recs) < 100: break
        start += len(recs); time.sleep(1.2)
    return out

drafts = []
stats = {"works":0, "gaps":0, "found":0, "no_sk":0}
for sl in slugs:
    p = f"{ROOT}/data/manga.v2/{sl}.yml"
    if not os.path.exists(p): continue
    d = yaml.safe_load(open(p, encoding="utf-8"))
    stats["works"] += 1
    title = d["title"]
    isbns = [re.sub(r"\D","",str(v.get("isbn13") or "")) for e in d.get("editions",[]) for v in e.get("volumes",[]) if v.get("isbn13")]
    sk = series_keys_for_isbns(isbns)
    if not sk:
        stats["no_sk"] += 1; continue
    # 主prefix + 既存番号 + gap
    from collections import Counter
    pc = Counter(reg(i) for i in isbns if reg(i))
    mainpref = pc.most_common(1)[0][0] if pc else None
    nums = sorted({v.get("number") for e in d.get("editions",[]) for v in e.get("volumes",[]) if v.get("number")})
    if len(nums) < 2: continue
    gaps = [n for n in range(nums[0], nums[-1]+1) if n not in nums]
    if not gaps: continue
    stats["gaps"] += len(gaps)
    nv = ndl_volumes(title)
    for n in gaps:
        if n in nv:
            ib, iss, pref = nv[n]
            if mainpref and pref and pref != mainpref:  # 別出版社=別作の混入防止
                continue
            drafts.append({"series_keys": sk, "number": n, "isbn13": ib, "issued": iss,
                           "publisher": "", "title": title, "ndl_title": title})
            stats["found"] += 1

yaml.safe_dump(drafts, open(f"{ROOT}/.cache/seed4-drafts.yml", "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
print(f"batch[{OFFSET}:{OFFSET+LIMIT}] 作{stats['works']} / gap{stats['gaps']} / NDL発見{stats['found']} / series_key無{stats['no_sk']}")
print(f"→ .cache/seed4-drafts.yml ({len(drafts)}件)")
for dr in drafts[:15]: print(f"  {dr['title'][:22]:24} vol{dr['number']} isbn{dr['isbn13']} {dr['issued']}")
