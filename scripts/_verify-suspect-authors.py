"""疑著者の職業をWikipediaで裏取り。漫画家→keep / 声優・俳優・作家等→remove確定 / 不明→leave。中断耐性。"""
import urllib.request,urllib.parse,sys,re,json,os,time,csv
sys.stdout.reconfigure(encoding="utf-8")
ROOT="C:/Users/shuic/code/MANGAL"
names=[r['疑著者'] for r in csv.DictReader(open(ROOT+"/.cache/suspect-authors.csv",encoding="utf-8-sig"))]
CACHE=ROOT+"/.cache/suspect-verify.json"
out=json.load(open(CACHE,encoding="utf-8")) if os.path.exists(CACHE) else {}
UA={"User-Agent":"MANGAL/1.0"}
MANGA=re.compile(r"漫画家|まんが家|マンガ家|イラストレーター|絵師")
NONM=re.compile(r"声優|俳優|女優|小説家|脚本家|落語家|評論家|学者|教授|歌手|タレント|ミュージシャン|政治家|アナウンサー|野球|格闘家|騎手|お笑い|芸人|歌人|詩人|批評家|社会学者|宗教学者|思想家|編集委員会|バンド|音楽")
def cls(name):
    for q in [name,name+" 漫画家",name+" 人物"]:
        try:
            url="https://ja.wikipedia.org/w/api.php?"+urllib.parse.urlencode({"action":"query","prop":"extracts","exintro":1,"explaintext":1,"redirects":1,"format":"json","titles":q})
            r=json.loads(urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=20).read().decode("utf-8"))
            for pid,pg in r["query"]["pages"].items():
                if pid=="-1" or "extract" not in pg: continue
                ex=pg["extract"][:160]
                if MANGA.search(ex): return "keep(漫画家)"
                if NONM.search(ex): return "remove:"+ (NONM.search(ex).group())
        except Exception: pass
    return "unknown"
todo=[n for n in names if n not in out]
print("疑著者 %d / 既 %d / 残 %d"%(len(names),len(out),len(todo)),flush=True)
rem=0
for i,nm in enumerate(todo,1):
    out[nm]=cls(nm)
    if out[nm].startswith("remove"): rem+=1
    time.sleep(0.2)
    if i%150==0:
        json.dump(out,open(CACHE,"w",encoding="utf-8"),ensure_ascii=False)
        print("  %d/%d remove確定=%d"%(i,len(todo),rem),flush=True)
json.dump(out,open(CACHE,"w",encoding="utf-8"),ensure_ascii=False)
from collections import Counter
c=Counter(v.split(':')[0].split('(')[0] for v in out.values())
print("完了:",dict(c),flush=True)
