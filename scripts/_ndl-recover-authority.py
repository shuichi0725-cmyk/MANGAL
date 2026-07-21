"""B: NDL典拠ID回収(同名異人分離)。discovery TSVが拾い損ねた著者典拠IDを per-ISBN SRUで回収。
[[acquire_all_obtainable_info]] の抜き忘れ是正。NDL=1.2s/req・cache優先・resumable。

- 対象ISBN = discovery(2024/2025)で「271新規著者(docs/ndl-new-authors-2024-2025.tsv)」を含む行。
  --all で discovery全ISBN。
- 各ISBN → creators (name, authority_id, yomi, role)。
- 出力:
  data/seeds/ndl-author-authority.jsonl  = authority_id毎 {name, yomi, isbns[], roles[]} (durable seed)
  docs/ndl-homonym-candidates.tsv        = 同一name→複数authority_id (=同名異人) の証拠

usage:
  python _ndl-recover-authority.py            # 271著者のISBNのみ(既定)
  python _ndl-recover-authority.py --all       # discovery全ISBN
"""
import sys, os, re, json, time, html, collections, urllib.request, urllib.parse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
CACHE = f"{ROOT}/.cache/ndl-sru-raw-cache.json"
RATE = 1.2  # NDL安全(楽天速度・429回避)
ALLISBN = "--all" in sys.argv
NOQUERY = "--no-query" in sys.argv  # cacheのみで抽出(throttle時の中間集計/top-up後の再抽出)

def nm(s):
    return re.sub(r"[\s　,、]", "", str(s or ""))

# 271新規著者
new_authors = set()
for l in open(f"{ROOT}/docs/ndl-new-authors-2024-2025.tsv", encoding="utf-8").read().splitlines()[1:]:
    if l.strip():
        new_authors.add(nm(l.split("\t")[0]))

# discovery ISBN収集
target = set()
for fn in (f"{ROOT}/data/seeds/ndl-discovery-2024.tsv", f"{ROOT}/data/seeds/ndl-discovery-2025.tsv"):
    if not os.path.exists(fn):
        continue
    rows = open(fn, encoding="utf-8").read().splitlines()
    h = rows[0].split("\t"); ci = h.index("creators"); ii = h.index("isbn13")
    for l in rows[1:]:
        c = l.split("\t")
        if len(c) <= ci:
            continue
        if ALLISBN:
            target.add(c[ii])
        else:
            creators = [nm(x) for x in c[ci].split("/") if x]
            if any(cr in new_authors for cr in creators):
                target.add(c[ii])
print(f"対象ISBN: {len(target)} ({'all discovery' if ALLISBN else '271著者含む'})", flush=True)

cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
need = [i for i in sorted(target) if i not in cache]
print(f"cache済 {len(target)-len(need)} / 要query {len(need)} (既存cache {len(cache)})", flush=True)

def ndl(isbn):
    url = "https://ndlsearch.ndl.go.jp/api/sru?" + urllib.parse.urlencode(
        {"operation": "searchRetrieve", "query": f"isbn={isbn}", "recordSchema": "dcndl", "maximumRecords": "3"})
    for attempt in range(4):
        try:
            x = html.unescape(urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "MANGAL/1.0"}), timeout=30).read().decode("utf-8", "replace"))
            time.sleep(RATE)
            return x
        except Exception as e:
            if "429" in str(e):
                print(f"  429 backoff", flush=True)
            time.sleep(RATE * (attempt + 3))
    return ""

n = 0
for isbn in ([] if NOQUERY else need):
    x = ndl(isbn)
    if x:
        cache[isbn] = x
    n += 1
    if n % 25 == 0:
        print(f"  query {n}/{len(need)}", flush=True)
        json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)

# ---- 抽出 ----
CRE = re.compile(
    r'<foaf:Agent\s+rdf:about="https?://id\.ndl\.go\.jp/auth/entity/(\d+)">\s*'
    r'<foaf:name>([^<]+)</foaf:name>(?:\s*<dcndl:transcription>([^<]+)</dcndl:transcription>)?', re.S)

auth = {}  # aid -> {name, yomi, isbns:set}
name_auth = collections.defaultdict(set)  # nm(name) -> set(aid)
name_disp = {}  # nm -> display name
for isbn in sorted(target):
    x = cache.get(isbn, "")
    if not x:
        continue
    rec = re.search(r"<recordData>(.*?)</recordData>", x, re.S)
    scope = rec.group(1) if rec else x
    for m in CRE.finditer(scope):
        aid, name, yomi = m.group(1), m.group(2).strip(), (m.group(3) or "").strip()
        a = auth.setdefault(aid, {"name": name, "yomi": yomi, "isbns": set()})
        a["isbns"].add(isbn)
        if yomi and not a["yomi"]:
            a["yomi"] = yomi
        name_auth[nm(name)].add(aid)
        name_disp[nm(name)] = name

# durable seed
with open(f"{ROOT}/data/seeds/ndl-author-authority.jsonl", "w", encoding="utf-8") as f:
    for aid, a in sorted(auth.items()):
        f.write(json.dumps({"ndl_authority_id": aid, "name": a["name"], "yomi": a["yomi"],
                            "n_isbn": len(a["isbns"]), "isbns": sorted(a["isbns"])[:20]}, ensure_ascii=False) + "\n")

# homonym = 同一name(norm)→複数authority_id
homonyms = {n: a for n, a in name_auth.items() if len(a) > 1}
with open(f"{ROOT}/docs/ndl-homonym-candidates.tsv", "w", encoding="utf-8") as f:
    f.write("name\tn_authorities\tauthority_ids\tdetails\n")
    for n0, aids in sorted(homonyms.items(), key=lambda x: -len(x[1])):
        det = " || ".join(f"{aid}:{auth[aid]['yomi']}({len(auth[aid]['isbns'])}冊)" for aid in sorted(aids))
        f.write(f"{name_disp[n0]}\t{len(aids)}\t{','.join(sorted(aids))}\t{det}\n")

print(f"\n回収: authority {len(auth)} / 著者名(norm) {len(name_auth)}")
print(f"★同名異authority(同名異人候補): {len(homonyms)}")
print(f"seed: data/seeds/ndl-author-authority.jsonl / homonym: docs/ndl-homonym-candidates.tsv")
for n0, aids in sorted(homonyms.items(), key=lambda x: -len(x[1]))[:10]:
    print(f"   {name_disp[n0]}: {sorted(aids)}")
