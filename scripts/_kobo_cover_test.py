#!/usr/bin/env python3
"""
Kobo電子書影テスト: 書影欠けの作品を題+著者+巻番号で厳格照合し、Koboのlargeimageで埋まるか測定。
READ-ONLY(適用なし)。歩留まり=ヒット率と、照合した Kobo題を出して精度確認。
使い方: python _kobo_cover_test.py [作品数=15]
"""
import sys, os, json, re, time, glob, unicodedata, urllib.request, urllib.parse, random
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L
except ImportError: from yaml import SafeLoader as L
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env = {}
for ln in open(os.path.join(ROOT, ".env.local"), encoding="utf-8"):
    if "=" in ln and not ln.strip().startswith("#"):
        k, v = ln.split("=", 1); env[k.strip()] = v.strip()
from urllib.parse import urlparse
RREF = env["RAKUTEN_REFERER"]; _o = urlparse(RREF); RORG = f"{_o.scheme}://{_o.netloc}"

def to13(s):
    s = str(s or "").replace("-", "").strip(); return s if len(s) == 13 and s.isdigit() else ""
def naz(s): return re.sub(r"[\s　・！!？\?（）\(\)【】「」〔〕〜~,，、。:：;；/／\.．’'\"＆&\-]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()
def nau(s): return re.sub(r"[\s　・（）\(\)\[\]]", "", unicodedata.normalize("NFKC", str(s or "")))
def volnum(rt):
    t = unicodedata.normalize("NFKC", rt)
    m = re.search(r"[（(]\s*(\d+)\s*[）)]\s*$", t) or re.search(r"第\s*(\d+)\s*巻", t) or re.search(r"[　 ](\d+)\s*$", t)
    if m: return int(m.group(1)), naz(t[:m.start()])
    return None, naz(t)

def kobo(title, pg=1):
    time.sleep(1.0)
    p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"], "format": "json",
         "formatVersion": "2", "title": title, "hits": 30, "page": pg}
    u = "https://openapi.rakuten.co.jp/services/api/Kobo/EbookSearch/20170426?" + urllib.parse.urlencode(p)
    try:
        return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"Referer": RREF, "Origin": RORG, "User-Agent": "M/0.1", "Accept": "application/json"}), timeout=30).read())
    except Exception as e:
        return {"err": str(e)}

N = int(sys.argv[1]) if len(sys.argv) > 1 else 15
# 書影欠けの作品を探す(標準版で >=3巻 かつ null率>=40% かつ ISBN有)
files = glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml"))
random.seed(7); random.shuffle(files)
targets = []
for fp in files:
    try: d = yaml.load(open(fp, encoding="utf-8"), Loader=L)
    except: continue
    if not isinstance(d, dict): continue
    eds = d.get("editions") or []
    if not eds: continue
    e = max(eds, key=lambda x: len(x.get("volumes") or []))
    vols = e.get("volumes") or []
    if len(vols) < 3: continue
    miss = [v for v in vols if not v.get("cover_url")]
    if len(miss) < max(2, len(vols) * 0.4): continue
    targets.append((d, [v.get("number") for v in miss if isinstance(v.get("number"), int)]))
    if len(targets) >= N: break

print(f"テスト対象 {len(targets)}作（書影欠け）\n")
tot_miss = tot_hit = 0
for d, missnums in targets:
    title = d.get("title"); base = naz(title)
    pau = set(nau(a.get("name")) for a in (d.get("authors") or []) if a.get("name"))
    found = {}
    try:
        for pg in (1, 2):
            r = kobo(title, pg)
            if r.get("err"): print(f"  ERR {title}: {r['err']}"); break
            its = r.get("Items", [])
            if not its: break
            for it in its:
                n, rest = volnum(it.get("title", ""))
                if rest != base: continue
                ra = nau(it.get("author", ""))
                if pau and not any(pa and pa in ra for pa in pau): continue
                if n is None: n = 1
                img = it.get("largeImageUrl") or it.get("mediumImageUrl") or ""
                if n in missnums and "noimage" not in img and img:
                    found.setdefault(n, (img, it.get("title", "")))
            if r.get("count", 0) <= pg * 30: break
    except Exception as ex:
        print(f"  ERR {title}: {ex}"); continue
    tot_miss += len(missnums); tot_hit += len(found)
    sample = next(iter(found.items()), None)
    smp = f' 例: vol{sample[0]}←Kobo「{sample[1][1][:26]}」' if sample else ''
    print(f"  [{title[:26]}] 著{list(pau)[:1]} 欠け{len(missnums)}巻 → Kobo充当 {len(found)}巻{smp}")

print(f"\n★歩留まり: 欠け{tot_miss}巻中 Kobo充当可 {tot_hit}巻 ({100*tot_hit//max(tot_miss,1)}%)")
