"""ruby題(怪物(けもの)事変型)でauto漏れした残巻抜けを、ルビ除去マッチ+版aware+live楽天で確証。
ruby = title中の （かな/カナ）。除去した題で楽天残差題照合。他guard(版ブロック/種2非存在/発売日整合)は同じ。"""
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
    d=yaml.safe_load(open(p,encoding="utf-8")); title=d.get("title","")
    if not re.search(r"[（(][ぁ-んァ-ヶ・ー]+[）)]",title): continue   # ruby題のみ
    wbase=L.norm(deruby(title))
    eds=d.get("editions") or []
    allisbn=[ni(v.get("isbn13")) for e in eds for v in (e.get("volumes") or []) if v.get("isbn13")]
    sk=sk_for([i for i in allisbn if len(i)==13])
    if not sk: continue
    items=rak(deruby(title))
    byv={}
    for it in items:
        raw=L.clean_title(it.get("title",""))
        v,res=L.parse_vol(raw)
        if v is None or L.norm(deruby(res))!=wbase: continue
        ib=ni(it.get("isbn",""))
        if len(ib)==13: byv.setdefault(v,[]).append((ib,it))
    for e in eds:
        et=e.get("type") or "standard"
        vols=[(v.get("number"),ni(v.get("isbn13")),pm(str(v.get("release_date")))) for v in (e.get("volumes") or []) if v.get("number")]
        nums=sorted(n for n,_,_ in vols)
        if len(nums)<2: continue
        gaps=[n for n in range(nums[0],nums[-1]+1) if n not in nums]
        pre9=set(ib[:9] for _,ib,_ in vols if len(ib)==13); dm={n:dt for n,_,dt in vols if dt}
        for n in gaps:
            for ib,it in byv.get(n,[]):
                if ib[:9] not in pre9 or ib in db: continue
                dt=pm(L.date_str(L.parse_salesdate(it.get("salesDate",""))))
                def neigh(x,lo):
                    for m in (range(x-1,0,-1) if lo else range(x+1,nums[-1]+2)):
                        if m in dm: return dm[m]
                    return None
                lo,hi=neigh(n,True),neigh(n,False)
                if dt is not None and ((lo and dt<lo-18) or (hi and dt>hi+18)): continue
                cands.append({"slug":slug,"series_keys":sk,"number":n,"isbn13":ib,"edition_type":et,
                    "release_date":L.date_str(L.parse_salesdate(it.get("salesDate",""))),"publisher":it.get("publisherName",""),"title":title})
                break
json.dump(cands,open(f"{ROOT}/.cache/volgap-ruby-cands.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
from collections import defaultdict
bk=defaultdict(list)
for c in cands: bk[(c['title'],c['edition_type'])].append(c['number'])
print("ruby確証",len(cands),"巻 /",len(set(c['slug'] for c in cands)),"作")
for (t,et),ns in sorted(bk.items()): print(f"  {t[:30]:32}[{et}] {sorted(ns)}")
