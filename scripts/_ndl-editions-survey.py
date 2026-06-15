"""[調査only] NDLで版違い(完全版/新装版/愛蔵版/ワイド/復刻/フルカラー/カラー/オールカラー/新装再編版)の
漫画(ndc=726)を全件列挙→本編単位に重複除去→db-v2と突合し未登録候補をTSV化。
楽天は使わない(収穫中)。登録・本番変更は一切しない。出力: .cache/ndl-editions-survey.tsv
"""
import urllib.parse, urllib.request, time, re, sys, sqlite3, unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
EP = "https://ndlsearch.ndl.go.jp/api/sru"
OUT = ROOT / ".cache" / "ndl-editions-survey.tsv"

EDITIONS = [  # (NDL題キーワード, 我々のtype or None)
    ("完全版", "kanzenban"), ("新装版", "shinsoban"), ("愛蔵版", "aizoban"),
    ("ワイド版", "wideban"), ("復刻版", None), ("フルカラー", None),
    ("カラー版", None), ("オールカラー", None), ("新装再編版", None),
]
DROP_WORDS = ["総集編", "ガイド", "公式", "大全集", "画集", "原画集", "設定資料", "ファンブック", "資料集"]


def lnm(t): return t.split("}")[-1]


def norm(t):
    t = t or ""
    t = re.sub(r"[〔\[(（【].*?[〕\])）】]", "", t)
    for w in ["完全版", "新装版", "愛蔵版", "文庫版", "ワイド版", "フルカラー", "カラー版",
              "オールカラー", "復刻版", "新装再編版", "新装"]:
        t = t.replace(w, "")
    t = unicodedata.normalize("NFKC", t)
    t = re.sub(r"\s+", "", t).lower()
    t = re.sub(r"[ぁ-ん]", lambda m: chr(ord(m.group()) + 0x60), t)  # ひら→カタ
    t = re.sub(r"[^0-9a-zヲ-ヴー一-龯]", "", t)
    return t


def base_title(full):
    b = full.split(" : ")[0].strip()
    b = re.sub(r"[.　\s]*(?:第?\d+|上巻|下巻|上|下|別巻|前編|後編)\s*$", "", b).strip()
    return b


def fetch(name, start, maxr=200):
    q = {"operation": "searchRetrieve", "recordSchema": "dcndl", "recordPacking": "xml",
         "maximumRecords": str(maxr), "startRecord": str(start), "query": f"title={name} AND ndc=726"}
    url = EP + "?" + urllib.parse.urlencode(q)
    for attempt in range(4):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "MANGAL/0.1", "Accept": "application/xml"}),
                timeout=40).read()
        except Exception as e:
            if attempt < 3:
                time.sleep(5 + attempt * 5); continue
            raise


def rec_fields(rd):
    kids = list(rd)
    it = rd.iter() if kids else (ET.fromstring(rd.text).iter() if rd.text and "<" in rd.text else [])
    f = {}
    isbn = None
    for el in it:
        k = lnm(el.tag); t = (el.text or "").strip()
        if not t:
            continue
        if k in ("title", "seriesTitle", "creator", "volume", "edition") and k not in f:
            f[k] = t
        if k == "identifier" and not isbn:
            m = re.search(r"97[89]\d{10}", t.replace("-", ""))
            if m:
                isbn = m.group()
    if isbn:
        f["isbn"] = isbn
    return f


# DB(db-v2)
con = sqlite3.connect(str(ROOT / ".cache" / "db-v2.sqlite"))
allt = set()
type_titles = defaultdict(set)
for title, etype in con.execute("select s.title, e.type from series s join editions e on e.series_id=s.id"):
    n = norm(title); allt.add(n)
    if etype:
        type_titles[etype].add(n)

works = {}  # (base_norm, edition) -> dict
totals = {}
for name, typ in EDITIONS:
    start = 1; total = None; got = 0
    while True:
        try:
            b = fetch(name, start)
        except Exception as e:
            print(f"[{name}] ERR start={start}: {str(e)[:50]}"); break
        root = ET.fromstring(b)
        if total is None:
            for el in root.iter():
                if lnm(el.tag) == "numberOfRecords":
                    total = int(el.text or "0"); break
        page = 0
        for rd in root.iter():
            if lnm(rd.tag) != "recordData":
                continue
            page += 1
            f = rec_fields(rd)
            full = f.get("seriesTitle") or f.get("title") or ""
            if not full or name not in (f.get("title", "") + f.get("seriesTitle", "") + f.get("edition", "")):
                # editionキーワードがどこにも無ければ別物の可能性→ただしtitle検索なので基本含む
                pass
            if any(w in full for w in DROP_WORDS):
                continue
            bt = base_title(full)
            bn = norm(bt)
            if not bn:
                continue
            key = (bn, name)
            w = works.setdefault(key, {"edition": name, "base": bt, "creator": f.get("creator", ""),
                                       "isbn": f.get("isbn", ""), "n": 0, "type": typ})
            w["n"] += 1
            if not w["isbn"] and f.get("isbn"):
                w["isbn"] = f["isbn"]
        got += page
        start += 200
        time.sleep(1.3)
        if total is None or start > total or page == 0:
            break
    totals[name] = (total, got)
    print(f"[{name}] NDL numberOfRecords={total} 取得{got}")

# 突合・分類
rows = []
for (bn, name), w in works.items():
    typ = w["type"]
    if typ and bn in type_titles.get(typ, set()):
        status = "already"        # 既に同型版を保有
    elif bn in allt:
        status = "have_no_edition"  # 本編はある・この版が無い(ドラゴンボール型)
    else:
        status = "missing_work"     # 本編ごと未登録
    rows.append((w["edition"], status, w["n"], w["base"], w["creator"], w["isbn"], bn))

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("edition\tstatus\tn_vols\tbase_title\tcreator\tisbn_sample\tbase_norm\n")
    for r in sorted(rows, key=lambda x: (x[0], x[1], -x[2])):
        fh.write("\t".join(str(x) for x in r) + "\n")

# サマリ
from collections import Counter
print("\n=== サマリ(版 × 状態 = 作品数) ===")
c = Counter((e, s) for e, s, *_ in rows)
by_ed = defaultdict(lambda: Counter())
for (e, s), n in c.items():
    by_ed[e][s] = n
print(f"{'版':10} {'未登録(本編無)':>12} {'版未登録(本編有)':>14} {'既保有':>8} {'計作品':>8}")
for name, _ in EDITIONS:
    cc = by_ed[name]
    mw, hne, al = cc.get("missing_work", 0), cc.get("have_no_edition", 0), cc.get("already", 0)
    print(f"{name:10} {mw:>12} {hne:>14} {al:>8} {mw+hne+al:>8}")
print(f"\nTSV → {OUT}")
