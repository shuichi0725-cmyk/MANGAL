#!/usr/bin/env python3
"""
B群(offset)/C群(gap) 厳格調査(READ-ONLY): NDL著者strict + 種2各版 + collection信号で分類。
 FILL(NDLにDB欠け巻有・ISBN付=補完可) / S2_HAS(種2に欠け巻有=分裂/lost要merge) /
 COLLECTION(傑作集等) / CONT(続編/NDLも同欠け) / NDL_NONE。
使い方: python _ndl_classify_bc.py <B|C> [N] [offset]
"""
import sys, os, re, time, json, unicodedata, urllib.request, urllib.parse, sqlite3
import xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L
except ImportError: from yaml import SafeLoader as L
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NS = {"dcterms": "http://purl.org/dc/terms/", "dcndl": "http://ndl.go.jp/dcndl/terms/"}
RDFVAL = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}value"
CONT = re.compile(r"(シーズン|season|part|編$|篇$|第[二三四五六七八九]部|II|III|2nd|3rd|続)")
COLL = re.compile(r"(傑作集|傑作選|作品集|選集|短編集|短篇集|名作選|名作集|自選|コレクション|大全集|全集|COLLECTION)", re.I)

def to13(s):
    s = str(s or "").replace("-", "").strip(); return s if len(s) == 13 and s.isdigit() else ""
def naz(s): return re.sub(r"[\s　・！!？\?（）\(\)【】「」〔〕〜~,，、。:：;；/／\.．’'\"＆&\-－]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()
def clean_au(a): return naz(re.sub(r"[\s　]*(さく|作|著|漫画|画|まんが|原作|脚本|構成|原案|story|art)$", "", str(a or "").strip()))
def val(e):
    if e is None: return ""
    v = e.find(".//" + RDFVAL)
    return (v.text if v is not None and v.text else (e.text or "")).strip()
def sru(cql, n=50):
    q = urllib.parse.urlencode({"operation": "searchRetrieve", "recordSchema": "dcndl", "maximumRecords": str(n), "query": cql})
    time.sleep(0.8)
    return urllib.request.urlopen(urllib.request.Request("https://ndlsearch.ndl.go.jp/api/sru?" + q, headers={"User-Agent": "m/1.0"}), timeout=40).read().decode("utf-8")
def ndl_strict(title, pau):
    try: root = ET.fromstring(sru(f'title="{title}"'))
    except Exception: return None
    base = naz(title)[:8]; vols = {}
    for rd in root.iter("{http://www.loc.gov/zing/srw/}recordData"):
        try: rdf = ET.fromstring("".join(rd.itertext()))
        except: continue
        for res in rdf.iter("{http://ndl.go.jp/dcndl/terms/}BibResource"):
            t = val(res.find("dcterms:title", NS))
            if not t or base not in naz(t): continue
            cr = [naz(val(c)) for c in res.findall("dcterms:creator", NS)] + [naz(c.text or "") for c in res.iter("{http://purl.org/dc/elements/1.1/}creator")]
            if pau and not any(pa and any(pa in c or c in pa for c in cr if c) for pa in pau): continue
            m = re.search(r"(\d+)", val(res.find("dcndl:volume", NS)))
            num = int(m.group(1)) if m else (1 if not val(res.find("dcndl:volume", NS)) else None)
            isbn = ""
            for idf in res.findall("dcterms:identifier", NS):
                if "ISBN" in idf.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}datatype", ""): isbn = val(idf).replace("-", "")
            if num is not None and num <= 300: vols.setdefault(num, isbn)
    return vols

con = sqlite3.connect(os.path.join(ROOT, ".cache", "db-v2.sqlite"))
print("楽天題map...", flush=True); RT = {}
for line in open(os.path.join(ROOT, ".cache", "rakuten-isbn.jsonl"), encoding="utf-8"):
    try: o = json.loads(line)
    except: continue
    it = o.get("item") or {}; ib = to13(o.get("isbn") or it.get("isbn"))
    if ib: RT[ib] = it.get("title", "")
print(f"  {len(RT)}", flush=True)

def s2_info(slug):
    st = os.path.join(ROOT, "data", "manga", slug + ".yml")
    if not os.path.exists(st): return set(), ""
    m = re.search(r"_skey:\s*(.+)", open(st, encoding="utf-8").read())
    if not m: return set(), ""
    sids = [r[0] for r in con.execute("SELECT id FROM series WHERE series_key=?", (m.group(1).strip(),)).fetchall()]
    nums = set(); coll = ""
    for sid in sids:
        for (ib,) in con.execute("SELECT v.isbn13 FROM volumes v JOIN editions e ON v.edition_id=e.id WHERE e.series_id=?", (sid,)).fetchall():
            n = con.execute("SELECT number FROM volumes WHERE isbn13=?", (ib,)).fetchone()
            if n and isinstance(n[0], int): nums.add(n[0])
            rt = RT.get(to13(ib), "")
            if rt and COLL.search(rt): coll = rt
    return nums, coll

grp = sys.argv[1] if len(sys.argv) > 1 else "B"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 10**9
off = int(sys.argv[3]) if len(sys.argv) > 3 else 0
fn = {"B": "volnum-mismatch-B_offset.tsv", "C": "volnum-mismatch-C_gap.tsv"}[grp]
rows = open(os.path.join(ROOT, "data", "seeds", fn), encoding="utf-8").read().splitlines()[1:]
out = open(os.path.join(ROOT, "data", "seeds", f"ndl-classify-{grp}.tsv"), "a" if off else "w", encoding="utf-8")
if not off: out.write("slug\ttitle\tdb\tndl\ts2\tfill_isbns\tclass\n")
cnt = {}
for i, r in enumerate(rows[off:off + N]):
    slug = r.split("\t")[0]
    fp = os.path.join(ROOT, "data", "manga.v2", slug + ".yml")
    if not os.path.exists(fp): continue
    try: d = yaml.load(open(fp, encoding="utf-8"), Loader=L)
    except: continue
    title = d.get("title"); pau = [clean_au(a.get("name")) for a in (d.get("authors") or []) if a.get("name")]
    db = sorted(set(v.get("number") for e in d.get("editions", []) for v in e.get("volumes", []) if isinstance(v.get("number"), int)))
    if not db: continue
    full = list(range(1, db[-1] + 1)); miss = [x for x in full if x not in db]  # 欠け(内部+低)
    nv = ndl_strict(title, pau); s2n, coll = s2_info(slug)
    if nv is None: cls = "NDL_NONE"; nn = []; filli = ""
    else:
        nn = sorted(nv)
        fill = {x: nv[x] for x in miss if x in nv and nv[x]}  # NDLが持つ欠け巻(ISBN付)
        filli = ";".join(f"{k}:{v}" for k, v in sorted(fill.items()))
        if coll: cls = "COLLECTION"
        elif fill: cls = "FILL"
        elif any(x in s2n for x in miss): cls = "S2_HAS"
        elif CONT.search(str(title)) or (nn and min(nn) > 1): cls = "CONT"
        elif not nn: cls = "NDL_NONE"
        else: cls = "CONT"
    cnt[cls] = cnt.get(cls, 0) + 1
    out.write(f"{slug}\t{str(title)[:26]}\t{db}\t{nn[:10]}\t{sorted(s2n)[:10]}\t{filli}\t{cls}\n"); out.flush()
    if (i + 1) % 25 == 0: print(f"  {grp} ...{off+i+1} {dict(cnt)}", flush=True)
out.close()
print(f"完了 {grp} [{off}-{off+min(N,len(rows)-off)}]: {dict(cnt)}", flush=True)
