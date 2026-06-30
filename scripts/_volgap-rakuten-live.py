"""単一版remain作をLIVE楽天で確証(キャッシュに無い最近の取込もれ用)。1.1s厳守。
guard: 残差題完全一致(_rakuten_match_lib・スピンオフ/別作排除)+同出版社prefix+種2非存在+前後巻発売日整合。
入力 .cache/single-ed-remain.json [(slug,gaps_str)]。出力 .cache/volgap-live-cands.json"""
import sys,os,re,json,time,sqlite3,yaml,urllib.parse,urllib.request
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import _rakuten_match_lib as L
sys.stdout.reconfigure(encoding="utf-8")
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env=dict(l.strip().split("=",1) for l in open(f"{ROOT}/.env.local",encoding="utf-8") if "=" in l and not l.strip().startswith("#"))
URL="https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404"; ORIGIN="https://mangal.shuichi0725.workers.dev"
def ni(s): return re.sub(r"[^0-9X]","",str(s or "").upper())
def reg(ib):
    ib=ni(ib)
    if not ib.startswith("9784") or len(ib)!=13: return None
    b=ib[4:12]; n=int(b[:2])
    return b[:2] if n<=19 else b[:3] if n<=69 else b[:4] if n<=84 else b[:5] if n<=89 else b[:6] if n<=94 else b[:7]
con=sqlite3.connect(f"{ROOT}/.cache/db-v2.sqlite"); cur=con.cursor()
db=set(ni(r[0]) for r in cur.execute("SELECT isbn13 FROM volumes WHERE isbn13 IS NOT NULL"))
def sk_for(isbns):
    s=set()
    for ib in isbns:
        for r in cur.execute("SELECT se.series_key FROM volumes v JOIN editions e ON e.id=v.edition_id JOIN series se ON se.id=e.series_id WHERE v.isbn13=?",(ib,)): s.add(r[0])
    return sorted(s)
def rak(title):
    items=[]
    for pg in range(1,6):
        p={"applicationId":env["RAKUTEN_APP_ID"],"accessKey":env.get("RAKUTEN_ACCESS_KEY",""),"affiliateId":env.get("RAKUTEN_AFFILIATE_ID",""),"title":title,"booksGenreId":"001001","outOfStockFlag":"1","hits":"30","page":str(pg),"format":"json","formatVersion":"2"}
        req=urllib.request.Request(URL+"?"+urllib.parse.urlencode(p)); req.add_header("Referer",ORIGIN+"/");req.add_header("Origin",ORIGIN);req.add_header("User-Agent","Mozilla/5.0")
        try: j=json.loads(urllib.request.urlopen(req,timeout=30).read().decode("utf-8"))
        except Exception: break
        its=j.get("Items") or []
        if not its: break
        items+=its; time.sleep(1.1)
        if pg>=j.get("pageCount",1): break
    return items
def pm(s):
    m=re.match(r"(\d{4})(?:-(\d{1,2}))?",str(s or ""))
    return int(m.group(1))*12+(int(m.group(2) or 6)-1) if m else None
work=json.load(open(f"{ROOT}/.cache/single-ed-remain.json",encoding="utf-8"))
cands=[]; done=0
for slug,gaps in work:
    p=f"{ROOT}/data/manga.v2/{slug}.yml"
    if not os.path.exists(p): continue
    d=yaml.safe_load(open(p,encoding="utf-8")); eds=d.get("editions") or []
    title=d.get("title",""); base=L.norm(title)
    std=[(v.get("number"),ni(v.get("isbn13")),pm(str(v.get("release_date")))) for e in eds for v in (e.get("volumes") or []) if v.get("number")]
    isbns=[ib for _,ib,_ in std if len(ib)==13]
    from collections import Counter
    pc=Counter(reg(i) for i in isbns if reg(i)); mainpref=pc.most_common(1)[0][0] if pc else None
    sk=sk_for(isbns)
    if not sk: continue
    miss=sorted(set(int(x) for seg in gaps.split(";") if ":" in seg for x in re.findall(r"\d+",seg.split(":",1)[1])))
    datemap={n:dt for n,_,dt in std if dt}
    items=rak(title); done+=1
    # build vol->item (exact base)
    byv={}
    for it in items:
        raw=L.clean_title(it.get("title",""))
        v,res=L.parse_vol(raw)
        if v is None or L.norm(res)!=base: continue
        ib=ni(it.get("isbn",""))
        if len(ib)!=13: continue
        byv.setdefault(v,[]).append((ib,it))
    nums=sorted(set(datemap)|set(byv))
    for n in miss:
        for ib,it in byv.get(n,[]):
            if reg(ib)!=mainpref or ib in db: continue
            dt=pm(L.date_str(L.parse_salesdate(it.get("salesDate",""))))
            def neigh(x,lo):
                for m in (range(x-1,0,-1) if lo else range(x+1,(nums[-1] if nums else x)+2)):
                    if m in datemap: return datemap[m]
                return None
            lo,hi=neigh(n,True),neigh(n,False)
            if dt is not None and ((lo and dt<lo-18) or (hi and dt>hi+18)): continue
            cov=(it.get("largeImageUrl") or "").split("?")[0]
            cands.append({"slug":slug,"series_keys":sk,"number":n,"isbn13":ib,
                "release_date":L.date_str(L.parse_salesdate(it.get("salesDate",""))),"publisher":it.get("publisherName",""),
                "title":title,"cover":cov if "noimage" not in cov else "","raw":raw})
            break
    if done%40==0: print(f"  {done} works, {len(cands)} cands",flush=True)
json.dump(cands,open(f"{ROOT}/.cache/volgap-live-cands.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
print(f"DONE {done}作 → 確証候補 {len(cands)}巻")
