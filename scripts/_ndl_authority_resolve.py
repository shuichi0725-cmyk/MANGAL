"""NDL著者典拠で曖昧merge群を裁定(慎重版): 種2別qidの小群を NDL典拠IDで homonym(split)/同一作(keep)判定。
種2 qid不整合(同著者別qid=FULL SWING型)を NDL典拠が解消。低速0.7s・cache優先・resumable。
出力: data/seeds/merge-authority-decisions.tsv (group→keep/split/flag + 証拠)。種2 read-only。"""
import sqlite3, collections, re, json, os, urllib.request, urllib.parse, html, time, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
CACHE = f"{ROOT}/.cache/ndl-sru-raw-cache.json"
con = sqlite3.connect(f"file:{ROOT}/.cache/db-v2.sqlite?mode=ro", uri=True); con.text_factory = lambda b: b.decode("utf-8","replace")

def strip_punct(t): return re.sub(r"[\s　・･:：、。!！?？\-—–~〜\.]+$", "", str(t or "")).strip()
def nkana(k): return re.sub(r"[\s　・･×]", "", str(k or ""))
def is_ascii(t):
    try: str(t or "").encode("ascii"); return bool(t)
    except: return False
def pref(i): i = re.sub(r"\D","",str(i or "")); return i[:7] if len(i) >= 7 else ""

ser = list(con.execute("SELECT id,title,title_kana,qid FROM series WHERE title IS NOT NULL"))
sid_q = {s[0]: s[3] for s in ser}; sid_t = {s[0]: s[1] for s in ser}
sid_pref = collections.defaultdict(set); sid_isbn = {}
for sid, isbn in con.execute("SELECT e.series_id,v.isbn13 FROM volumes v JOIN editions e ON e.id=v.edition_id WHERE v.isbn13 IS NOT NULL ORDER BY v.number"):
    sid_pref[sid].add(pref(isbn)); sid_isbn.setdefault(sid, isbn)
sid_au = collections.defaultdict(set)
for sid, name in con.execute("SELECT sa.series_id,m.name FROM series_authors sa JOIN mangaka m ON m.id=sa.mangaka_id"): sid_au[sid].add(name)

# 曖昧群: title-strip + kana、2-4 series、別qid、同出版社(pub_compatible通る=guard対象)
groups = {}
tg = collections.defaultdict(list)
for sid, t, k, q in ser: tg[("T", strip_punct(t))].append(sid)
kg = collections.defaultdict(list)
for sid, t, k, q in ser:
    if nkana(k): kg[("K", nkana(k))].append((sid, t))
def add(key, sids, kana=False):
    s = [x[0] for x in sids] if kana else sids
    if not (2 <= len(s) <= 4): return
    if kana and not any(is_ascii(x[1]) for x in sids): return
    qs = set(sid_q[x] for x in s if sid_q.get(x))
    if len(qs) < 2: return
    prefs = [sid_pref[x] for x in s if sid_pref[x]]
    if len(prefs) < 2 or len(set.union(*prefs)) >= sum(len(p) for p in prefs): return  # 別社=skip
    groups[key] = s
for k, v in tg.items(): add(k, v)
for k, v in kg.items(): add(k, v, True)
print(f"曖昧merge群(NDL裁定対象): {len(groups)}", flush=True)

cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
need = set()
for sids in groups.values():
    for s in sids:
        if sid_isbn.get(s) and sid_isbn[s] not in cache: need.add(sid_isbn[s])
print(f"NDL新規照会: {len(need)}件 (cache {len(cache)})", flush=True)

def ndl(isbn):
    if isbn in cache: return cache[isbn]
    url = "https://ndlsearch.ndl.go.jp/api/sru?" + urllib.parse.urlencode({"operation":"searchRetrieve","query":f"isbn={isbn}","recordSchema":"dcndl","maximumRecords":"2"})
    try:
        x = html.unescape(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"}), timeout=20).read().decode("utf-8","replace"))
        cache[isbn] = x; time.sleep(0.7); return x
    except Exception as e:
        return f"ERR{e}"
n = 0
for isbn in sorted(need):
    ndl(isbn); n += 1
    if n % 50 == 0:
        print(f"  {n}/{len(need)}", flush=True); json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)

def auth_of(isbn):
    x = cache.get(isbn, "")
    return set(re.findall(r"auth/entity/(\d+)", x))

# 裁定
fo = open(f"{ROOT}/data/seeds/merge-authority-decisions.tsv", "w", encoding="utf-8")
fo.write("group_key\tdecision\tsids\ttitles\tndl_authorities\treason\n")
dec = collections.Counter()
for key, sids in groups.items():
    auths = {s: auth_of(sid_isbn.get(s, "")) for s in sids}
    nonempty = [a for a in auths.values() if a]
    if len(nonempty) < 2:
        d = "flag_typo_or_old"; reason = "NDL典拠不足→著者名/人手"  # ドーベルマン型
    elif set.union(*nonempty) and all(nonempty[0] & a for a in nonempty):
        d = "keep_same_work"; reason = "典拠overlap=同一作(FULL SWING型)"
    else:
        # 典拠が互いに素=別作
        allp = [a for a in nonempty]
        disjoint = all(not (allp[i] & allp[j]) for i in range(len(allp)) for j in range(i+1, len(allp)))
        if disjoint: d = "split_homonym"; reason = "典拠互いに素=別作(ジパング型)"
        else: d = "partial"; reason = "典拠一部overlap=要確認"
    dec[d] += 1
    ts = "|".join(sid_t.get(s,"")[:10] for s in sids)
    aus = "|".join(",".join(sorted(auths[s])) or "-" for s in sids)
    fo.write(f"{key[1][:20]}\t{d}\t{','.join(map(str,sids))}\t{ts}\t{aus}\t{reason}\n")
fo.close()
print(f"\n裁定完了 → data/seeds/merge-authority-decisions.tsv")
for k, v in dec.most_common(): print(f"  {k}: {v}")
