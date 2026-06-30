"""巻抜け作の誤マッチ(別作混入)を NDL取得データ + harvest の ISBN→実題名で網羅検出。
各巻のISBN→実題名(NDL優先,harvest補完)が作品題と乖離=別作混入。英↔カナ/ハイフン揺れは著者一致or base一致で除外。"""
import json, re, os, unicodedata, yaml
ROOT = "C:/Users/shuic/code/MANGAL"
# harvest ISBN→題
tmap = json.load(open(f"{ROOT}/.cache/isbn-title-map.json", encoding="utf-8"))
amap = json.load(open(f"{ROOT}/.cache/isbn-author-map.json", encoding="utf-8"))
# NDL ISBN→題(取得データから)
ndl_t = {}
for l in open(f"{ROOT}/.cache/volgap-ndl.jsonl", encoding="utf-8"):
    try:
        d = json.loads(l)
    except Exception:
        continue
    for r in d.get("records", []):
        if r.get("isbn") and r.get("ndl_title"):
            ndl_t.setdefault(r["isbn"], r["ndl_title"])

def norm(s):
    return re.sub(r"[\s　・,，\.。、:：;!！?？()（）\[\]【】/／\-~〜ー上中下前後巻第集]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()

def title_of(ib):
    return tmap.get(ib) or ndl_t.get(ib) or ""

slugs = [l.rstrip("\n").split("\t")[0] for l in open(f"{ROOT}/docs/production-diagnostics/vol_gap.tsv", encoding="utf-8")][1:]
hits = []
for sl in slugs:
    p = f"{ROOT}/data/manga.v2/{sl}.yml"
    if not os.path.exists(p):
        continue
    d = yaml.safe_load(open(p, encoding="utf-8"))
    wt = norm(d.get("title", ""))
    if len(wt) < 2:
        continue
    wau = [norm(a.get("name")) for a in (d.get("authors") or []) + (d.get("original_authors") or []) if a.get("name")]
    mis = []
    for e in d.get("editions", []):
        for v in e.get("volumes", []):
            ib = re.sub(r"\D", "", str(v.get("isbn13") or ""))
            rt = title_of(ib)
            if not rt:
                continue
            nrt = norm(rt)
            # 双方向の包含も乖離も無い = 別作。著者一致なら救済
            if wt not in nrt and nrt not in wt:
                ra = amap.get(ib, "")
                au_ok = bool(ra) and any(wa and wa in norm(ra) for wa in wau)
                if not au_ok:
                    mis.append((v.get("number"), ib, rt[:34], ra[:14]))
    if mis:
        hits.append({"slug": sl, "title": d.get("title", ""), "mis": mis})

hits.sort(key=lambda x: -len(x["mis"]))
print(f"巻抜け{len(slugs)}作 / 誤マッチ(別作混入)候補: {len(hits)}作 (NDL+harvest網羅)")
for h in hits[:50]:
    others = sorted({re.sub(r"[（(].*", "", m[2]).strip() for m in h["mis"]})
    print(f"  {h['title'][:24]:26} ← {others[:2]}")
json.dump(hits, open(f"{ROOT}/.cache/mismatch-ndl.json", "w", encoding="utf-8"), ensure_ascii=False)
