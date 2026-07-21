"""カレンダー日付ライブ補完(manga.v2基点)。発売日残(当月+未来)+最近の創刊(2020-2024 第1巻)。
★取得できる物は全部とる = Rakuten完全itemを rakuten-isbn-delta.jsonl に保存(書影/価格/Kana等も)。日付→override。"""
import json,os,re,time,urllib.request,urllib.parse,sys,yaml
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
env={}
for ln in open(ROOT+"/.env.local",encoding="utf-8"):
    if "=" in ln: k,v=ln.split("=",1); env[k.strip()]=v.strip()
REF=env.get("RAKUTEN_REFERER","https://github.com/")
from urllib.parse import urlparse
o=urlparse(REF)
OV=json.load(open(ROOT+"/data/seeds/release-date-full.json",encoding="utf-8"))
CALD=ROOT+"/.cache/calendar-prod2"
# 対象収集: release 2026-06+ unknown(slug,vol) + launch 2020-2024 unknown(slug→1巻)
tgt={}  # slug -> set(vols)
for fn in os.listdir(CALD+"/release"):
    ym=fn[:-5]
    if ym>="2026-06":
        d=json.load(open(CALD+"/release/"+fn,encoding="utf-8"))
        for slug,vol in d["unknown"]: tgt.setdefault(slug,set()).add(vol)
for fn in os.listdir(CALD+"/launch"):
    ym=fn[:-5]
    if "2020-01"<=ym<="2024-12":
        d=json.load(open(CALD+"/launch/"+fn,encoding="utf-8"))
        for slug in d["unknown"]: tgt.setdefault(slug,set()).add(1)
# manga.v2でISBN解決(override未収のみ)
isbns=[]
for slug,vols in tgt.items():
    p=ROOT+"/data/manga.v2/"+slug+".yml"
    if not os.path.exists(p): continue
    try: d=yaml.safe_load(open(p,encoding="utf-8"))
    except: continue
    for e in (d.get("editions") or []):
        for v in (e.get("volumes") or []):
            if v.get("number") in vols and v.get("isbn13") and v["isbn13"] not in OV:
                isbns.append(v["isbn13"])
isbns=list(dict.fromkeys(isbns))
print(f"ライブ対象ISBN(override未収): {len(isbns)}",flush=True)
def rk(isbn):
    p={"applicationId":env["RAKUTEN_APP_ID"],"accessKey":env.get("RAKUTEN_ACCESS_KEY",""),"affiliateId":env.get("RAKUTEN_AFFILIATE",""),"format":"json","formatVersion":"2","isbn":isbn,"outOfStockFlag":1}
    u="https://openapi.rakuten.co.jp/services/api/BooksBook/Search/20170404?"+urllib.parse.urlencode(p)
    try:
        d=json.loads(urllib.request.urlopen(urllib.request.Request(u,headers={"Referer":REF,"Origin":o.scheme+"://"+o.netloc,"User-Agent":"M/1"}),timeout=25).read())
        time.sleep(1.0); its=d.get("Items") or []
        return its[0] if its else None
    except Exception: time.sleep(1.0); return None
def parse(sd):
    m=re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日",str(sd or ""))
    return "%s-%02d-%02d"%(m.group(1),int(m.group(2)),int(m.group(3))) if m else None
delta=open(ROOT+"/.cache/rakuten-isbn-delta.jsonl","a",encoding="utf-8")
added=savedfull=0
for i,ib in enumerate(isbns,1):
    it=rk(ib)
    if it:
        delta.write(json.dumps({"isbn":ib,"item":it},ensure_ascii=False)+"\n"); savedfull+=1  # ★全部保存
        fd=parse(it.get("salesDate",""))
        if fd: OV[ib]=fd; added+=1
    if i%50==0: print(f"  {i}/{len(isbns)} 日付追加{added} full保存{savedfull}",flush=True)
delta.close()
json.dump(OV,open(ROOT+"/data/seeds/release-date-full.json","w",encoding="utf-8"),ensure_ascii=False,separators=(",",":"))
print(f"完了: 日付追加 {added} / full item保存 {savedfull} / override総数 {len(OV)}",flush=True)
