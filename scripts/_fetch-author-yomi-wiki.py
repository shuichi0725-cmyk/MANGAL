"""本番フリガナ残(2,819)を Wikipedia 冒頭「名前(よみ)」から取得。 ground-truth。
旧字正規化＋カタカナ読み許可。 hiragana→katakana で author-yomi 形式に。 中断耐性。
"""
import urllib.request, urllib.parse, sys, re, json, os, time
sys.stdout.reconfigure(encoding="utf-8")
ROOT = "C:/Users/shuic/code/MANGAL"
names = json.load(open(ROOT + "/.cache/author-residual-prod.json", encoding="utf-8"))
CACHE = ROOT + "/.cache/author-wiki-yomi.json"
out = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
VAR = str.maketrans({"髙":"高","﨑":"崎","德":"徳","廣":"広","濵":"浜","桒":"桑","槇":"槙","劒":"剣","眞":"真","靏":"鶴","來":"来","國":"国"})

def h2k(s):
    return "".join(chr(ord(c)+0x60) if "ぁ"<=c<="ん" else c for c in s)

def wiki_yomi(name):
    qs = [name, name.translate(VAR), name+" (漫画家)", name.translate(VAR)+" (漫画家)"]
    seen = set()
    for q in qs:
        if q in seen: continue
        seen.add(q)
        url = "https://ja.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
            {"action":"query","prop":"extracts","exintro":1,"explaintext":1,"redirects":1,"format":"json","titles":q})
        try:
            r = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"MANGAL-authoryomi/1.0"}), timeout=20).read().decode("utf-8"))
            for pid, pg in r["query"]["pages"].items():
                if pid == "-1" or "extract" not in pg: continue
                ex = pg["extract"][:160]
                if "漫画" not in ex and "イラスト" not in ex and "作画" not in ex:
                    continue  # 漫画家記事に限定(同名異人除け)
                m = re.search(r"[（(]([ぁ-んァ-ヶー\s]+?)[、，)）]", ex)
                if m:
                    y = h2k(re.sub(r"\s", "", m.group(1)))
                    if re.fullmatch(r"[ァ-ヶー]{2,14}", y):
                        return y
        except Exception:
            pass
    return ""

todo = [n for n in names if n not in out]
print("対象 %d / 既取得 %d / 残 %d" % (len(names), len(out), len(todo)), flush=True)
ok = 0
for i, nm in enumerate(todo, 1):
    out[nm] = wiki_yomi(nm)
    if out[nm]: ok += 1
    time.sleep(0.2)
    if i % 100 == 0:
        json.dump(out, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
        print("  %d/%d ok=%d" % (i, len(todo), ok), flush=True)
json.dump(out, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
print("完了: 取得%d / 試行%d" % (sum(1 for v in out.values() if v), len(out)), flush=True)
