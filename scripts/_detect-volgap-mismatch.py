"""巻抜け作の中の誤マッチ(別作の巻が混入)を検出。各巻のISBN→実題名(harvest)が作品題と乖離=混入候補。
title厳密でなく base一致で判定、英↔カナ表記揺れは著者一致で吸収。 per-case精査の対象を出す。"""
import json, re, os, unicodedata, yaml
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
tmap = json.load(open(f"{ROOT}/.cache/isbn-title-map.json", encoding="utf-8"))
amap = json.load(open(f"{ROOT}/.cache/isbn-author-map.json", encoding="utf-8"))

def norm(s):
    return re.sub(r"[\s　・,，\.。、:：;!！?？()（）\[\]【】/／\-~〜]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()

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
            rt = tmap.get(ib, "")
            if not rt:
                continue
            nrt = norm(rt)
            # 作品題が実題名に含まれない = 別作疑い(英カナ揺れ救済: 著者一致なら除外)
            if wt not in nrt:
                ra = amap.get(ib, "")
                au_ok = bool(ra) and any(wa and wa in norm(ra) for wa in wau)
                if not au_ok:
                    mis.append((v.get("number"), ib, rt[:32], ra[:16]))
    if mis:
        hits.append((sl, d.get("title", ""), len(d.get("editions", [])), mis))

hits.sort(key=lambda x: -len(x[3]))
print(f"巻抜け{len(slugs)}作中、誤マッチ(別作混入)候補: {len(hits)}作")
for sl, t, ned, mis in hits[:30]:
    print(f"■ {t[:24]:26} ({sl})")
    for num, ib, rt, ra in mis[:4]:
        print(f"     vol{num} 実題[{rt}] 著[{ra}]")
json.dump([(sl, t, mis) for sl, t, ned, mis in hits], open(f"{ROOT}/.cache/volgap-mismatch.json", "w", encoding="utf-8"), ensure_ascii=False)
