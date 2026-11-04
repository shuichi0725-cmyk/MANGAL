"""存在確認で「記事あり」と記録したのに本文を取っていない題(1回目の429で中断した分)の本文だけを取る。
10件ずつ・3秒間隔。 429 は共有の冷却に焼いて即終了。"""
import json, sys, os, time, re, urllib.request, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
from wiki_mag_lib import ROOT, safe_key
from _wiki_host import cooldown_check, cooldown_set, acquire, release
sys.stdout.reconfigure(encoding="utf-8")
L = os.path.join(ROOT, ".cache/magazine-lists")
OUT = os.path.join(L, "wiki")
IDX = os.path.join(L, "wiki-index.json")
idx = json.load(open(IDX, encoding="utf-8"))
ex = json.load(open(os.path.join(L, "wiki-exists.json"), encoding="utf-8"))
UA = {"User-Agent": "MANGAL-research/1.0 (manga catalogue; magazine check)"}
DIS = re.compile(r"\{\{\s*(?:aimai|Aimai|曖昧さ回避|Disambig|disambig|人名の曖昧さ回避)")
todo = [t for t, e in ex.items() if not e["missing"] and t not in idx]
finals = list(dict.fromkeys(ex[t]["final"] for t in todo))
print("本文取得", len(todo), "題 /", len(finals), "記事", flush=True)
cooldown_check(); acquire("mag-wiki")
try:
    got = {}
    for i in range(0, len(finals), 10):
        b = finals[i:i + 10]
        q = urllib.parse.urlencode({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main", "format": "json",
                                    "formatversion": "2", "redirects": "1", "titles": "|".join(b)})
        req = urllib.request.Request("https://ja.wikipedia.org/w/api.php", data=q.encode(), headers=UA)
        try:
            d = json.load(urllib.request.urlopen(req, timeout=60))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                cooldown_set(60, "mag-wiki"); break
            raise
        q2 = d.get("query", {})
        rd = {x["from"]: x["to"] for x in q2.get("redirects", [])}
        nm = {x["from"]: x["to"] for x in q2.get("normalized", [])}
        for p in q2.get("pages", []):
            if p.get("revisions"):
                got[p["title"]] = p["revisions"][0]["slots"]["main"]["content"]
        for t in b:                                   # 要求名 → 最終名(リダイレクト)も引けるように
            f = nm.get(t, t); f = rd.get(f, f)
            if f in got and t not in got:
                got[t] = got[f]
        print(f"  {min(i + 10, len(finals))}/{len(finals)}", flush=True)
        time.sleep(3)
    n = 0
    for t in todo:
        f = ex[t]["final"]; wt = got.get(f)
        if wt is None:
            continue
        fn = safe_key(f) + ".txt"
        open(os.path.join(OUT, fn), "w", encoding="utf-8").write(wt)
        idx[t] = {"final": f, "missing": False, "disambig": bool(DIS.search(wt)), "file": fn}; n += 1
    json.dump(idx, open(IDX, "w", encoding="utf-8"), ensure_ascii=False)
    print("保存", n, "題")
finally:
    release("mag-wiki")
