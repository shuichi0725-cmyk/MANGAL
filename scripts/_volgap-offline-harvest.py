"""巻抜け作の欠番巻を【キャッシュ済NDL】(.cache/volgap-ndl.jsonl)からオフライン収穫し種4 autoへ純粋追加。
liveNDLを叩かず高速。 guard 4層(=_register-seed4-ndl.pyと同等):
 ①出版社prefix一致(別作/別社混入防止) ②series_key bind(既存ISBN→db-v2)
 ③種2既存ISBN skip(under-merge=取込もれでない) ④巻番号既存 skip。
さらに媒体/別作 guard: ndl_titleに録音資料/映像資料/小説prefix/外伝(題に無い時)→除外候補としてflag。
gap = 全edition union の欠番(=どの版にも無い真の欠け)。 主にMADBラグ(2023+新刊)取込もれを回収。
出力: data/seeds/volumes-supplement-auto.yml に純粋追加(既存entry isbn13 dedup保護) + changelog。
使用: _volgap-offline-harvest.py [--apply]  (dry-run既定)"""
import json,sqlite3,os,re,unicodedata,sys,yaml
from collections import Counter
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPLY="--apply" in sys.argv
ADDED="2026-06-30"
MEDIA=["録音資料","映像資料","ビデオ","DVD","CD-ROM"]
con=sqlite3.connect(f"{ROOT}/.cache/db-v2.sqlite"); cur=con.cursor()
def reg(ib):
    ib=re.sub(r"\D","",str(ib or ""))
    if not ib.startswith("9784") or len(ib)!=13: return None
    b=ib[4:12]; n=int(b[:2])
    return b[:2] if n<=19 else b[:3] if n<=69 else b[:4] if n<=84 else b[:5] if n<=89 else b[:6] if n<=94 else b[:7]
def norm(s): return re.sub(r"[^0-9X]","",str(s or "").upper())
def fmt_date(s):
    s=unicodedata.normalize("NFKC",str(s or "").strip())
    m=re.match(r"(\d{4})[.\-/](\d{1,2})",s)
    if m: return f"{m.group(1)}-{int(m.group(2)):02d}"
    m=re.match(r"(\d{4})(\d{2})$",s)
    if m: return f"{m.group(1)}-{m.group(2)}"
    m=re.match(r"(\d{4})",s); return m.group(1) if m else ""
db_isbns={norm(r[0]) for r in cur.execute("SELECT isbn13 FROM volumes WHERE isbn13 IS NOT NULL")}
def sk_for(isbns):
    s=set()
    for ib in isbns:
        for r in cur.execute("SELECT se.series_key FROM volumes v JOIN editions e ON e.id=v.edition_id JOIN series se ON se.id=e.series_id WHERE v.isbn13=?",(ib,)): s.add(r[0])
    return sorted(s)
def sids_for(keys):
    s=set()
    for k in keys:
        for r in cur.execute("SELECT id FROM series WHERE series_key=?",(k,)): s.add(r[0])
    return s
def num_exists(sids,num):
    return any(cur.execute("SELECT 1 FROM volumes v JOIN editions e ON e.id=v.edition_id WHERE e.series_id=? AND v.number=?",(sid,num)).fetchone() for sid in sids)
def flag_media_spinoff(nt,t):
    base=nt.split(" : ")[0].strip()
    if any(m in nt for m in MEDIA): return "MEDIA"
    if base.startswith("小説") and not t.startswith("小説"): return "NOVEL"
    if ("外伝" in nt and "外伝" not in t) or ("番外編" in nt and "番外編" not in t):
        # 副題側に親シリーズ名で外伝が出るFP(ソードオラトリア型)は base==t なら許す
        def n(s): return unicodedata.normalize("NFKC",re.sub(r"[\s:：・!?！？、,，.。\-―~〜]","",s)).lower()
        if n(base)!=n(t): return "SPINOFF"
    return None

ndl={}
for l in open(f"{ROOT}/.cache/volgap-ndl.jsonl",encoding="utf-8"):
    o=json.loads(l); ndl[o["slug"]]=o.get("records",[])
drafts=[]; flagged=[]; stat=Counter()
for slug,recs in ndl.items():
    p=f"{ROOT}/data/manga.v2/{slug}.yml"
    if not os.path.exists(p): stat["no_yml"]+=1; continue
    d=yaml.safe_load(open(p,encoding="utf-8")); eds=d.get("editions") or []
    isbns=[i for i in (norm(v.get("isbn13")) for e in eds for v in (e.get("volumes") or []) if v.get("isbn13")) if i]
    pc=Counter(reg(i) for i in isbns if reg(i)); mainpref=pc.most_common(1)[0][0] if pc else None
    nums=sorted({v.get("number") for e in eds for v in (e.get("volumes") or []) if v.get("number")})
    if len(nums)<2: continue
    gaps=[n for n in range(nums[0],nums[-1]+1) if n not in nums]
    if not gaps: continue
    sk=sk_for(isbns)
    if not sk: stat["no_sk"]+=1; continue
    sids=sids_for(sk)
    by_vol={}
    for r in recs:
        mn=re.search(r"\d+",(r.get("volume") or "").strip())
        if mn and r.get("isbn"): by_vol.setdefault(int(mn.group()),[]).append(r)
    for n in gaps:
        picked=None
        for r in by_vol.get(n,[]):
            ib=norm(r.get("isbn"))
            if len(ib)!=13: continue
            if mainpref and reg(ib)!=mainpref: continue
            if ib in db_isbns: picked="SKIP_DB"; break
            picked=r; break
        if picked=="SKIP_DB": stat["g3_in_db"]+=1; continue
        if not picked: stat["no_match"]+=1; continue
        ib=norm(picked.get("isbn"))
        if num_exists(sids,n): stat["g4_dup"]+=1; continue
        fl=flag_media_spinoff(picked.get("ndl_title",""),d["title"])
        rec={"slug":slug,"series_keys":sk,"number":n,"isbn13":ib,"issued":picked.get("date",""),
             "publisher":picked.get("publisher",""),"title":d["title"],"ndl_title":picked.get("ndl_title","")}
        if fl: flagged.append((fl,rec)); stat[f"flag_{fl}"]+=1; continue
        drafts.append(rec); stat["draft"]+=1
print("=== offline harvest (guarded) ===")
for k,v in stat.most_common(): print(f"{v:5d} {k}")
print(f"\nclean drafts {len(drafts)} / flagged(除外) {len(flagged)}")
for fl,r in flagged: print(f"  EXCLUDE[{fl}] {r['title'][:18]} v{r['number']} {r['isbn13']} | {r['ndl_title'][:30]}")
if not APPLY:
    print("\n(--apply で auto.yml へ純粋追加)"); sys.exit()
auto=yaml.safe_load(open(f"{ROOT}/data/seeds/volumes-supplement-auto.yml",encoding="utf-8"))
existing=auto.get("volumes",[]); have={norm(e.get("isbn13")) for e in existing}
new=[]
for d in drafts:
    if d["isbn13"] in have: continue
    have.add(d["isbn13"])
    new.append({"series_keys":d["series_keys"],"qid":None,"number":d["number"],"isbn13":d["isbn13"],
        "release_date":fmt_date(d.get("issued")),"pages":None,"publisher":d.get("publisher") or "",
        "edition_type":"standard","title_display":d.get("title"),"source":"ndl-auto","added_at":ADDED,
        "note":"MADB取込もれ(MADBラグ)。NDLキャッシュで確認(ISBN/巻/発売日・出版社prefix一致guard)。巻抜けper-case offline harvest。"})
merged=existing+new
open(f"{ROOT}/data/seeds/volumes-supplement-auto.yml","w",encoding="utf-8").write(
 "# 【自動生成】NDL 確認済 MADB取込もれ巻 (= 種4 auto)。 生成元 _register-seed4-ndl.py / _volgap-offline-harvest.py。\n"
 "# 手動版 data/seeds/volumes-supplement.yml は不変。 promote/audit が両方 load。\n"
 "# ★ db-v2 再build / NDL再取得時は再生成。\n"
 + yaml.dump({"schema_version":1,"generator":"ndl-auto","volumes":merged},allow_unicode=True,sort_keys=False,width=200))
with open(f"{ROOT}/data/seeds/volume-gaps-changelog.jsonl","a",encoding="utf-8") as f:
    for e in new:
        f.write(json.dumps({"op":"add-seed4-auto","series_keys":e["series_keys"],"number":e["number"],
            "isbn13":e["isbn13"],"release_date":e["release_date"],"title":e["title_display"],
            "reason":"巻抜けper-case offline harvest(MADBラグ取込もれ・NDLキャッシュ+prefix guard)","at":ADDED},ensure_ascii=False)+"\n")
print(f"\n既存{len(existing)} + 新規{len(new)} = {len(merged)} → volumes-supplement-auto.yml + changelog")
