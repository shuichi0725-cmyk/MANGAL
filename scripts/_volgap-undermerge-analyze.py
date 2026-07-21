import json,sqlite3,os,re,yaml
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
con=sqlite3.connect(f"{ROOT}/.cache/db-v2.sqlite"); cur=con.cursor()
def norm(s): return re.sub(r"[^0-9X]","",str(s or "").upper())
def reg(ib):
    ib=norm(ib)
    if not ib.startswith("9784") or len(ib)!=13: return None
    b=ib[4:12]; n=int(b[:2])
    return b[:2] if n<=19 else b[:3] if n<=69 else b[:4] if n<=84 else b[:5] if n<=89 else b[:6] if n<=94 else b[:7]
def series_of_isbn(ib):
    r=cur.execute("SELECT se.series_key,se.title FROM volumes v JOIN editions e ON e.id=v.edition_id JOIN series se ON se.id=e.series_id WHERE v.isbn13=? LIMIT 1",(ib,)).fetchone()
    return r
ndl={}
for l in open(f"{ROOT}/.cache/volgap-ndl.jsonl",encoding="utf-8"):
    o=json.loads(l); ndl[o["slug"]]=o.get("records",[])
out=[]
for slug,recs in ndl.items():
    p=f"{ROOT}/data/manga.v2/{slug}.yml"
    if not os.path.exists(p): continue
    d=yaml.safe_load(open(p,encoding="utf-8")); eds=d.get("editions") or []
    isbns=[i for i in (norm(v.get("isbn13")) for e in eds for v in (e.get("volumes") or []) if v.get("isbn13")) if i]
    from collections import Counter
    pc=Counter(reg(i) for i in isbns if reg(i)); mainpref=pc.most_common(1)[0][0] if pc else None
    # this work's own series_keys
    own=set()
    for ib in isbns:
        for r in cur.execute("SELECT se.series_key FROM volumes v JOIN editions e ON e.id=v.edition_id JOIN series se ON se.id=e.series_id WHERE v.isbn13=?",(ib,)): own.add(r[0])
    nums=sorted({v.get("number") for e in eds for v in (e.get("volumes") or []) if v.get("number")})
    if len(nums)<2: continue
    gaps=[n for n in range(nums[0],nums[-1]+1) if n not in nums]
    if not gaps: continue
    by_vol={}
    for r in recs:
        mn=re.search(r"\d+",(r.get("volume") or "").strip())
        if mn and r.get("isbn"): by_vol.setdefault(int(mn.group()),[]).append(r)
    for n in gaps:
        for r in by_vol.get(n,[]):
            ib=norm(r.get("isbn"))
            if len(ib)!=13 or (mainpref and reg(ib)!=mainpref): continue
            si=series_of_isbn(ib)
            if si and si[0] not in own:  # exists in 種2, different cluster = under-merge
                out.append({"slug":slug,"title":d["title"],"number":n,"isbn13":ib,
                    "other_key":si[0],"other_title":si[1]})
                break
# group by slug
from collections import defaultdict
bys=defaultdict(list)
for o in out: bys[o["slug"]].append(o)
print(f"under-merge works: {len(bys)} / missing-vol instances: {len(out)}")
with open(f"{ROOT}/.cache/undermerge-detail.txt","w",encoding="utf-8") as f:
    for slug,items in sorted(bys.items()):
        t=items[0]["title"]
        f.write(f"\n{slug} [{t}]\n")
        for o in items:
            same = "SAME?" if o["title"][:6] in o["other_title"] or o["other_title"][:6] in o["title"] else "DIFF"
            f.write(f"   v{o['number']} {o['isbn13']} -> 種2:[{o['other_title'][:30]}] ({same})\n")
json.dump(out,open(f"{ROOT}/.cache/undermerge.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("wrote .cache/undermerge-detail.txt")
