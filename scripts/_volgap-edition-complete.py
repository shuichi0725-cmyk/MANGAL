"""clean多版作(全巻ISBN有)の各版を、同ISBNブロック(9桁prefix)+残差題完全一致でNDLから完成。
種2 edition-type誤分類でdedup消失した巻(キカイダー型)を版正規化で救済。
慎重: ①同版ブロックのみ ②残差題完全一致(外伝/別作排除) ③既存巻のISBN/日付は保持・NDLは欠番補完のみ
④巻番号が現状より増える版のみ出力。レビュー用にdry出力→人が確認後 --apply。
使用: _volgap-edition-complete.py [--apply]"""
import sys,os,re,json,sqlite3,yaml
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import _rakuten_match_lib as L
sys.stdout.reconfigure(encoding="utf-8")
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPLY="--apply" in sys.argv
def ni(s): return re.sub(r"[^0-9X]","",str(s or "").upper())
def fdate(s):
    s=str(s or "").replace(".","-"); m=re.match(r"(\d{4})(?:-(\d{1,2}))?",s)
    return f"{m.group(1)}-{int(m.group(2)):02d}" if (m and m.group(2)) else (m.group(1) if m else "")
ndl={}
for l in open(f"{ROOT}/.cache/volgap-ndl.jsonl",encoding="utf-8"):
    o=json.loads(l); ndl[o["slug"]]=o.get("records",[])
slugs=json.load(open(f"{ROOT}/.cache/clean-multiedition.json",encoding="utf-8"))
overrides={}; report=[]
for slug in slugs:
    p=f"{ROOT}/data/manga.v2/{slug}.yml"
    if not os.path.exists(p): continue
    d=yaml.safe_load(open(p,encoding="utf-8")); eds=d.get("editions") or []
    wbase=L.norm(d.get("title",""))
    # ★版間でISBN 9桁prefix重複する作はskip(ブロックで版区別不可=別版引き込み危険)
    pref_by_ed=[set(ni(v.get("isbn13"))[:9] for v in (e.get("volumes") or []) if v.get("isbn13") and len(ni(v.get("isbn13")))==13) for e in eds]
    seen=set(); shared=False
    for ps in pref_by_ed:
        if ps & seen: shared=True; break
        seen|=ps
    if shared: continue
    # ndl by vol with residual-base match
    recs=[]
    for r in ndl.get(slug,[]):
        ib=ni(r.get("isbn"))
        if len(ib)!=13: continue
        mn=re.search(r"\d+",(r.get("volume") or "").strip())
        if not mn: continue
        nt=(r.get("ndl_title","") or "").split(" : ")[0]
        _v,_res=L.parse_vol(L.clean_title(nt))
        if wbase and L.norm(_res)!=wbase: continue
        recs.append((int(mn.group()),ib,fdate(r.get("date"))))
    new_eds=[]; changed=False; rep_lines=[]
    for e in eds:
        et=e.get("type") or "standard"
        exist={v.get("number"):v for v in (e.get("volumes") or []) if v.get("number")}
        pre9=set(ni(v.get("isbn13"))[:9] for v in exist.values() if v.get("isbn13") and len(ni(v.get("isbn13")))==13)
        if not pre9: new_eds.append(e); continue
        # NDL vols in this block
        blockvols={}
        for n,ib,dt in recs:
            if ib[:9] in pre9: blockvols.setdefault(n,(ib,dt))
        allnums=sorted(set(exist)|set(blockvols))
        vols=[]
        for n in allnums:
            if n in exist:
                vols.append(exist[n])  # 既存保持
            else:
                ib,dt=blockvols[n]
                vols.append({"number":n,"isbn13":ib,"cover_url":None,"release_date":dt})
                changed=True
        # only if added
        new_eds.append({"type":et,"label":e.get("label") or "","publisher":e.get("publisher") or "","imprint":e.get("imprint") or "","volumes":vols})
        added=[n for n in allnums if n not in exist]
        if added: rep_lines.append(f"  [{et}] +{added} (既{len(exist)}→{len(vols)})")
    if changed:
        ov={"editions":new_eds}
        if d.get("authors"): ov["authors"]=[{"name":a.get("name"),"role":a.get("role")} for a in d["authors"]]
        overrides[slug]=ov
        report.append(f"{slug} | {d.get('title','')[:24]}\n"+"\n".join(rep_lines))
print(f"完成対象 {len(overrides)}作")
open(f"{ROOT}/.cache/edition-complete-report.txt","w",encoding="utf-8").write("\n".join(report))
json.dump(overrides,open(f"{ROOT}/.cache/edition-complete.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("→ .cache/edition-complete-report.txt / .json")
if APPLY:
    base=json.load(open(f"{ROOT}/data/seeds/edition-overrides.json",encoding="utf-8"))
    for k,v in overrides.items():
        if k not in base: base[k]=v   # 既存override(手動)は上書きしない
    json.dump(base,open(f"{ROOT}/data/seeds/edition-overrides.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
    print(f"applied {len(overrides)} (既存override温存)")
