"""漢字名著者の読み=Wikipedia記事冒頭「名前(よみ、...)」から取得(濁点保持)。名前直後のカッコに限定し誤爆抑制。中断耐性。"""
import urllib.request,urllib.parse,sys,re,json,os,time
sys.stdout.reconfigure(encoding="utf-8")
ROOT="C:/Users/shuic/code/MANGAL"
names=json.load(open(ROOT+"/.cache/author-residual-prod.json",encoding="utf-8"))
CACHE=ROOT+"/.cache/author-introyomi.json"
out=json.load(open(CACHE,encoding="utf-8")) if os.path.exists(CACHE) else {}
VAR=str.maketrans({"髙":"高","﨑":"崎","德":"徳","廣":"広","濵":"浜","桒":"桑","槇":"槙","眞":"真","來":"来","國":"国"})
UA={"User-Agent":"MANGAL-introyomi/1.0"}
def h2k(s): return ''.join(chr(ord(c)+0x60) if 'ぁ'<=c<='ん' else c for c in s)
def fetch(name):
    for q in [name+" 漫画家",name.translate(VAR)+" 漫画家",name]:
        try:
            url="https://ja.wikipedia.org/w/api.php?"+urllib.parse.urlencode({"action":"query","prop":"extracts","exintro":1,"explaintext":1,"redirects":1,"format":"json","titles":q})
            r=json.loads(urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=20).read().decode("utf-8"))
            for pid,pg in r["query"]["pages"].items():
                if pid=="-1" or "extract" not in pg: continue
                ex=pg["extract"][:160]
                if not re.search(r"漫画|まんが|イラスト|作画|原作者|小説家|脚本",ex): continue
                # ★名前(変異字許容)の直後のカッコ内のよみ
                m=re.match(r'.{0,3}?[（(]([ぁ-んァ-ヶー\s]+?)[、，)）]',ex)
                if m:
                    y=h2k(re.sub(r'[\s　]','',m.group(1)))
                    if re.fullmatch(r'[ァ-ヶー]{2,14}',y): return y
        except Exception: pass
    return ""
todo=[n for n in names if n not in out]
print("漢字名対象 %d / 既 %d / 残 %d"%(len(names),len(out),len(todo)),flush=True)
ok=0
for i,nm in enumerate(todo,1):
    out[nm]=fetch(nm)
    if out[nm]: ok+=1
    time.sleep(0.2)
    if i%100==0:
        json.dump(out,open(CACHE,"w",encoding="utf-8"),ensure_ascii=False)
        print("  %d/%d ok=%d"%(i,len(todo),ok),flush=True)
json.dump(out,open(CACHE,"w",encoding="utf-8"),ensure_ascii=False)
print("完了: 取得%d / 試行%d"%(sum(1 for v in out.values() if v),len(out)),flush=True)
