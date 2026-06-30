"""per-case巻抜け確証用 楽天Books lookup。絶版/品切れも取得(outOfStockFlag=1)・1.1s厳守。
使用: _volgap-rakuten-lookup.py "タイトル" [絞り込み語...]
出力: ISBN / title / salesDate / publisher / 価格 (絞り込み語を全部含むitemを優先表示)"""
import sys,os,json,time,urllib.parse,urllib.request
sys.stdout.reconfigure(encoding="utf-8")
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env=dict(l.strip().split("=",1) for l in open(f"{ROOT}/.env.local",encoding="utf-8") if "=" in l and not l.strip().startswith("#"))
title=sys.argv[1]; needles=sys.argv[2:]
URL="https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404"
ORIGIN="https://mangal.shuichi0725.workers.dev"
items=[]
for pg in range(1,7):
    p={"applicationId":env["RAKUTEN_APP_ID"],"accessKey":env.get("RAKUTEN_ACCESS_KEY",""),
       "affiliateId":env.get("RAKUTEN_AFFILIATE_ID",""),"title":title,"booksGenreId":"001001",
       "outOfStockFlag":"1","hits":"30","page":str(pg),"format":"json","formatVersion":"2"}
    req=urllib.request.Request(URL+"?"+urllib.parse.urlencode(p))
    req.add_header("Referer",ORIGIN+"/"); req.add_header("Origin",ORIGIN); req.add_header("User-Agent","Mozilla/5.0")
    try: j=json.loads(urllib.request.urlopen(req,timeout=30).read().decode("utf-8"))
    except Exception as e: print("ERR",e); break
    its=j.get("Items") or []
    if not its: break
    items+=its
    time.sleep(1.1)
def hit(it):
    s=(it.get("title","") or "")+(it.get("subTitle","") or "")
    return needles and all(nd in s for nd in needles)
print(f"=== 楽天 '{title}' {len(items)}件 (絞り込み={needles}) ===")
for it in sorted(items,key=lambda x:not hit(x)):
    mark="★" if hit(it) else " "
    print(f"{mark} {it.get('isbn','') or '------':13} {it.get('salesDate',''):11} {(it.get('publisherName','') or '')[:10]:10} {(it.get('title','') or '')[:50]}")
