"""当月+未来の月のみ(発売日カレンダー不足・新刊・harvest無)をライブ楽天で完全日化→overrideへ統合。"""
import sqlite3,re,json,os,time,urllib.request,urllib.parse,sys
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
env={}
for ln in open(ROOT+"/.env.local",encoding="utf-8"):
    if "=" in ln: k,v=ln.split("=",1); env[k.strip()]=v.strip()
REF=env.get("RAKUTEN_REFERER","https://github.com/")
from urllib.parse import urlparse
o=urlparse(REF)
ov=json.load(open(ROOT+"/data/seeds/release-date-full.json",encoding="utf-8"))
con=sqlite3.connect("file:"+ROOT+"/.cache/db-v2.sqlite?mode=ro",uri=True); con.text_factory=lambda b:b.decode("utf-8","replace")
need=[ib for rd,ib in con.execute("SELECT release_date,isbn13 FROM volumes") if ib and re.match(r"^\d{4}-\d{2}$",str(rd or "")) and str(rd)>="2026-06" and ib not in ov]
print(f"ライブ対象: {len(need)}件",flush=True)
def rk(isbn):
    p={"applicationId":env["RAKUTEN_APP_ID"],"accessKey":env.get("RAKUTEN_ACCESS_KEY",""),"affiliateId":env.get("RAKUTEN_AFFILIATE",""),"format":"json","formatVersion":"2","isbn":isbn,"outOfStockFlag":1}
    u="https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?"+urllib.parse.urlencode(p)
    try:
        d=json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={"Referer":REF,"Origin":o.scheme+"://"+o.netloc,"User-Agent":"M/1"}),timeout=25).read())
        time.sleep(1.0); its=d.get("Items") or []
        return its[0].get("salesDate","") if its else ""
    except Exception: time.sleep(1.0); return ""
def parse(sd):
    m=re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日",str(sd or ""))
    return "%s-%02d-%02d"%(m.group(1),int(m.group(2)),int(m.group(3))) if m else None
added=0
for i,ib in enumerate(need,1):
    fd=parse(rk(ib))
    if fd: ov[ib]=fd; added+=1
    if i%30==0: print(f"  {i}/{len(need)} 追加{added}",flush=True)
json.dump(ov,open(ROOT+"/data/seeds/release-date-full.json","w",encoding="utf-8"),ensure_ascii=False,separators=(",",":"))
print(f"完了: ライブ追加 {added} / override総数 {len(ov)}",flush=True)
