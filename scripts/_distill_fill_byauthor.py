"""巻抜けの難件(汎用題/題揺れ=アウト→OUT等)を ★作者検索＋既存ISBN錨 で取り直す。
NDL creator検索→作者の全作品→既存ページのISBNを含むtitle群=同一作→全巻採用。
出力: distill-fill-2026.jsonl に上書き追記(slug key)。usage: python _distill_fill_byauthor.py <slug1> <slug2> ..."""
import sys, re, json, os, time, html, urllib.request, urllib.parse, yaml, unicodedata
ROOT = "C:/Users/shuic/code/MANGAL"
RATE = 1.2
def norm(s): return re.sub(r"[\s　・･:：!！?？.,。、\-〜~\[\]()『』「」]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()
def basetitle(t): return re.sub(r"[.．:：]\s*(vol(ume)?\.?\s*)?\d+.*$", "", str(t or ""), flags=re.I).strip()
def cleanau(a): return re.sub(r"(ストーリー協力|監修協力|監修|協力|ネーム構成|構成|原作|作画|著|画|漫画|＆.*|&.*)$", "", str(a or "")).strip()
def volnum(v, t):
    m = re.sub(r"\D", "", str(v or ""))
    if m: return int(m)
    mm = re.search(r"(\d+)\s*$", str(t or ""))
    return int(mm.group(1)) if mm else 1
def ndl_creator(au):
    q = f'creator="{au}" AND ndc=726.1'
    url = "https://ndlsearch.ndl.go.jp/api/sru?" + urllib.parse.urlencode({"operation": "searchRetrieve", "query": q, "recordSchema": "dcndl", "maximumRecords": "200"})
    try:
        x = html.unescape(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "MANGAL/1.0"}), timeout=40).read().decode("utf-8", "replace"))
        time.sleep(RATE)
    except Exception: return []
    out = []
    for rec in re.findall(r"<recordData>(.*?)</recordData>", x, re.S):
        ib = re.search(r'ISBN">([0-9\-]+)', rec)
        if not ib: continue
        isbn = re.sub(r"\D", "", ib.group(1))
        if len(isbn) != 13: continue
        t = re.search(r"<dcterms:title>([^<]+)", rec); vm = re.search(r"<dcndl:volume>.*?<rdf:value>([^<]+)", rec, re.S); d = re.search(r"<dcterms:date>([^<]+)", rec)
        out.append({"isbn": isbn, "title": (t.group(1) if t else "").strip(), "vol": vm.group(1) if vm else "", "date": (d.group(1).strip() if d else "")})
    return out

slugs = sys.argv[1:]
fillrecs = {json.loads(l)["slug"]: json.loads(l) for l in open(f"{ROOT}/data/seeds/distill-fill-2026.jsonl", encoding="utf-8")}
for slug in slugs:
    pf = f"{ROOT}/.preview-data/manga/{slug}.yml"
    if not os.path.exists(pf): print(f"  {slug}: page無"); continue
    d = yaml.safe_load(open(pf, encoding="utf-8"))
    exist_isbn = {v.get("isbn13") for e in d.get("editions", []) for v in e.get("volumes", []) if v.get("isbn13")}
    aus = [cleanau(a.get("name")) for a in (d.get("authors", []) + d.get("original_authors", [])) if a.get("name") and a.get("name") != "(unknown)"]
    allrec = []
    for au in aus[:3]:
        if au: allrec += ndl_creator(au)
    # ISBN錨: 既存ISBNを含む title群(basetitle)を同一作とみなす
    from collections import defaultdict
    by_bt = defaultdict(list)
    for r in allrec: by_bt[norm(basetitle(r["title"]))].append(r)
    target = None
    for bt, recs in by_bt.items():
        if exist_isbn & {r["isbn"] for r in recs}: target = recs; break
    if not target:
        print(f"  {slug}: 錨ISBN一致せず(取得{len(allrec)})"); continue
    seen = {}
    for r in target:
        n = volnum(r["vol"], r["title"])
        dt = (re.match(r"(\d{4})[.](\d{1,2})", r["date"]) if r["date"] else None)
        rd = f"{dt.group(1)}-{int(dt.group(2)):02d}" if dt else (r["date"][:4] if re.match(r"\d{4}", r["date"]) else None)
        if n not in seen: seen[n] = {"number": n, "isbn13": r["isbn"], "release_date": rd}
    vols = sorted(seen.values(), key=lambda v: v["number"])
    fillrecs[slug] = {"slug": slug, "base_title": d.get("title"), "author": ",".join(aus), "volumes": vols, "n_found": len(vols), "src": "byauthor"}
    print(f"  {slug}: {len(vols)}巻(作者検索・ISBN錨)")
with open(f"{ROOT}/data/seeds/distill-fill-2026.jsonl", "w", encoding="utf-8") as f:
    for r in fillrecs.values(): f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"distill-fill-2026.jsonl 更新: {len(fillrecs)}件")
