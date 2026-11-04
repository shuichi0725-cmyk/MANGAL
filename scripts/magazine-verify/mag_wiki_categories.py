"""第2弾の誌名 → ja.wikipedia の雑誌記事のカテゴリ(少年漫画雑誌/少女漫画雑誌/青年漫画雑誌/女性漫画雑誌…)を引く。
記事の有無は全題名ダンプで先に判定し、 在る題だけ prop=categories(本文なし)を 50件ずつ・3秒間隔。
入力 = 引数の JSON(誌名の候補リスト {canon: [候補題...]})。 出力 = .cache/magazine-lists/mag-wiki-cats.json"""
import gzip, json, os, sys, time, urllib.request, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
from wiki_mag_lib import ROOT
from _wiki_host import cooldown_check, cooldown_set, acquire, release
sys.stdout.reconfigure(encoding="utf-8")
L = os.path.join(ROOT, ".cache", "magazine-lists")
cand = json.load(open(sys.argv[1], encoding="utf-8"))
T = set()
with gzip.open(os.path.join(ROOT, ".cache", "jawiki-dump", "jawiki-latest-all-titles-in-ns0.gz"), "rt", encoding="utf-8") as f:
    next(f)
    for ln in f:
        T.add(ln.rstrip("\n"))


def dk(t):
    t = t.strip().replace(" ", "_").replace("　", "_")
    return (t[0].upper() + t[1:]) if t and "a" <= t[0] <= "z" else t


titles = []
for c, ts in cand.items():
    for t in ts:
        if dk(t) in T and t not in titles:
            titles.append(t)
print("候補題", sum(len(v) for v in cand.values()), "/ ダンプに在る", len(titles), flush=True)
out = {}
cooldown_check(); acquire("mag-check")
try:
    for i in range(0, len(titles), 50):
        b = titles[i:i + 50]
        q = urllib.parse.urlencode({"action": "query", "prop": "categories", "cllimit": "max", "format": "json", "formatversion": "2",
                                    "redirects": "1", "titles": "|".join(b)})
        req = urllib.request.Request("https://ja.wikipedia.org/w/api.php", data=q.encode(),
                                     headers={"User-Agent": "MANGAL-research/1.0 (manga catalogue; magazine check)"})
        try:
            d = json.load(urllib.request.urlopen(req, timeout=60))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                cooldown_set(60, "mag-check"); break
            raise
        qq = d.get("query", {})
        nm = {x["from"]: x["to"] for x in qq.get("normalized", [])}
        rd = {x["from"]: x["to"] for x in qq.get("redirects", [])}
        pages = {p["title"]: p for p in qq.get("pages", [])}
        for t in b:
            f = nm.get(t, t); f = rd.get(f, f)
            p = pages.get(f, {})
            out[t] = {"final": f, "cats": [c["title"].replace("Category:", "") for c in p.get("categories", [])]}
        print(f"  {min(i + 50, len(titles))}/{len(titles)}", flush=True)
        time.sleep(3)
finally:
    release("mag-check")
json.dump(out, open(os.path.join(L, "mag-wiki-cats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("保存", len(out))
