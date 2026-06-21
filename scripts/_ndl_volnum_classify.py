#!/usr/bin/env python3
"""
NDL厳格分類(READ-ONLY): volnum-mismatch-A群を著者strict NDL照合で分類。証拠表を出す。
著者一致した NDL 巻のみ採用 → 汎用題の別作ヒットを排除。番号是正は真の単巻が確証された時のみ候補化。
出力 data/seeds/ndl-volnum-classify-A.tsv。
使い方: python _ndl_volnum_classify.py [N=422] [offset=0]
"""
import sys, os, re, time, urllib.request, urllib.parse, unicodedata
import xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L
except ImportError: from yaml import SafeLoader as L
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NS = {"dcterms": "http://purl.org/dc/terms/", "dcndl": "http://ndl.go.jp/dcndl/terms/", "foaf": "http://xmlns.com/foaf/0.1/"}
RDFVAL = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}value"
CONT = re.compile(r"(シーズン|season|part|編$|篇$|第[二三四五六七八九]|II|III|2nd|3rd|続)")

def naz(s): return re.sub(r"[\s　・！!？\?（）\(\)【】「」〔〕〜~,，、。:：;；/／\.．’'\"＆&\-－]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()
def clean_au(a):
    a = re.sub(r"[\s　]*(さく|作|著|漫画|画|まんが|原作|脚本|構成|原案|story|art)$", "", str(a or "").strip())
    return naz(a)
def val(e):
    if e is None: return ""
    v = e.find(".//" + RDFVAL)
    return (v.text if v is not None and v.text else (e.text or "")).strip()

def sru(cql, n=50):
    q = urllib.parse.urlencode({"operation": "searchRetrieve", "recordSchema": "dcndl", "maximumRecords": str(n), "query": cql})
    time.sleep(0.8)
    return urllib.request.urlopen(urllib.request.Request("https://ndlsearch.ndl.go.jp/api/sru?" + q, headers={"User-Agent": "m/1.0"}), timeout=40).read().decode("utf-8")

def ndl_strict(title, pauthors):
    """著者一致した巻のみ {number: isbn} で返す。NDLエラーは None。"""
    try: root = ET.fromstring(sru(f'title="{title}"'))
    except Exception: return None
    base = naz(title)[:8]
    vols = {}
    for rd in root.iter("{http://www.loc.gov/zing/srw/}recordData"):
        try: rdf = ET.fromstring("".join(rd.itertext()))
        except: continue
        for res in rdf.iter("{http://ndl.go.jp/dcndl/terms/}BibResource"):
            t = val(res.find("dcterms:title", NS))
            if not t or base not in naz(t): continue
            # 著者一致 (creator / dc:creator / foaf)
            creators = [naz(val(c)) for c in res.findall("dcterms:creator", NS)]
            creators += [naz(c.text or "") for c in res.iter("{http://purl.org/dc/elements/1.1/}creator")]
            if pauthors and not any(pa and any(pa in c or c in pa for c in creators if c) for pa in pauthors):
                continue  # 著者不一致 = 別作として排除
            volraw = val(res.find("dcndl:volume", NS))
            m = re.search(r"(\d+)", volraw)
            num = int(m.group(1)) if m else (1 if not volraw else None)
            isbn = ""
            for idf in res.findall("dcterms:identifier", NS):
                if "ISBN" in idf.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}datatype", ""):
                    isbn = val(idf).replace("-", "")
            if num is not None and num <= 300: vols.setdefault(num, isbn)
    return vols

def main():
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 422
    off = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    rows = open(os.path.join(ROOT, "data", "seeds", "volnum-mismatch-A_single_ge2.tsv"), encoding="utf-8").read().splitlines()[1:]
    out = open(os.path.join(ROOT, "data", "seeds", "ndl-volnum-classify-A.tsv"), "a" if off else "w", encoding="utf-8")
    if not off: out.write("slug\ttitle\tdb_nums\tndl_nums\tclass\tfill_isbns\n")
    cnt = {"MISSING": 0, "TRUE_SINGLE": 0, "CONT": 0, "NDL_NONE": 0}
    todo = rows[off:off + N]
    for i, r in enumerate(todo):
        slug = r.split("\t")[0]
        fp = os.path.join(ROOT, "data", "manga.v2", slug + ".yml")
        if not os.path.exists(fp): continue
        try: d = yaml.load(open(fp, encoding="utf-8"), Loader=L)
        except: continue
        title = d.get("title")
        pau = [clean_au(a.get("name")) for a in (d.get("authors") or []) if a.get("name")]
        db = sorted(set(v.get("number") for e in d.get("editions", []) for v in e.get("volumes", []) if isinstance(v.get("number"), int)))
        nv = ndl_strict(title, pau)
        if nv is None:
            cls = "NDL_NONE"; nn = []
        else:
            nn = sorted(nv)
            if not nn: cls = "NDL_NONE"
            elif CONT.search(str(title)) or (nn and min(nn) > 1): cls = "CONT"
            elif len(nn) == 1 and nn == [1]: cls = "TRUE_SINGLE"
            elif len(nn) > 1 or 1 in nv: cls = "MISSING"
            else: cls = "CONT"
        cnt[cls] = cnt.get(cls, 0) + 1
        fill_isbns = ";".join(f"{k}:{nv[k]}" for k in (nn or []) if k not in db and nv.get(k)) if nv else ""
        out.write(f"{slug}\t{str(title)[:30]}\t{db}\t{nn[:12]}\t{cls}\t{fill_isbns}\n"); out.flush()
        if (i + 1) % 25 == 0: print(f"  ...{off+i+1} ({dict(cnt)})", flush=True)
    out.close()
    print(f"完了 [{off}-{off+len(todo)}]: {dict(cnt)}", flush=True)

if __name__ == "__main__":
    main()
