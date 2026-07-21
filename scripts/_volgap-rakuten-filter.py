import json,os,re,yaml,sys
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
EXCLUDE_ISBN={"9784832295810"}  # ぼっち外伝
cands=json.load(open(f"{ROOT}/.cache/volgap-rakuten-cands.json",encoding="utf-8"))
from collections import defaultdict
byslug=defaultdict(list)
for c in cands:
    if c["isbn13"] in EXCLUDE_ISBN: continue
    byslug[c["slug"]].append(c)
def pdate(s):
    m=re.match(r"(\d{4})(?:-(\d{1,2}))?",str(s or ""))
    if not m: return None
    return int(m.group(1))*12+(int(m.group(2) or 6)-1)  # months since year0, mid-year if month unknown
safe=[]; defer_work=[]; skip_cand=[]
for slug,cs in byslug.items():
    d=yaml.safe_load(open(f"{ROOT}/data/manga.v2/{slug}.yml",encoding="utf-8"))
    pop=d.get("popularity") or 0
    if pop and pop>=3000:
        defer_work.append((slug,d.get("title",""),len(cs),f"pop{pop}")); continue
    # existing standard seq num->date(months)
    seq={}
    for e in d.get("editions") or []:
        if (e.get("type") or "standard")!="standard": continue
        for v in e.get("volumes") or []:
            if v.get("number") and v.get("release_date"): seq[v["number"]]=pdate(v.get("release_date"))
    candmap={c["number"]:pdate(c["release_date"]) for c in cs}
    allnum=sorted(set(seq)|set(candmap))
    def neighbor_date(n,lo):
        rng=range(n-1,0,-1) if lo else range(n+1,max(allnum)+2)
        for m in rng:
            if m in seq and seq[m] is not None: return seq[m]
            if m in candmap and candmap[m] is not None: return candmap[m]
        return None
    for c in cs:
        n=c["number"]; cd=candmap[n]
        lo=neighbor_date(n,True); hi=neighbor_date(n,False)
        ok=True
        if cd is not None:
            if lo is not None and cd < lo-18: ok=False   # 1.5yr前=版違い
            if hi is not None and cd > hi+18: ok=False
        if ok: safe.append(c)
        else: skip_cand.append((c["title"],n,c["release_date"]))
print(f"安全 {len(safe)}巻 / 人気作後回し {len(defer_work)}作 / 版混在候補skip {len(skip_cand)}")
print("\n=== 人気作後回し ===")
for slug,t,n,r in sorted(defer_work): print(f"  {t[:24]:26} 候補{n} [{r}]")
print("\n=== 版混在でskipした候補 ===")
for t,n,dt in sorted(skip_cand): print(f"  {t[:24]:26} v{n} {dt}")
json.dump(safe,open(f"{ROOT}/.cache/volgap-rakuten-safe.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
print(f"\n安全候補の作品: ",sorted(set(c['title'] for c in safe)))

# 追加: skipのあった作は丸ごとdefer(怪しいは飛ばす)
skipslugs={c2["slug"] for c2 in cands if c2["isbn13"] not in EXCLUDE_ISBN and c2["title"] in {t for t,_,_ in skip_cand}}
# 正確にslug単位で: rebuild
skip_titles={t for t,_,_ in skip_cand}
clean=[c for c in safe if c["title"] not in skip_titles]
deferred_partial=sorted(set(c["title"] for c in safe if c["title"] in skip_titles))
print("\n==== 最終 ====")
print(f"完全クリーン作のみ適用: {len(clean)}巻 / {len(set(c['title'] for c in clean))}作")
print(f"partial-skipで丸ごと後回し: {deferred_partial}")
json.dump(clean,open(f"{ROOT}/.cache/volgap-rakuten-clean.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("作品:",sorted(set(c['title'] for c in clean)))
