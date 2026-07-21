"""安全アンソロ270群を種2から統合(one-page-all)→.preview-dataに生成(テスト点検用)。_anthology:true付与。"""
import yaml,sqlite3,re,unicodedata,os,pykakasi
import os; ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); PREV=ROOT+"/.preview-data/manga"
kks=pykakasi.kakasi()
_NUM=re.compile(r"^[-+]?(\d[\d_]*|\d*\.\d+([eE][-+]?\d+)?)$")
def _rep(d,data):
    return d.represent_scalar("tag:yaml.org,2002:str",data,style="'") if (_NUM.match(data) or data.lower() in("true","false","null","yes","no","on","off","~")) else d.represent_scalar("tag:yaml.org,2002:str",data)
yaml.add_representer(str,_rep,Dumper=yaml.SafeDumper)
def kana_slug(t):
    r=kks.convert(str(t or "")); s="-".join(x['hepburn'] for x in r if x['hepburn'].strip())
    s=re.sub(r"[^a-z0-9]+","-",s.lower()).strip("-")
    return s[:70] or "anthology"
def yreg(s):
    m=re.search(r"(\d{4})",str(s or "")); 
    return int(m.group(1)) if m else 2000
ans=yaml.safe_load(open(ROOT+"/data/seeds/anthology-merge.yml",encoding="utf-8"))["anthologies"]
safe=[a for a in ans if a.get("safe")]
con=sqlite3.connect("file:"+ROOT+"/.cache/db-v2.sqlite?mode=ro",uri=True); con.text_factory=lambda b:b.decode("utf-8","replace")
made=0; used=set()
for a in safe:
    vols=[]; auths=[]
    for sid in a["sids"]:
        for n,ib,rd,cv in con.execute("SELECT v.number,v.isbn13,v.release_date,v.cover_url FROM volumes v JOIN editions e ON v.edition_id=e.id WHERE e.series_id=? ORDER BY v.number",(sid,)):
            vols.append({"isbn13":ib,"release_date":rd,"cover_url":cv,"_d":rd or ""})
        for (nm,) in con.execute("SELECT m.name FROM series_authors sa JOIN mangaka m ON sa.mangaka_id=m.id WHERE sa.series_id=?",(sid,)):
            if nm and nm not in auths: auths.append(nm)
    if not vols: continue
    vols.sort(key=lambda v:v["_d"])
    for i,v in enumerate(vols,1): v["number"]=i; v.pop("_d",None)
    title=a["title"]; slug=kana_slug(title)
    base=slug; k=1
    while slug in used: k+=1; slug=base+"-"+str(k)
    used.add(slug)
    yr=min((yreg(v.get("release_date")) for v in vols if v.get("release_date")),default=2000)
    doc={"slug":slug,"title":title,"title_kana":"".join(x["kana"] for x in kks.convert(title)),
        "title_romaji":slug.replace("-"," "),"year_started":yr,"year_ended":None,"status":"completed",
        "authors":[{"name":n,"role":"artist"} for n in (auths[:6] or [{"name":"アンソロジー"}])] if auths else [{"name":"アンソロジー","role":"artist"}],
        "original_authors":[],"credits":[],"publisher":"(unknown)","publishers":[],
        "demographic":"other","genres":["comedy"],"genres_provisional":True,
        "first_volume_date":vols[0].get("release_date"),"synopsis":"",
        "catch":None,"_anthology":True,"_franchise":a.get("franchise"),
        "editions":[{"type":"standard","label":"アンソロジー","volumes":vols,"publisher":"(unknown)"}]}
    if doc["catch"] is None: doc.pop("catch")
    yaml.safe_dump(doc,open(PREV+"/"+slug+".yml","w",encoding="utf-8"),allow_unicode=True,sort_keys=False)
    made+=1
print("アンソロpreview生成: "+str(made)+"群")
