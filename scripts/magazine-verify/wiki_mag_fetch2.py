"""残りの題を軽く引く: ①存在だけ(本文なし)を50件ずつ ②在る記事だけ本文を10件ずつ・3秒間隔。
429 は共有の冷却(_wiki_host)に焼いて即終了。 再実行すれば続きから(wiki-index.json に済みを記録)。"""
import json, sys, os, time, re, urllib.request, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
from wiki_mag_lib import ROOT, safe_key
from _wiki_host import cooldown_check, cooldown_set, acquire, release
sys.stdout.reconfigure(encoding="utf-8")
L = os.path.join(ROOT, ".cache/magazine-lists")
OUT = os.path.join(L, "wiki"); os.makedirs(OUT, exist_ok=True)
IDX = os.path.join(L, "wiki-index.json")
idx = json.load(open(IDX, encoding="utf-8")) if os.path.exists(IDX) else {}
EX = os.path.join(L, "wiki-exists.json")
ex = json.load(open(EX, encoding="utf-8")) if os.path.exists(EX) else {}
UA = {"User-Agent": "MANGAL-research/1.0 (manga catalogue; magazine check)"}
DIS = re.compile(r"\{\{\s*(?:aimai|Aimai|曖昧さ回避|Disambig|disambig|人名の曖昧さ回避)")


def call(params):
    q = urllib.parse.urlencode(dict(params, format="json", formatversion="2", redirects="1"))
    req = urllib.request.Request("https://ja.wikipedia.org/w/api.php", data=q.encode(), headers=UA)
    try:
        return json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            json.dump(idx, open(IDX, "w", encoding="utf-8"), ensure_ascii=False)
            json.dump(ex, open(EX, "w", encoding="utf-8"), ensure_ascii=False)
            cooldown_set(60, "mag-wiki"); release("mag-wiki"); sys.exit(2)
        raise


def resolve(q, t):
    nm = {x["from"]: x["to"] for x in q.get("normalized", [])}
    rd = {x["from"]: x["to"] for x in q.get("redirects", [])}
    f = nm.get(t, t)
    return rd.get(f, f)


def variants(t):
    v = []
    for x in (t.replace("!", "！").replace("?", "？"), t.replace("！", "!").replace("？", "?")):
        if x != t:
            v.append(x)
    v.append(t + " (漫画)")
    base = re.split(r"[ 　]+[-‐－〜~]", t)[0].strip()
    if base and base != t:
        v += [base, base + " (漫画)"]
    return v


cooldown_check(); acquire("mag-wiki")
try:
    need = json.load(open(os.path.join(L, "wiki-need-titles.json"), encoding="utf-8"))
    todo = [t for t in need if t not in idx]
    # 1回目で無かった/曖昧さ回避だった題 → 変種
    for t in need:
        e = idx.get(t)
        if e and (e["missing"] or e.get("disambig")):
            todo += variants(t)
    todo = [t for t in dict.fromkeys(todo) if t not in idx and t not in ex]
    print("存在確認", len(todo), flush=True)
    for i in range(0, len(todo), 50):
        b = todo[i:i + 50]
        d = call({"action": "query", "titles": "|".join(b)}); time.sleep(1.5)
        q = d.get("query", {}); pages = {p["title"]: p for p in q.get("pages", [])}
        for t in b:
            f = resolve(q, t); p = pages.get(f, {})
            ex[t] = {"final": f, "missing": bool(p.get("missing") or p.get("invalid") or not p)}
        json.dump(ex, open(EX, "w", encoding="utf-8"), ensure_ascii=False)
    have = [t for t in todo if not ex[t]["missing"]]
    for t in todo:
        if ex[t]["missing"]:
            idx[t] = {"final": ex[t]["final"], "missing": True}
    print("在る記事", len(have), "→ 本文取得", flush=True)
    finals = list(dict.fromkeys(ex[t]["final"] for t in have))
    got = {}
    for i in range(0, len(finals), 10):
        b = finals[i:i + 10]
        d = call({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main", "titles": "|".join(b)}); time.sleep(3)
        for p in d.get("query", {}).get("pages", []):
            if p.get("revisions"):
                got[p["title"]] = p["revisions"][0]["slots"]["main"]["content"]
        print(f"  {min(i + 10, len(finals))}/{len(finals)}", flush=True)
    for t in have:
        f = ex[t]["final"]; wt = got.get(f)
        if wt is None:
            continue
        fn = safe_key(f) + ".txt"
        open(os.path.join(OUT, fn), "w", encoding="utf-8").write(wt)
        idx[t] = {"final": f, "missing": False, "disambig": bool(DIS.search(wt)), "file": fn}
    json.dump(idx, open(IDX, "w", encoding="utf-8"), ensure_ascii=False)
    print("済み", len(idx))
finally:
    release("mag-wiki")
