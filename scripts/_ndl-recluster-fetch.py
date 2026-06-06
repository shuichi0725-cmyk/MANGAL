"""recluster 31群の全ISBNを NDL SRU で取得し、dc:creator の役割付き著者を確定。
出力: .cache/ndl-recluster-full.json  {isbn: {title, vol, year, creators:[{name, role}]}}
- resumable: 既存キャッシュにあるISBNはskip。
- dc:creator は "武村勇治 漫画" / "池波正太郎 原作" 形式 = name + role を末尾語で分離。
"""
import sys, os, json, csv, re, html, time
import urllib.request, urllib.parse

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAND = os.path.join(ROOT, "data", "seeds", "slug-recluster-candidates.tsv")
OUT = os.path.join(ROOT, ".cache", "ndl-recluster-full.json")

ROLE_ARTIST = ["漫画", "作画", "画", "絵", "まんが", "マンガ"]
ROLE_ORIGINAL = ["原作", "原案", "著", "作", "原著", "脚本"]
ROLE_SUPER = ["監修", "編", "編集", "協力"]

def classify_role(word):
    if word in ROLE_ARTIST:
        return "artist"
    if word in ROLE_ORIGINAL:
        return "original"
    if word in ROLE_SUPER:
        return "supervisor"
    return None

def parse_creators(xml):
    """dc:creator のテキスト群 "名前 役割" を [{name, role}] に。"""
    out = []
    for s in re.findall(r"<dc:creator[^>]*>(.*?)</dc:creator>", xml, re.S):
        s = s.strip()
        if not s:
            continue
        parts = s.split()
        role = None
        name = s
        if len(parts) >= 2:
            r = classify_role(parts[-1])
            if r:
                role = r
                name = " ".join(parts[:-1])
        out.append({"name": name.strip(), "role": role})
    return out

def fetch(isbn):
    url = ("https://ndlsearch.ndl.go.jp/api/sru?operation=searchRetrieve&recordSchema=dcndl"
           "&maximumRecords=3&query=" + urllib.parse.quote('isbn="%s"' % isbn))
    raw = urllib.request.urlopen(url, timeout=30).read().decode("utf-8")
    x = html.unescape(raw)
    # title: 最初の dc:title > rdf:value
    mt = re.search(r"<dc:title>.*?<rdf:value>(.*?)</rdf:value>", x, re.S)
    title = (mt.group(1).strip() if mt else "")
    # volume: dcndl:volume > rdf:value
    mv = re.search(r"<dcndl:volume>.*?<rdf:value>(.*?)</rdf:value>", x, re.S)
    vol = (mv.group(1).strip() if mv else "")
    # year: dcterms:date
    md = re.search(r"<dcterms:date>(.*?)</dcterms:date>", x, re.S)
    year = ""
    if md:
        ym = re.search(r"(\d{4})", md.group(1))
        year = ym.group(1) if ym else ""
    creators = parse_creators(x)
    return {"title": title, "vol": vol, "year": year, "creators": creators}

def main():
    isbns = []
    seen = set()
    for row in csv.DictReader(open(CAND, encoding="utf-8"), delimiter="\t"):
        for i in row["isbns"].split(","):
            i = i.strip()
            if i and i not in seen:
                seen.add(i); isbns.append(i)
    cache = {}
    if os.path.exists(OUT):
        cache = json.load(open(OUT, encoding="utf-8"))
    todo = [i for i in isbns if i not in cache]
    print(f"全{len(isbns)} ISBN / 既取得{len(cache)} / 今回{len(todo)}")
    ok = err = 0
    for n, isbn in enumerate(todo, 1):
        try:
            cache[isbn] = fetch(isbn)
            ok += 1
        except Exception as e:
            cache[isbn] = {"error": str(e)}
            err += 1
        if n % 20 == 0:
            json.dump(cache, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"  {n}/{len(todo)} (ok={ok} err={err})")
        time.sleep(0.3)
    json.dump(cache, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"完了: ok={ok} err={err} → {OUT}")

if __name__ == "__main__":
    main()
