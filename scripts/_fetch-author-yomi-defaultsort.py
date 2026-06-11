"""漢字名著者の読みを Wikipedia DEFAULTSORT(pageprops)から取得。 自前実装・検証付き。
対象=漢字含む名(ローマ字/カナ名は除外)。 search→title一致確認→pageprops.defaultsort→カタカナ化。 中断耐性。
"""
import urllib.request, urllib.parse, sys, re, json, os, time
sys.stdout.reconfigure(encoding="utf-8")
ROOT = "C:/Users/shuic/code/MANGAL"
names = json.load(open(ROOT + "/.cache/author-residual-prod.json", encoding="utf-8"))
CACHE = ROOT + "/.cache/author-defaultsort.json"
out = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
VAR = str.maketrans({"髙":"高","﨑":"崎","德":"徳","廣":"広","濵":"浜","桒":"桑","槇":"槙","劒":"剣","眞":"真","來":"来","國":"国"})
UA = {"User-Agent": "MANGAL-authoryomi/1.0"}

def api(params):
    url = "https://ja.wikipedia.org/w/api.php?" + urllib.parse.urlencode(params)
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read().decode("utf-8"))

def h2k(s):
    return "".join(chr(ord(c)+0x60) if "ぁ"<=c<="ん" else c for c in s)

def fetch(name):
    nn = name.replace(" ", "")
    for q in [name+" 漫画家", name.translate(VAR)+" 漫画家", name, name.translate(VAR)]:
        try:
            sr = api({"action":"query","list":"search","srsearch":q,"srlimit":3,"format":"json"})
            for hit in sr.get("query",{}).get("search",[]):
                title = hit["title"]
                tn = title.split("(")[0].split("（")[0].strip().replace(" ","")
                # title と name が概ね一致(変異字考慮)
                if not (tn == nn or tn == nn.translate(VAR) or nn == tn.translate(VAR)):
                    continue
                pp = api({"action":"query","titles":title,"prop":"pageprops|extracts","exintro":1,"explaintext":1,"format":"json"})
                for _, pg in pp.get("query",{}).get("pages",{}).items():
                    ex = (pg.get("extract") or "")[:200]
                    if not re.search(r"漫画|まんが|イラスト|作画|原作者|小説家|脚本", ex):
                        continue  # 漫画関連記事のみ(同名異人除け)
                    ds = pg.get("pageprops",{}).get("defaultsort","")
                    if ds:
                        y = h2k(re.sub(r"[\s　]", "", ds))
                        if re.fullmatch(r"[ァ-ヶー]{2,14}", y):
                            return y
        except Exception:
            pass
    return ""

todo = [n for n in names if n not in out]
print("漢字名対象 %d / 既取得 %d / 残 %d" % (len(names), len(out), len(todo)), flush=True)
ok = 0
for i, nm in enumerate(todo, 1):
    out[nm] = fetch(nm)
    if out[nm]: ok += 1
    time.sleep(0.25)
    if i % 100 == 0:
        json.dump(out, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
        print("  %d/%d ok=%d" % (i, len(todo), ok), flush=True)
json.dump(out, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
print("完了: 取得%d / 試行%d" % (sum(1 for v in out.values() if v), len(out)), flush=True)
