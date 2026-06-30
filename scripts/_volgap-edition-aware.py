"""残巻抜けをper-edition(版ごと)にcached NDLで確証。多版作のFrankenstein回避:
欠番巻のISBNが【その版の既存ISBNと共通prefix(>=10桁)一致】する時だけ採用=同版continuation。
+ 種2非存在 + 前後巻発売日整合。 edition_type=その版で種4追加(promoteが版振り分け)。
うしおととら型(ワイド版9784091258XXX系のv2-9)を安全に拾う。 confirmableのみ出力。
使用: _volgap-edition-aware.py [--apply]"""
import sys,os,re,json,sqlite3,yaml
sys.stdout.reconfigure(encoding="utf-8")
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPLY="--apply" in sys.argv
def norm_isbn(s): return re.sub(r"[^0-9X]","",str(s or "").upper())
def pdate(s):
    m=re.match(r"(\d{4})[.\-](\d{1,2})",str(s or "")) or re.match(r"(\d{4})",str(s or ""))
    if not m: return None
    y=int(m.group(1)); mo=int(m.group(2)) if m.lastindex and m.lastindex>=2 else 6
    return y*12+mo-1
con=sqlite3.connect(f"{ROOT}/.cache/db-v2.sqlite"); cur=con.cursor()
db_isbns={norm_isbn(r[0]) for r in cur.execute("SELECT isbn13 FROM volumes WHERE isbn13 IS NOT NULL")}
def sk_for(isbns):
    s=set()
    for ib in isbns:
        for r in cur.execute("SELECT se.series_key FROM volumes v JOIN editions e ON e.id=v.edition_id JOIN series se ON se.id=e.series_id WHERE v.isbn13=?",(ib,)): s.add(r[0])
    return sorted(s)
ndl={}
for l in open(f"{ROOT}/.cache/volgap-ndl.jsonl",encoding="utf-8"):
    o=json.loads(l); ndl[o["slug"]]=o.get("records",[])
def lcp(strs):
    if not strs: return ""
    s1,s2=min(strs),max(strs); i=0
    while i<len(s1) and i<len(s2) and s1[i]==s2[i]: i+=1
    return s1[:i]

remain=[l.rstrip("\n").split("\t")[0] for l in open(f"{ROOT}/docs/production-diagnostics/vol_gap_virtual_remain.tsv",encoding="utf-8")][1:]
cands=[]; stat={"works":0,"nomatch":0}
for slug in remain:
    p=f"{ROOT}/data/manga.v2/{slug}.yml"
    if not os.path.exists(p): continue
    d=yaml.safe_load(open(p,encoding="utf-8")); eds=d.get("editions") or []
    allisbn=[norm_isbn(v.get("isbn13")) for e in eds for v in (e.get("volumes") or []) if v.get("isbn13")]
    sk=sk_for([i for i in allisbn if i])
    if not sk: continue
    # ndl by vol number
    by_vol={}
    for r in ndl.get(slug,[]):
        mn=re.search(r"\d+",(r.get("volume") or "").strip())
        if mn and r.get("isbn"): by_vol.setdefault(int(mn.group()),[]).append(r)
    work_has=False
    for e in eds:
        et=e.get("type") or "standard"
        vols=[(v.get("number"),norm_isbn(v.get("isbn13")),pdate(v.get("release_date"))) for v in (e.get("volumes") or []) if v.get("number")]
        nums=sorted(n for n,_,_ in vols)
        if len(nums)<2: continue
        gaps=[n for n in range(nums[0],nums[-1]+1) if n not in nums]
        if not gaps: continue
        ed_isbns=[ib for _,ib,_ in vols if len(ib)==13]
        pre=lcp(ed_isbns)
        if len(pre)<10: continue   # 版のISBN系列が固まってない=同版判定不可→skip(怪しい)
        datemap={n:dt for n,_,dt in vols if dt}
        def neigh(n,lo):
            rng=range(n-1,0,-1) if lo else range(n+1,nums[-1]+2)
            for m in rng:
                if m in datemap: return datemap[m]
            return None
        for n in gaps:
            best=None
            for r in by_vol.get(n,[]):
                ib=norm_isbn(r.get("isbn"))
                if len(ib)!=13 or not ib.startswith(pre): continue   # 同版ISBN系列のみ
                if ib in db_isbns: continue
                dt=pdate(r.get("date"))
                lo,hi=neigh(n,True),neigh(n,False)
                if dt is not None:
                    if lo is not None and dt<lo-18: continue
                    if hi is not None and dt>hi+18: continue
                best=r; break
            if best:
                cands.append({"slug":slug,"series_keys":sk,"number":n,"isbn13":norm_isbn(best["isbn"]),
                    "release_date":(best.get("date") or "")[:7].replace(".","-"),"edition_type":et,
                    "publisher":best.get("publisher",""),"title":d.get("title")})
                work_has=True
    if work_has: stat["works"]+=1
print(f"確証候補 {len(cands)}巻 / {stat['works']}作 (同版ISBN系列+種2非存在+発売日整合)")
from collections import Counter,defaultdict
bk=defaultdict(list)
for c in cands: bk[(c['title'],c['edition_type'])].append(c['number'])
with open(f"{ROOT}/.cache/volgap-edition-cands.txt","w",encoding="utf-8") as f:
    for (t,et),ns in sorted(bk.items()): f.write(f"{t[:26]:28} [{et}] {sorted(ns)}\n")
json.dump(cands,open(f"{ROOT}/.cache/volgap-edition-cands.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("→ .cache/volgap-edition-cands.txt / .json")
if not APPLY: print("\n(--apply で種4手動へ追加)")
