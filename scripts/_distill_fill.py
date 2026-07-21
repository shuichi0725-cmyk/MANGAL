"""真の抜け(62件=種2にも本番にも無い継続巻)の earlier volumes を NDL題検索で取得。
★著者一致のみ採用(homonym/別作の誤混入を防ぐ=慎重)。 1.2s・resumable。
出力: data/seeds/distill-fill-2026.jsonl  ({slug, base_title, author, volumes:[{number,isbn13,release_date}], n_found})"""
import csv, re, json, os, time, html, urllib.request, urllib.parse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
OUT = f"{ROOT}/data/seeds/distill-fill-2026.jsonl"
RATE = 1.2

def na(n): return re.sub(r"[\s　,、／/]", "", str(n or ""))
def main_title(t): return re.sub(r"\s*[:：].*$", "", str(t or "")).strip()
def volnum(v, t):
    m = re.sub(r"\D", "", str(v or ""))
    if m: return int(m)
    mm = re.search(r"[.．]\s*(\d+)\s*$", str(t or ""))
    return int(mm.group(1)) if mm else 1

def ndl_search(title):
    q = f'title="{title}" AND ndc=726.1'
    url = "https://ndlsearch.ndl.go.jp/api/sru?" + urllib.parse.urlencode(
        {"operation": "searchRetrieve", "query": q, "recordSchema": "dcndl", "maximumRecords": "40"})
    for attempt in range(3):
        try:
            x = html.unescape(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "MANGAL/1.0"}), timeout=30).read().decode("utf-8", "replace"))
            time.sleep(RATE); break
        except Exception:
            time.sleep(RATE * (attempt + 2)); x = ""
    out = []
    for rec in re.findall(r"<recordData>(.*?)</recordData>", x, re.S):
        ib = re.search(r'ISBN">([0-9\-]+)', rec)
        if not ib: continue
        isbn = re.sub(r"\D", "", ib.group(1))
        if len(isbn) != 13: continue
        t = re.search(r"<dcterms:title>([^<]+)", rec)
        vm = re.search(r"<dcndl:volume>.*?<rdf:value>([^<]+)", rec, re.S)
        d = re.search(r"<dcterms:date>([^<]+)", rec)
        cre = re.findall(r"<dc:creator>([^<]+)", rec)
        out.append({"isbn": isbn, "title": (t.group(1) if t else "").strip(),
                    "vol": vm.group(1) if vm else "", "date": (d.group(1).strip() if d else ""),
                    "cre": [re.sub(r"\s+(著|原作|作画|漫画|画|劇画)$", "", c).strip() for c in cre]})
    return out

rows = list(csv.DictReader(open(f"{ROOT}/data/seeds/distill-fill-targets-2026.tsv", encoding="utf-8"), delimiter="\t"))
done = set()
if os.path.exists(OUT):
    for l in open(OUT, encoding="utf-8"):
        try: done.add(json.loads(l)["slug"])
        except: pass
fo = open(OUT, "a", encoding="utf-8")
filled = thin = 0
for i, r in enumerate(rows):
    if r["slug"] in done: continue
    myau = {na(a) for a in r["author"].split(",") if a.strip()}
    recs = ndl_search(main_title(r["base_title"]))
    # ★著者一致のみ(homonym/別作除外)
    same = [x for x in recs if myau & {na(c) for c in x["cre"]}] if myau else []
    seen_isbn = {}
    for x in same:
        n = volnum(x["vol"], x["title"])
        d = re.sub(r"[.](\d)", r"-0\1", re.sub(r"[.](\d\d)", r"-\1", x["date"]))[:7] if x["date"] else None
        if n not in seen_isbn: seen_isbn[n] = {"number": n, "isbn13": x["isbn"], "release_date": d}
    vols = sorted(seen_isbn.values(), key=lambda v: v["number"])
    rec = {"slug": r["slug"], "base_title": r["base_title"], "author": r["author"],
           "volumes": vols, "n_found": len(vols)}
    fo.write(json.dumps(rec, ensure_ascii=False) + "\n"); fo.flush()
    if len(vols) >= 2: filled += 1
    else: thin += 1
    if (i + 1) % 10 == 0: print(f"  {i+1}/{len(rows)} (埋まった{filled}/薄い{thin})", flush=True)
fo.close()
recs = [json.loads(l) for l in open(OUT, encoding="utf-8")]
print(f"完了: {len(recs)}件 / 複数巻取得(埋まった){sum(1 for r in recs if r['n_found']>=2)} / 1巻のみ(薄い){sum(1 for r in recs if r['n_found']<2)}")
