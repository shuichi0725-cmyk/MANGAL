"""残巻抜けを【楽天全harvest(ローカルキャッシュ)】でper-case確証→種4候補。
_rakuten_match_lib使用=残差題完全一致guard(スピンオフ/外伝/データ本を自然排除=無理にマッチさせない)。
さらに guard: 同出版社prefix(reg) / 種2(db-v2)非存在 / 欠番のみ。
BIG(最大巻>20=人気長編)は除外(後回し)。 confirmableのみ出力。
使用: _volgap-rakuten-harvest.py [--apply]"""
import sys,os,re,json,sqlite3,yaml
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import _rakuten_match_lib as L
sys.stdout.reconfigure(encoding="utf-8")
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPLY="--apply" in sys.argv
def norm_isbn(s): return re.sub(r"[^0-9X]","",str(s or "").upper())
def reg(ib):
    ib=norm_isbn(ib)
    if not ib.startswith("9784") or len(ib)!=13: return None
    b=ib[4:12]; n=int(b[:2])
    return b[:2] if n<=19 else b[:3] if n<=69 else b[:4] if n<=84 else b[:5] if n<=89 else b[:6] if n<=94 else b[:7]
con=sqlite3.connect(f"{ROOT}/.cache/db-v2.sqlite"); cur=con.cursor()
db_isbns={norm_isbn(r[0]) for r in cur.execute("SELECT isbn13 FROM volumes WHERE isbn13 IS NOT NULL")}
def sk_for(isbns):
    s=set()
    for ib in isbns:
        for r in cur.execute("SELECT se.series_key FROM volumes v JOIN editions e ON e.id=v.edition_id JOIN series se ON se.id=e.series_id WHERE v.isbn13=?",(ib,)): s.add(r[0])
    return sorted(s)

# remain list, parse gaps, exclude BIG(max>20)
rows=[l.rstrip("\n").split("\t") for l in open(f"{ROOT}/docs/production-diagnostics/vol_gap_virtual_remain.tsv",encoding="utf-8")][1:]
works=[]
for r in rows:
    if len(r)<3: continue
    slug,title,gaps=r[0],r[1],r[2]
    miss=set(); mx=0
    for seg in gaps.split(";"):
        if ":" not in seg: continue
        for x in re.findall(r"\d+",seg.split(":",1)[1]): miss.add(int(x)); mx=max(mx,int(x))
    works.append((slug,title,sorted(miss)))   # BIG除外撤廃=全remain対象(版混在は後段filterで処理)
print(f"対象(全remain) {len(works)}作")

# build target_bases from production titles
slug2yml={}
bases=set()
for slug,title,miss in works:
    p=f"{ROOT}/data/manga.v2/{slug}.yml"
    if not os.path.exists(p): continue
    d=yaml.safe_load(open(p,encoding="utf-8")); slug2yml[slug]=d
    bases.add(L.norm(d.get("title","")))
print(f"target_bases {len(bases)} / 楽天harvest index構築中...")
index,scanned=L.build_index(bases,progress=lambda n:print(f"  scan {n//1000}k",flush=True) if n%1000000==0 else None)
print(f"index keys {len(index)} (scanned {scanned})")

cands=[]; skipped=0
for slug,title,miss in works:
    d=slug2yml.get(slug)
    if not d: continue
    base=L.norm(d.get("title",""))
    eds=d.get("editions") or []
    isbns=[i for i in (norm_isbn(v.get("isbn13")) for e in eds for v in (e.get("volumes") or []) if v.get("isbn13")) if i]
    from collections import Counter
    pc=Counter(reg(i) for i in isbns if reg(i)); mainpref=pc.most_common(1)[0][0] if pc else None
    sk=sk_for(isbns)
    if not sk: skipped+=1; continue
    for n in miss:
        recs=index.get((base,n),[])
        # same publisher prefix + dated + not in 種2
        ok=[r for r in recs if r.get("date") and reg(r["isbn"])==mainpref and norm_isbn(r["isbn"]) not in db_isbns]
        if not ok: continue
        r=min(ok,key=lambda x:x["date"])
        cands.append({"slug":slug,"series_keys":sk,"number":n,"isbn13":norm_isbn(r["isbn"]),
            "release_date":L.date_str(r["date"]),"publisher":r.get("publisher",""),
            "title":d.get("title"),"cover":r.get("cover",""),"raw":r["raw"]})
print(f"\n確証候補 {len(cands)} (種4追加可) / series_key無 skip {skipped}")
json.dump(cands,open(f"{ROOT}/.cache/volgap-rakuten-cands.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
with open(f"{ROOT}/.cache/volgap-rakuten-cands.txt","w",encoding="utf-8") as f:
    for c in cands: f.write(f"{c['title'][:24]:26} v{c['number']:<3} {c['isbn13']} {c['release_date']:8} {c['publisher'][:12]:14}| 楽天raw:{c['raw'][:34]}\n")
print("→ .cache/volgap-rakuten-cands.json / .txt")
if not APPLY:
    print("\n(--apply で種4 auto へ純粋追加)")
