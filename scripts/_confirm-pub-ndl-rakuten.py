"""未登録出版社の上位を、サンプルISBNで NDL+楽天 確認(種2社名と照合)。キー追加前の検証。"""
import json, re, os, time, html, urllib.parse, urllib.request, yaml, sys
sys.stdout.reconfigure(encoding="utf-8")
ROOT = "C:/Users/shuic/code/MANGAL"
env = dict(l.strip().split("=", 1) for l in open(f"{ROOT}/.env.local", encoding="utf-8") if "=" in l and not l.strip().startswith("#"))
ORIGIN = "https://mangal.shuichi0725.workers.dev"
N = int(sys.argv[sys.argv.index("--top")+1]) if "--top" in sys.argv else 25

an = json.load(open(f"{ROOT}/.cache/pub-unknown-analysis.json", encoding="utf-8"))
unkeyed = an["unkeyed"]; ex = an["unkeyed_ex"]
top = sorted(unkeyed.items(), key=lambda x: -x[1])[:N]

def first_isbn(slug):
    p = f"{ROOT}/data/manga.v2/{slug}.yml"
    if not os.path.exists(p): return None
    d = yaml.safe_load(open(p, encoding="utf-8"))
    for e in d.get("editions", []):
        for v in e.get("volumes", []):
            ib = re.sub(r"\D", "", str(v.get("isbn13") or ""))
            if len(ib) == 13: return ib
    return None

def rakuten(ib):
    p = {"applicationId": env["RAKUTEN_APP_ID"], "accessKey": env["RAKUTEN_ACCESS_KEY"], "affiliateId": env.get("RAKUTEN_AFFILIATE_ID", ""), "isbn": ib, "outOfStockFlag": "1", "format": "json", "formatVersion": "2"}
    req = urllib.request.Request("https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?" + urllib.parse.urlencode(p))
    req.add_header("Referer", ORIGIN+"/"); req.add_header("Origin", ORIGIN); req.add_header("User-Agent", "Mozilla/5.0")
    try:
        it = (json.loads(urllib.request.urlopen(req, timeout=15).read()).get("Items") or [None])[0]
        return it.get("publisherName", "") if it else ""
    except Exception: return ""

def ndl(ib):
    q = {"operation": "searchRetrieve", "query": f"isbn={ib}", "recordSchema": "dcndl", "maximumRecords": "1"}
    req = urllib.request.Request("https://ndlsearch.ndl.go.jp/api/sru?" + urllib.parse.urlencode(q)); req.add_header("User-Agent", "Mozilla/5.0")
    try:
        xml = html.unescape(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))
        m = re.search(r"<dc:publisher>([^<]+)<", xml) or re.search(r"<dcndl:publicationName>([^<]+)<", xml)
        return m.group(1).strip() if m else ""
    except Exception: return ""

print(f"=== 未登録出版社 上位{N} を NDL+楽天で確認 ===")
results = []
for nm, cnt in top:
    sl = (ex.get(nm) or [None])[0]
    ib = first_isbn(sl) if sl else None
    if not ib:
        print(f"  [{cnt:>3}] {nm:18} ISBN無(skip)"); continue
    rk = rakuten(ib); time.sleep(0.5)
    nd = ndl(ib); time.sleep(1.2)
    def norm(s): return re.sub(r"[\s　・株式会社有限\(\)]", "", str(s or ""))
    ok = norm(nm) in norm(rk) or norm(rk) in norm(nm) or norm(nm) in norm(nd) or norm(nd) in norm(nm)
    results.append({"name": nm, "count": cnt, "isbn": ib, "rakuten": rk, "ndl": nd, "confirmed": ok})
    print(f"  [{cnt:>3}] {nm:18} {'✓' if ok else '✗'} 楽天[{rk}] NDL[{nd}]")
json.dump(results, open(f"{ROOT}/.cache/pub-confirm.json", "w", encoding="utf-8"), ensure_ascii=False)
print(f"\n確認OK: {sum(1 for r in results if r['confirmed'])}/{len(results)}")
