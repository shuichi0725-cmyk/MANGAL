"""1冊≠1巻(solo_nonfirst)断片の本編mergeを分析。
各断片(1巻だけ・巻番号≠1)について、種2で「同title(name:token厳密一致)+著者重複+巻数が断片より多い」本編sidを探す。
あれば merge候補(series-merge.yml)。 title不一致/著者不一致/本編不在 は skip(spinoff/homonym/真の単巻)。
dry-run=表示 / --apply=series-merge.yml追記。"""
import sys, re, json, sqlite3, unicodedata, os, yaml
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
APPLY = "--apply" in sys.argv

def norm(s):
    return re.sub(r"[\s　・,，\.。、:：;!！?？()（）\[\]【】/／\-~〜～]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()

def title_tokens(series_key):
    # name: token のみ(著者名も含むが title照合は集合一致で吸収)。 sub:は除外(spinoff判別)
    return {norm(m) for m in re.findall(r"name:([^|]+)", series_key or "")}

con = sqlite3.connect(DB); cur = con.cursor()
# 種2 全series: sid, series_key, 著者集合, 巻数
print("種2 index構築中...", flush=True)
sid_key = {sid: sk for sid, sk in cur.execute("SELECT id, series_key FROM series")}
sid_vols = {}
for sid, c in cur.execute("SELECT e.series_id, COUNT(v.id) FROM volumes v JOIN editions e ON e.id=v.edition_id GROUP BY e.series_id"):
    sid_vols[sid] = c
sid_au = {}
for sid, nm in cur.execute("SELECT sa.series_id, m.name FROM series_authors sa JOIN mangaka m ON m.id=sa.mangaka_id"):
    sid_au.setdefault(sid, set()).add(nm)
# title token → sids
tok_sids = {}
for sid, sk in sid_key.items():
    for t in title_tokens(sk):
        if len(t) >= 2:
            tok_sids.setdefault(t, []).append(sid)

def frag_sid_of_isbn(ib):
    r = cur.execute("SELECT e.series_id FROM volumes v JOIN editions e ON e.id=v.edition_id WHERE v.isbn13=?", (ib,)).fetchone()
    return r[0] if r else None

rows = [l.rstrip("\n").split("\t") for l in open(ROOT/"docs"/"production-diagnostics"/"solo_nonfirst.tsv", encoding="utf-8")][1:]
cands = {}   # frozenset(keys) -> info
skips = {"no_main": 0, "title_only": 0}
for r in rows:
    sl, title = r[0], r[1]
    p = ROOT/"data"/"manga.v2"/f"{sl}.yml"
    if not p.exists(): continue
    d = yaml.safe_load(open(p, encoding="utf-8"))
    isbns = [re.sub(r"\D","",str(v.get("isbn13") or "")) for e in d.get("editions",[]) for v in e.get("volumes",[]) if v.get("isbn13")]
    fsid = next((frag_sid_of_isbn(i) for i in isbns if frag_sid_of_isbn(i)), None)
    if fsid is None: continue
    fkey = sid_key.get(fsid)
    fau = sid_au.get(fsid, set()) or {a.get("name") for a in d.get("authors",[])}
    fvols = sid_vols.get(fsid, 1)
    nt = norm(title)
    # 本編候補: 同title token + 著者重複 + 巻数 > 断片
    best = None
    for cs in set(tok_sids.get(nt, [])):
        if cs == fsid: continue
        if nt not in title_tokens(sid_key.get(cs)): continue   # title厳密
        if not (sid_au.get(cs, set()) & fau): continue          # 著者重複
        if sid_vols.get(cs, 0) <= fvols: continue               # 本編=巻数多い
        if best is None or sid_vols.get(cs,0) > sid_vols.get(best,0): best = cs
    if best is None:
        skips["no_main"] += 1; continue
    kk = tuple(sorted({fkey, sid_key[best]}))
    cands[kk] = {"title": title, "frag": fkey, "main": sid_key[best], "main_vols": sid_vols.get(best), "frag_slug": sl}

print(f"solo断片 {len(rows)} / 本編mergeできる候補 {len(cands)} / 本編不在(skip) {skips['no_main']}")
print("=== merge候補(断片→本編統合) サンプル ===")
for kk, m in list(cands.items())[:25]:
    print(f"  {m['title'][:24]:26} 断片→本編({m['main_vols']}巻) {m['main'][:42]}")
json.dump([{"title": m["title"], "merge_keys": list(k)} for k, m in cands.items()], open(ROOT/".cache"/"solo-merge-candidates.json","w",encoding="utf-8"), ensure_ascii=False)

if APPLY:
    mp = ROOT/"data"/"seeds"/"series-merge.yml"
    ex = yaml.safe_load(open(mp, encoding="utf-8")) or []
    for kk, m in cands.items():
        ex.append({"main": m["title"], "merge_keys": list(kk),
                   "note": f"1冊≠1巻 断片を本編({m['main_vols']}巻)に統合。title厳密一致+著者重複確認・spinoff除外。2026-06-29"})
    yaml.safe_dump(ex, open(mp,"w",encoding="utf-8"), allow_unicode=True, sort_keys=False, width=4096)
    print(f"APPLIED: series-merge.yml に {len(cands)}群 追記")
