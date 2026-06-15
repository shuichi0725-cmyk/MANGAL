"""[調査only] NDL版違いを"全件"取得(SRU 500件上限を日付分割で回避)。
各版keyword×日付バケットで<500に割り、和集合→本編単位dedup→db-v2突合→TSV。
NDLのみ・登録/本番変更なし。出力 .cache/ndl-editions-full.tsv
"""
import urllib.parse, urllib.request, time, re, sys, sqlite3, unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
EP = "https://ndlsearch.ndl.go.jp/api/sru"
OUT = ROOT / ".cache" / "ndl-editions-full.tsv"

EDITIONS = [("完全版", "kanzenban"), ("新装版", "shinsoban"), ("愛蔵版", "aizoban"),
            ("ワイド版", "wideban"), ("復刻版", None), ("フルカラー", None),
            ("カラー版", None), ("オールカラー", None), ("新装再編版", None)]
DROP_WORDS = ["総集編", "ガイド", "公式", "大全集", "画集", "原画集", "設定資料", "ファンブック", "資料集"]
DECADES = [(1900, 1979), (1980, 1989), (1990, 1994), (1995, 1999), (2000, 2004),
           (2005, 2009), (2010, 2014), (2015, 2019), (2020, 2026)]


def lnm(t): return t.split("}")[-1]


def norm(t):
    t = t or ""
    t = re.sub(r"[〔\[(（【].*?[〕\])）】]", "", t)
    for w in ["完全版", "新装版", "愛蔵版", "文庫版", "ワイド版", "フルカラー", "カラー版", "オールカラー", "復刻版", "新装再編版", "新装"]:
        t = t.replace(w, "")
    t = unicodedata.normalize("NFKC", t)
    t = re.sub(r"\s+", "", t).lower()
    t = re.sub(r"[ぁ-ん]", lambda m: chr(ord(m.group()) + 0x60), t)
    t = re.sub(r"[^0-9a-zヲ-ヴー一-龯]", "", t)
    return t


def base_title(full):
    b = full.split(" : ")[0].strip()
    b = re.sub(r"[.　\s]*(?:第?\d+|上巻|下巻|上|下|別巻|前編|後編)\s*$", "", b).strip()
    return b


def req(params):
    url = EP + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "MANGAL/0.1", "Accept": "application/xml"}), timeout=40).read()
        except Exception:
            if attempt < 3:
                time.sleep(4 + attempt * 4); continue
            raise


def cql(name, yr=None):
    q = f"title={name} AND ndc=726"
    if yr:
        q += f" AND from={yr[0]} AND until={yr[1]}"
    return q


def count(name, yr=None):
    b = req({"operation": "searchRetrieve", "recordSchema": "dcndl", "recordPacking": "xml",
             "maximumRecords": "1", "query": cql(name, yr)})
    for el in ET.fromstring(b).iter():
        if lnm(el.tag) == "numberOfRecords":
            return int(el.text or "0")
    return 0


def fetch_window(name, yr=None):
    b = req({"operation": "searchRetrieve", "recordSchema": "dcndl", "recordPacking": "xml",
             "maximumRecords": "500", "query": cql(name, yr)})
    out = []
    for rd in ET.fromstring(b).iter():
        if lnm(rd.tag) != "recordData":
            continue
        kids = list(rd)
        it = rd.iter() if kids else (ET.fromstring(rd.text).iter() if rd.text and "<" in rd.text else [])
        f = {}; isbn = None
        for el in it:
            k = lnm(el.tag); t = (el.text or "").strip()
            if not t:
                continue
            if k in ("title", "seriesTitle", "creator") and k not in f:
                f[k] = t
            if k == "identifier" and not isbn:
                m = re.search(r"97[89]\d{10}", t.replace("-", ""))
                if m:
                    isbn = m.group()
        if isbn:
            f["isbn"] = isbn
        if f.get("title") or f.get("seriesTitle"):
            out.append(f)
    return out


# DB
con = sqlite3.connect(str(ROOT / ".cache" / "db-v2.sqlite"))
allt = set(); type_titles = defaultdict(set)
for title, etype in con.execute("select s.title, e.type from series s join editions e on e.series_id=s.id"):
    n = norm(title); allt.add(n)
    if etype:
        type_titles[etype].add(n)

works = {}
seen_rec = set()
coverage = {}


def absorb(recs, name, typ):
    for f in recs:
        full = f.get("title") or f.get("seriesTitle") or ""
        rk = f.get("isbn") or full
        if rk in seen_rec:
            continue
        seen_rec.add(rk)
        if any(w in full for w in DROP_WORDS):
            continue
        bn = norm(base_title(f.get("seriesTitle") or full))
        if not bn:
            continue
        w = works.setdefault((bn, name), {"edition": name, "base": base_title(f.get("seriesTitle") or full),
                                          "creator": f.get("creator", ""), "isbn": f.get("isbn", ""), "n": 0, "type": typ})
        w["n"] += 1
        if not w["isbn"] and f.get("isbn"):
            w["isbn"] = f["isbn"]


for name, typ in EDITIONS:
    tot = count(name); time.sleep(1.0)
    fetched = 0
    absorb(fetch_window(name), name, typ)  # base 500(未日付/順序先頭の捕捉)
    fetched += 1
    for (a, b) in DECADES:
        c = count(name, (a, b)); time.sleep(1.0)
        if c == 0:
            continue
        if c <= 500:
            absorb(fetch_window(name, (a, b)), name, typ); fetched += 1; time.sleep(1.0)
        else:
            for y in range(a, b + 1):
                cy = count(name, (y, y)); time.sleep(0.8)
                if cy == 0:
                    continue
                absorb(fetch_window(name, (y, y)), name, typ); fetched += 1; time.sleep(0.9)
    coverage[name] = (tot, fetched)
    nwk = sum(1 for k in works if k[1] == name)
    print(f"[{name}] numberOfRecords={tot} fetch呼数{fetched} 重複除去作品{nwk}", flush=True)

# 分類・出力
rows = []
for (bn, name), w in works.items():
    typ = w["type"]
    if typ and bn in type_titles.get(typ, set()):
        st = "already"
    elif bn in allt:
        st = "have_no_edition"
    else:
        st = "missing_work"
    rows.append((w["edition"], st, w["n"], w["base"], w["creator"], w["isbn"], bn))

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("edition\tstatus\tn_vols\tbase_title\tcreator\tisbn_sample\tbase_norm\n")
    for r in sorted(rows, key=lambda x: (x[0], x[1], -x[2])):
        fh.write("\t".join(str(x) for x in r) + "\n")

from collections import Counter
by_ed = defaultdict(Counter)
for e, s, *_ in rows:
    by_ed[e][s] += 1
print("\n=== 全件サマリ(版 × 状態 = 作品数) ===")
print(f"{'版':10}{'本編無':>8}{'版未登録(本編有)':>16}{'既保有':>8}{'計':>7}{'母集団':>8}")
for name, _ in EDITIONS:
    cc = by_ed[name]; mw, hne, al = cc["missing_work"], cc["have_no_edition"], cc["already"]
    print(f"{name:10}{mw:>8}{hne:>16}{al:>8}{mw+hne+al:>7}{coverage[name][0]:>8}")
print(f"\nTSV → {OUT}")
