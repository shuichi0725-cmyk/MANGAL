"""recent単一版(>=2015)の出版社移籍/format漏れを救済。residual-base完全一致+発売日整合+種2非存在のみ
(版ブロック/同pub guard外す=移籍で別ISBN block・別publisherになるため)。単一版限定=Frankenstein無し。
review用に出力(怪しさは残差題完全一致+date-fitで抑制するが要目視)。"""
import sys,os,re,json,time,sqlite3,yaml,urllib.parse,urllib.request
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import _rakuten_match_lib as L
sys.stdout.reconfigure(encoding="utf-8")
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env=dict(l.strip().split("=",1) for l in open(f"{ROOT}/.env.local",encoding="utf-8") if "=" in l and not l.strip().startswith("#"))
URL="https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404"; ORIGIN="https://mangal.shuichi0725.workers.dev"
def ni(s): return re.sub(r"[^0-9X]","",str(s or "").upper())
def deruby(s): return re.sub(r"[（(][ぁ-んァ-ヶ・ー]+[）)]","",str(s or ""))
con=sqlite3.connect(f"{ROOT}/.cache/db-v2.sqlite"); cur=con.cursor()
db=set(ni(r[0]) for r in cur.execute("SELECT isbn13 FROM volumes WHERE isbn13 IS NOT NULL"))
def sk_for(isbns):
    s=set()
    for ib in isbns:
        for r in cur.execute("SELECT se.series_key FROM volumes v JOIN editions e ON e.id=v.edition_id JOIN series se ON se.id=e.series_id WHERE v.isbn13=?",(ib,)): s.add(r[0])
    return sorted(s)
def pm(s):
    m=re.match(r"(\d{4})(?:-(\d{1,2}))?",str(s or "")); return int(m.group(1))*12+(int(m.group(2) or 6)-1) if m else None
def rak(title):
    items=[]
    for pg in range(1,5):
        p={"applicationId":env["RAKUTEN_APP_ID"],"accessKey":env.get("RAKUTEN_ACCESS_KEY",""),"affiliateId":env.get("RAKUTEN_AFFILIATE_ID",""),"title":title,"booksGenreId":"001001","outOfStockFlag":"1","hits":"30","page":str(pg),"format":"json","formatVersion":"2"}
        req=urllib.request.Request(URL+"?"+urllib.parse.urlencode(p)); req.add_header("Referer",ORIGIN+"/");req.add_header("Origin",ORIGIN);req.add_header("User-Agent","Mozilla/5.0")
        try: j=json.loads(urllib.request.urlopen(req,timeout=30).read().decode("utf-8"))
        except Exception: break
        its=j.get("Items") or []
        if not its: break
        items+=its; time.sleep(1.1)
        if pg>=j.get("pageCount",1): break
    return items
remain=[l.rstrip("\n").split("\t")[0] for l in open(f"{ROOT}/docs/production-diagnostics/vol_gap_virtual_remain.tsv",encoding="utf-8")][1:]
cands=[]
for slug in remain:
    p=f"{ROOT}/data/manga.v2/{slug}.yml"
    if not os.path.exists(p): continue
    d=yaml.safe_load(open(p,encoding="utf-8")); eds=d.get("editions") or []
    if len(set(e.get("type") or "standard" for e in eds))>1: continue   # 単一版のみ
    if (d.get("year_started") or 0)<2015: continue   # recent
    title=d.get("title",""); wbase=L.norm(deruby(title))
    allisbn=[ni(v.get("isbn13")) for e in eds for v in (e.get("volumes") or []) if v.get("isbn13")]
    sk=sk_for([i for i in allisbn if len(i)==13])
    if not sk: continue
    e=eds[0]; vols=[(v.get("number"),pm(str(v.get("release_date")))) for v in (e.get("volumes") or []) if v.get("number")]
    nums=sorted(n for n,_ in vols); 
    if len(nums)<2: continue
    gaps=[n for n in range(nums[0],nums[-1]+1) if n not in nums]; dm={n:dt for n,dt in vols if dt}
    items=rak(deruby(title))
    byv={}
    for it in items:
        raw=L.clean_title(it.get("title",""))
        v,res=L.parse_vol(raw)
        if v is None or L.norm(deruby(res))!=wbase: continue
        ib=ni(it.get("isbn",""))
        if len(ib)==13: byv.setdefault(v,[]).append((ib,it))
    for n in gaps:
        for ib,it in byv.get(n,[]):
            if ib in db: continue
            dt=pm(L.date_str(L.parse_salesdate(it.get("salesDate",""))))
            def neigh(x,lo):
                for m in (range(x-1,0,-1) if lo else range(x+1,nums[-1]+2)):
                    if m in dm: return dm[m]
                return None
            lo,hi=neigh(n,True),neigh(n,False)
            if dt is not None and ((lo and dt<lo-18) or (hi and dt>hi+18)): continue
            cands.append({"slug":slug,"series_keys":sk,"number":n,"isbn13":ib,"edition_type":"standard",
                "release_date":L.date_str(L.parse_salesdate(it.get("salesDate",""))),"publisher":it.get("publisherName",""),"title":title,"raw":raw})
            break
json.dump(cands,open(f"{ROOT}/.cache/volgap-migration-cands.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("移籍tolerant確証",len(cands),"巻 /",len(set(c['slug'] for c in cands)),"作")
for c in sorted(cands,key=lambda x:x['title']):
    print(f"  {c['title'][:26]:28} v{c['number']:<3} {c['isbn13']} {c['release_date']:8} {c['publisher'][:12]:14}| {c['raw'][:24]}")
