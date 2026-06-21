#!/usr/bin/env python3
"""
NDL巻数パイロット(READ-ONLY): volnum-mismatch-A群(単巻なのに番号≥2)をNDL照合。
NDLに全巻あるか/vol1あるか/真の単巻か を測り、歩留まり(補完 vs 番号是正 vs 続編)を出す。
使い方: python _ndl_volnum_pilot.py [N=20]
"""
import sys, os, re, time, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L
except ImportError: from yaml import SafeLoader as L
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NS = {"dcterms": "http://purl.org/dc/terms/", "dcndl": "http://ndl.go.jp/dcndl/terms/"}
RDFVAL = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}value"

def clean_author(a):
    a = re.sub(r"[\s　]*(さく|作|著|漫画|画|まんが|原作|脚本|構成)$", "", str(a or "").strip())
    return a.strip()
def val(e):
    if e is None: return ""
    v = e.find(".//" + RDFVAL)
    return (v.text if v is not None and v.text else (e.text or "")).strip()

def sru(cql, n=40):
    q = urllib.parse.urlencode({"operation": "searchRetrieve", "recordSchema": "dcndl",
                                "maximumRecords": str(n), "query": cql})
    time.sleep(0.8)
    return urllib.request.urlopen(urllib.request.Request(
        "https://ndlsearch.ndl.go.jp/api/sru?" + q, headers={"User-Agent": "m/1.0"}), timeout=40).read().decode("utf-8")

def ndl_volumes(title, author):
    cql = f'title="{title}"' + (f' AND creator="{author}"' if author else "")
    try: root = ET.fromstring(sru(cql))
    except Exception as e: return None
    vols = {}  # number -> isbn
    for rd in root.iter("{http://www.loc.gov/zing/srw/}recordData"):
        try: rdf = ET.fromstring("".join(rd.itertext()))
        except: continue
        for res in rdf.iter("{http://ndl.go.jp/dcndl/terms/}BibResource"):
            t = val(res.find("dcterms:title", NS))
            if not t or title[:6] not in t.replace(" ", ""): continue
            volraw = val(res.find("dcndl:volume", NS))
            m = re.search(r"(\d+)", volraw)
            num = int(m.group(1)) if m else (1 if not volraw else None)
            isbn = ""
            for idf in res.findall("dcterms:identifier", NS):
                if "ISBN" in idf.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}datatype", ""):
                    isbn = val(idf).replace("-", "")
            if num is not None: vols.setdefault(num, isbn)
    return vols

def main():
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    rows = open(os.path.join(ROOT, "data", "seeds", "volnum-mismatch-A_single_ge2.tsv"), encoding="utf-8").read().splitlines()[1:]
    fill = single = none = cont = 0
    for r in rows[:N]:
        slug = r.split("\t")[0]
        fp = os.path.join(ROOT, "data", "manga.v2", slug + ".yml")
        if not os.path.exists(fp): continue
        try: d = yaml.load(open(fp, encoding="utf-8"), Loader=L)
        except: continue
        title = d.get("title"); au = clean_author((d.get("authors") or [{}])[0].get("name"))
        cur = sorted(v.get("number") for e in d.get("editions", []) for v in e.get("volumes", []) if isinstance(v.get("number"), int))
        nv = ndl_volumes(title, au)
        if nv is None: print(f"  ? {title[:20]} NDLエラー"); none += 1; continue
        ndlnums = sorted(nv)
        if not ndlnums:
            print(f"  ✗ {title[:18]} (現{cur}) NDL=0件"); none += 1
        elif len(ndlnums) == 1 and ndlnums[0] == 1:
            print(f"  ① {title[:18]} (現{cur}) → NDLも単巻[1] = 番号是正(→1)"); single += 1
        elif 1 in nv or len(ndlnums) > 1:
            print(f"  ② {title[:18]} (現{cur}) → NDL複数巻{ndlnums[:8]} = 補完候補"); fill += 1
        else:
            print(f"  ③ {title[:18]} (現{cur}) → NDL{ndlnums[:5]}(vol1無) = 続編/要検証"); cont += 1
    print(f"\n歩留まり(計{N}): 補完候補②{fill} / 番号是正①{single} / 続編③{cont} / NDL無し{none}")

if __name__ == "__main__":
    main()
