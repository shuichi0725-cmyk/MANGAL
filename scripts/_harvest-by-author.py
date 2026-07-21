"""★全部取得: 全mangakaをauthor検索で一周 → 日付override + 完全item(書影/Kana/価格)をdelta保存。
取得し忘れゼロ設計: 全著者×全ページ×全item。resumable(done管理)・429リトライ・1.3秒/req。"""
import json,os,re,time,urllib.request,urllib.parse,sqlite3,sys
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
env={}
for ln in open(ROOT+"/.env.local",encoding="utf-8"):
    if "=" in ln: k,v=ln.split("=",1); env[k.strip()]=v.strip()
REF=env.get("RAKUTEN_REFERER","https://github.com/")
from urllib.parse import urlparse
o=urlparse(REF)
OVF=ROOT+"/data/seeds/release-date-full.json"
DONEF=ROOT+"/.cache/harvest-author-done.json"
DELTAF=ROOT+"/.cache/rakuten-isbn-delta.jsonl"
OV=json.load(open(OVF,encoding="utf-8"))
done=set(json.load(open(DONEF,encoding="utf-8"))) if os.path.exists(DONEF) else set()
# gap集合(種2 月のみ/抜け = 日付overrideの対象)
con=sqlite3.connect("file:"+ROOT+"/.cache/db-v2.sqlite?mode=ro",uri=True); con.text_factory=lambda b:b.decode("utf-8","replace")
gap=set(ib for rd,ib in con.execute("SELECT release_date,isbn13 FROM volumes") if ib and ((not str(rd or "")) or re.match(r"^\d{4}-\d{2}$",str(rd or ""))))
# 全mangaka名(dedup・空/明白junk除外)
authors=sorted(set(n for (n,) in con.execute("SELECT DISTINCT name FROM mangaka") if n and len(n)>=2 and not re.match(r"^[\d\s]+$",n)))
todo=[a for a in authors if a not in done]
print(f"著者総数{len(authors)} / 残{len(todo)} / gap対象ISBN{len(gap)} / override開始{len(OV)}",flush=True)
def search(author,page):
    p={"applicationId":env["RAKUTEN_APP_ID"],"accessKey":env.get("RAKUTEN_ACCESS_KEY",""),"affiliateId":env.get("RAKUTEN_AFFILIATE",""),"format":"json","formatVersion":"2","author":author,"booksGenreId":"001001","hits":30,"page":page,"outOfStockFlag":1}
    u="https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?"+urllib.parse.urlencode(p)
    for attempt in range(5):
        try:
            d=json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={"Referer":REF,"Origin":o.scheme+"://"+o.netloc,"User-Agent":"M/1"}),timeout=25).read())
            time.sleep(1.3); return d
        except urllib.error.HTTPError as e:
            if e.code==429: time.sleep(8+attempt*4)
            else: time.sleep(2); return {}
        except Exception: time.sleep(2)
    return {}
def parse(sd):
    m=re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日",str(sd or ""))
    return "%s-%02d-%02d"%(m.group(1),int(m.group(2)),int(m.group(3))) if m else None
delta=open(DELTAF,"a",encoding="utf-8")
added=books=0
for i,author in enumerate(todo,1):
    page=1
    while page<=100:
        d=search(author,page)
        items=d.get("Items") or []; pc=d.get("pageCount") or 1
        for it in items:
            delta.write(json.dumps({"isbn":it.get("isbn"),"item":it},ensure_ascii=False)+"\n"); books+=1  # ★全item保存
            ib=it.get("isbn"); fd=parse(it.get("salesDate",""))
            if ib in gap and fd and ib not in OV: OV[ib]=fd; added+=1
        if page>=pc: break
        page+=1
    done.add(author)
    if i%50==0:
        delta.flush()
        json.dump(sorted(done),open(DONEF,"w",encoding="utf-8"),ensure_ascii=False)
        json.dump(OV,open(OVF,"w",encoding="utf-8"),ensure_ascii=False,separators=(",",":"))
        print(f"  著者{i}/{len(todo)} 日付追加{added} 全item{books} override{len(OV)}",flush=True)
delta.close()
json.dump(sorted(done),open(DONEF,"w",encoding="utf-8"),ensure_ascii=False)
json.dump(OV,open(OVF,"w",encoding="utf-8"),ensure_ascii=False,separators=(",",":"))
print(f"完了: 日付追加{added} / 全item保存{books} / override{len(OV)} / 著者done{len(done)}",flush=True)
