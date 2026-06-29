"""出版社unknownの未登録社を次バッチ分、NDL+楽天で確認しpublishers.ymlにキー追加(慎重)。
確認: Rakuten/NDL の社名が種2社名と一致(非空)→confirmed。 空文字は不一致扱い(バグ修正)。
キー: pykakasi でローマ字化(衝突回避)。 確認できた社のみ追加。 空確認は held に回し保留(報告)。
使用: _batch-pub-keys.py --n 50 [--apply]"""
import json, re, os, time, html, urllib.parse, urllib.request, unicodedata, sys, yaml
import pykakasi
sys.stdout.reconfigure(encoding="utf-8")
ROOT = "C:/Users/shuic/code/MANGAL"
env = dict(l.strip().split("=", 1) for l in open(f"{ROOT}/.env.local", encoding="utf-8") if "=" in l and not l.strip().startswith("#"))
ORIGIN = "https://mangal.shuichi0725.workers.dev"
N = int(sys.argv[sys.argv.index("--n")+1]) if "--n" in sys.argv else 50
APPLY = "--apply" in sys.argv
kks = pykakasi.kakasi()

def pnorm(s):
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = re.sub(r"(株式会社|有限会社|合同会社|㈱|㈲)", "", s)
    return re.sub(r"[\s　・,，\.。、:：;!！?？()（）\-]", "", s).strip().lower()

def mkkey(nm):
    nm2 = re.sub(r"(株式会社|有限会社|.{0,8}?(出版事業部|事業部))", "", unicodedata.normalize("NFKC", nm))
    r = "".join(x["hepburn"] for x in kks.convert(nm2))
    r = re.sub(r"[^a-z0-9]+", "-", r.lower()).strip("-")
    return r or "pub"

an = json.load(open(f"{ROOT}/.cache/pub-unknown-analysis.json", encoding="utf-8"))
ex = an["unkeyed_ex"]
pub = yaml.safe_load(open(f"{ROOT}/data/publishers.yml", encoding="utf-8")) or {}
keys = set(pub.keys()); names = {pnorm(v["name"]) for v in pub.values()}
# 未登録のみ(既追加15を除外) を count順
unkeyed = sorted(((n, c) for n, c in an["unkeyed"].items() if pnorm(n) not in names), key=lambda x: -x[1])[:N]

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
        return (it.get("publisherName") or "") if it else ""
    except Exception: return ""

def ndl(ib):
    q = {"operation": "searchRetrieve", "query": f"isbn={ib}", "recordSchema": "dcndl", "maximumRecords": "1"}
    req = urllib.request.Request("https://ndlsearch.ndl.go.jp/api/sru?" + urllib.parse.urlencode(q)); req.add_header("User-Agent", "Mozilla/5.0")
    try:
        xml = html.unescape(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))
        for pat in [r"<dcterms:publisher>.*?<rdf:value>([^<]+)<", r"<dc:publisher>([^<]+)<", r"<dcndl:publicationName>([^<]+)<", r"<dcterms:publisher>([^<]+)<"]:
            m = re.search(pat, xml, re.S)
            if m: return re.sub(r"<.*?>", "", m.group(1)).strip()
    except Exception: return ""
    return ""

confirmed = []; held = []
usedkeys = set(keys)
for nm, cnt in unkeyed:
    sl = (ex.get(nm) or [None])[0]
    ib = first_isbn(sl) if sl else None
    rk = nd = ""
    if ib:
        rk = rakuten(ib); time.sleep(0.4)
        nd = ndl(ib); time.sleep(1.0)
    ok = (rk and (pnorm(nm) in pnorm(rk) or pnorm(rk) in pnorm(nm))) or (nd and (pnorm(nm) in pnorm(nd) or pnorm(nd) in pnorm(nm)))
    if ok:
        k = mkkey(nm); base = k; i = 2
        while k in usedkeys: k = f"{base}-{i}"; i += 1
        usedkeys.add(k)
        confirmed.append((k, nm, cnt, rk or nd))
    else:
        held.append((nm, cnt, rk, nd))

print(f"=== 次バッチ {len(unkeyed)}社 確認 ===")
print(f"confirmed {len(confirmed)} / held(空・不一致) {len(held)}")
for k, nm, c, src in confirmed[:50]: print(f"  ✓[{c:>3}] {k:28} = {nm}  (確認:{src})")
print("--- held(保留) ---")
for nm, c, rk, nd in held[:20]: print(f"  ✗[{c:>3}] {nm}  楽天[{rk}] NDL[{nd}]")

if APPLY and confirmed:
    for k, nm, c, src in confirmed:
        pub[k] = {"name": nm}
    yaml.safe_dump(pub, open(f"{ROOT}/data/publishers.yml", "w", encoding="utf-8"), allow_unicode=True, sort_keys=False, width=4096)
    print(f"\nAPPLIED: {len(confirmed)}社 追加 / 計 {len(pub)}社")
json.dump({"confirmed": [(k, nm) for k, nm, c, s in confirmed], "held": [(nm, c) for nm, c, r, n in held]}, open(f"{ROOT}/.cache/pub-batch.json", "w", encoding="utf-8"), ensure_ascii=False)
