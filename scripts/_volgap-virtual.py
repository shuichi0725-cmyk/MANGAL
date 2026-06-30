"""【テスト環境の巻抜けフィルタを本番DBで仮想再現】
未promoteのseed(種4 supplement+auto / series-merge手動+auto)を本番manga.v2に仮想適用し、
build-list-index と同じ vol_gap 判定(=ある版で max-min+1 > 巻数 の穴)を再計算。
promote(~90分)を待たず「修正後に巻抜けが何件残るか・どの作のどの巻か」を素早く出す。
冪等: 既promote反映分の種4/mergeは no-op(既に巻が在る)、新規分だけ穴を埋める。
使用: _volgap-virtual.py [--list] [--limit N]  (--list=残gapを全部TSV出力)"""
import sys,os,re,json,sqlite3,yaml
from collections import defaultdict
sys.stdout.reconfigure(encoding="utf-8")
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB=f"{ROOT}/.cache/db-v2.sqlite"
LIST="--list" in sys.argv
LIMIT=int(sys.argv[sys.argv.index("--limit")+1]) if "--limit" in sys.argv else 0
def norm(s): return re.sub(r"[^0-9X]","",str(s or "").upper())
con=sqlite3.connect(DB); cur=con.cursor()
key2sid={sk:sid for sid,sk in cur.execute("SELECT id,series_key FROM series")}
def isbn_keys(isbns):
    s=set()
    for ib in isbns:
        for r in cur.execute("SELECT se.series_key FROM volumes v JOIN editions e ON e.id=v.edition_id JOIN series se ON se.id=e.series_id WHERE v.isbn13=?",(ib,)): s.add(r[0])
    return s
_sidvols={}
def sid_typevols(sid):
    if sid not in _sidvols:
        rows=[(t,n) for t,n in cur.execute("SELECT e.type,v.number FROM volumes v JOIN editions e ON e.id=v.edition_id WHERE e.series_id=? AND v.number IS NOT NULL",(sid,))]
        _sidvols[sid]=rows
    return _sidvols[sid]

# --- merge groups (union-find over merge_keys: manual yml + auto json) ---
parent={}
def find(x):
    parent.setdefault(x,x)
    while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]
    return x
def union(a,b):
    ra,rb=find(a),find(b)
    if ra!=rb: parent[rb]=ra
def add_merges(keys_list):
    for ks in keys_list:
        ks=[k for k in ks if k in key2sid]
        for k in ks[1:]: union(ks[0],k)
my=yaml.safe_load(open(f"{ROOT}/data/seeds/series-merge.yml",encoding="utf-8")) or []
add_merges([e.get("merge_keys") or [] for e in my])
auto=json.load(open(f"{ROOT}/data/seeds/series-merge-auto.json",encoding="utf-8")).get("merges",[])
add_merges([e.get("merge_keys") or [] for e in auto])
group=defaultdict(list)
for k in list(parent): group[find(k)].append(k)
key2group={k:find(k) for k in parent}

# --- 種4 (manual + auto): series_keys -> numbers (with edition_type) ---
seed4=defaultdict(list)  # frozenset(series_keys) handled per-key: key -> [(type,number)]
def load_seed4(path):
    d=yaml.safe_load(open(path,encoding="utf-8")) or {}
    for e in d.get("volumes",[]):
        et=e.get("edition_type") or "standard"; n=e.get("number")
        if n is None: continue
        for k in (e.get("series_keys") or []):
            seed4[k].append((et,int(n)))
load_seed4(f"{ROOT}/data/seeds/volumes-supplement.yml")
load_seed4(f"{ROOT}/data/seeds/volumes-supplement-auto.yml")

# --- edition-overrides (奇子型=版を完全置換) ---
edov=json.load(open(f"{ROOT}/data/seeds/edition-overrides.json",encoding="utf-8"))

# --- page-dedup (重複ページ=本番でdrop→gap計上しない) ---
_pd=yaml.safe_load(open(f"{ROOT}/data/seeds/page-dedup.yml",encoding="utf-8")) or {}
dedup_drop={e["drop"] for e in _pd.get("dedup",[]) if e.get("drop")}

slugs=[l.rstrip("\n").split("\t")[0] for l in open(f"{ROOT}/docs/production-diagnostics/vol_gap.tsv",encoding="utf-8")][1:]
if LIMIT: slugs=slugs[:LIMIT]

def has_gap(typevols):
    by=defaultdict(set)
    for t,n in typevols: by[t].add(n)
    for t,ns in by.items():
        ns=sorted(ns)
        if len(ns)>=2 and ns[-1]-ns[0]+1>len(ns): return True,by
    return False,by
def gap_detail(by):
    out=[]
    for t,ns in by.items():
        ns=sorted(ns)
        if len(ns)>=2 and ns[-1]-ns[0]+1>len(ns):
            miss=[n for n in range(ns[0],ns[-1]+1) if n not in ns]
            out.append((t,miss))
    return out

before_gap=0; after_gap=0; closed=[]; remain=[]
for slug in slugs:
    if slug in dedup_drop: continue  # 本番でpage-dedup drop=表示されない
    p=f"{ROOT}/data/manga.v2/{slug}.yml"
    if not os.path.exists(p): continue
    d=yaml.safe_load(open(p,encoding="utf-8")); eds=d.get("editions") or []
    tv=[(e.get("type") or "standard",v.get("number")) for e in eds for v in (e.get("volumes") or []) if v.get("number")]
    bg,_=has_gap(tv)
    # edition-overrides(奇子型)= 版を完全置換して仮想適用
    if slug in edov:
        oeds=edov[slug].get("editions") or []
        tv=[(e.get("type") or "standard",v.get("number")) for e in oeds for v in (e.get("volumes") or []) if v.get("number")]
    if bg: before_gap+=1
    # virtual apply
    isbns=[i for i in (norm(v.get("isbn13")) for e in eds for v in (e.get("volumes") or []) if v.get("isbn13")) if i]
    skeys=isbn_keys(isbns)
    tv2=list(tv)
    # 種4
    seen4=set()
    for k in skeys:
        for tn in seed4.get(k,[]):
            if (k,tn) not in seen4: seen4.add((k,tn)); tv2.append(tn)
    # merge partners
    groups={key2group[k] for k in skeys if k in key2group}
    partner_keys=set()
    for g in groups:
        for k in group[g]: partner_keys.add(k)
    partner_keys-=skeys
    for k in partner_keys:
        sid=key2sid.get(k)
        if sid: tv2.extend(sid_typevols(sid))
        # 種4 on partner keys too
        for tn in seed4.get(k,[]): tv2.append(tn)
    ag,by2=has_gap(tv2)
    if ag: after_gap+=1; remain.append((slug,d.get("title",""),gap_detail(by2)))
    elif bg: closed.append((slug,d.get("title","")))

print(f"=== 巻抜け仮想再現(seed適用後) ===")
print(f"対象 {len(slugs)} 作")
print(f"適用前 gap: {before_gap}")
print(f"適用後 gap: {after_gap}  (closed {len(closed)})")
if LIST:
    with open(f"{ROOT}/docs/production-diagnostics/vol_gap_virtual_remain.tsv","w",encoding="utf-8") as f:
        f.write("slug\ttitle\tremaining_gaps\n")
        for slug,t,gd in remain:
            f.write(f"{slug}\t{t}\t{';'.join(f'{tp}:{m}' for tp,m in gd)}\n")
    print(f"→ docs/production-diagnostics/vol_gap_virtual_remain.tsv ({len(remain)})")
