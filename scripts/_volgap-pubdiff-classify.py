import os
import json,urllib.request,urllib.parse,html,re,time,sys,unicodedata
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
def norm(s): return unicodedata.normalize("NFKC",re.sub(r"[\s　・:：!！?？.,。、\-―~〜()（）\[\]【】'\"]","",str(s or ""))).lower()
def lk(ib):
    q={"operation":"searchRetrieve","query":f'isbn="{ib}"',"recordSchema":"dcndl","maximumRecords":"2"}
    req=urllib.request.Request("https://ndlsearch.ndl.go.jp/api/sru?"+urllib.parse.urlencode(q));req.add_header("User-Agent","Mozilla/5.0")
    try: xml=html.unescape(urllib.request.urlopen(req,timeout=30).read().decode("utf-8"))
    except Exception: return None
    t=re.search(r"<dc:title>.*?<rdf:value>([^<]+)",xml,re.S) or re.search(r"<dc:title>([^<]+)",xml)
    cre=re.findall(r"<dc:creator>([^<]+)",xml)
    return (re.sub(r"<.*?>","",t.group(1)) if t else "", cre[:2])
works=json.load(open(f"{ROOT}/.cache/pubdiff-works.json",encoding="utf-8"))
res=[]
for w in works:
    ib=w["hi"][1]
    r=lk(ib); time.sleep(1.2)
    nt,cre=(r if r else ("",[]))
    ntbase=norm(nt.split(" : ")[0].split(":")[0])
    wt=norm(w["title"])
    same = wt and ntbase and (wt in ntbase or ntbase in wt)
    res.append({**w,"hi_ndl_title":nt,"hi_ndl_cre":cre,"same_title":bool(same)})
json.dump(res,open(f"{ROOT}/.cache/pubdiff-ndl.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
bessaku=[r for r in res if not r["same_title"] and r["hi_ndl_title"]]
same=[r for r in res if r["same_title"]]
noinfo=[r for r in res if not r["hi_ndl_title"]]
print(f"別作(題不一致=除去候補): {len(bessaku)} / 同題(別版=残す): {len(same)} / NDL情報無: {len(noinfo)}")
print("--- 別作候補 ---")
for r in bessaku: print(f"  {r['title'][:14]:16} v{r['hi'][0]} → NDL「{r['hi_ndl_title'][:24]}」{r['hi_ndl_cre']}")
