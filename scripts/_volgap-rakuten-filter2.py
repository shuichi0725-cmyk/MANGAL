"""harvest候補(.cache/volgap-rakuten-cands.json)を新方針でfilter:
- 単一版(版1=standardのみ)作: 版混在リスク無→date-fit+同出版社で採用(高人気でもOK)。
- 多版作: harvestはstandard routing固定で非standard版gapを誤埋めしうる→defer(wiki rebuild行き)。
- 全候補: 種2非存在(harvest済) + 前後巻発売日整合(版違い日付逆行を除外)。
出力: .cache/volgap-rakuten-clean2.json"""
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
def pmonth(s):
    m=re.match(r"(\d{4})(?:-(\d{1,2}))?",str(s or ""))
    if not m: return None
    return int(m.group(1))*12+(int(m.group(2) or 6)-1)
clean=[]; defer_multi=[]; skip_date=[]
for slug,cs in byslug.items():
    d=yaml.safe_load(open(f"{ROOT}/data/manga.v2/{slug}.yml",encoding="utf-8"))
    ets=set(e.get("type") or "standard" for e in d.get("editions") or [])
    seq={}
    for e in d.get("editions") or []:
        if (e.get("type") or "standard")!="standard": continue
        for v in e.get("volumes") or []:
            if v.get("number") and v.get("release_date"): seq[v["number"]]=pmonth(v.get("release_date"))
    if len(ets)>1:
        defer_multi.append((d.get("title",""),len(cs))); continue   # 多版=wiki rebuild行き
    candmap={c["number"]:pmonth(c["release_date"]) for c in cs}
    alln=sorted(set(seq)|set(candmap))
    def neigh(n,lo):
        for m in (range(n-1,0,-1) if lo else range(n+1,(alln[-1] if alln else n)+2)):
            if m in seq: return seq[m]
            if m in candmap: return candmap[m]
        return None
    okwork=True; tmp=[]
    for c in cs:
        cd=candmap[c["number"]]; lo,hi=neigh(c["number"],True),neigh(c["number"],False)
        bad=cd is not None and ((lo is not None and cd<lo-18) or (hi is not None and cd>hi+18))
        if bad: skip_date.append((c["title"],c["number"],c["release_date"])); okwork=False
        else: tmp.append(c)
    if okwork: clean+=tmp
    # partial-skip作は丸ごとdefer(怪しい)
print(f"単一版clean {len(clean)}巻/{len(set(c['title'] for c in clean))}作 | 多版defer {len(defer_multi)}作 | date除外 {len(skip_date)}")
json.dump(clean,open(f"{ROOT}/.cache/volgap-rakuten-clean2.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("\n=== 単一版clean 作品 ===")
bk=defaultdict(list)
for c in clean: bk[c['title']].append(c['number'])
for t,ns in sorted(bk.items()): print(f"  {t[:26]:28} {sorted(ns)}")
print("\n=== 多版defer(wiki rebuild候補) ===")
for t,n in sorted(defer_multi): print(f"  {t[:26]:28} 候補{n}")
