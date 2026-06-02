"""衝突グループを4型に機械分類(merge/別版/spinoff/drop候補)。本番不変・調査用。
判定軸: 同qid(著者)/ 共通語幹(prefix/suffix)/ 巻数分布 / 別版マーカー。
★cm104凍結で新作はシリーズ構造無し=著者+語幹で結ぶしかない前提。
出力: .cache/collision-classified.json + 型別件数。
"""
import csv, json, sys, sqlite3, re
from collections import defaultdict, Counter
sys.stdout.reconfigure(encoding="utf-8")
k2s={r["key"]:r["slug"] for r in csv.DictReader(open(".cache/slug-firstpass.tsv",encoding="utf-8"),delimiter="\t")}
con=sqlite3.connect(".cache/db-v2.sqlite"); con.text_factory=lambda b:b.decode("utf-8","replace")
info=dict((k,(t,q)) for k,t,q in con.execute("SELECT series_key,title,qid FROM series"))
sid2key=dict(con.execute("SELECT id,series_key FROM series"))
imp_c=defaultdict(Counter)
for sid,imp in con.execute("SELECT series_id,imprint FROM editions WHERE imprint IS NOT NULL AND imprint!=''"):
    k=sid2key.get(sid)
    if k: imp_c[k][imp]+=1
imp_of={k:c.most_common(1)[0][0] for k,c in imp_c.items()}
maxvol=defaultdict(int)
for k,mx in con.execute("SELECT s.series_key,MAX(v.number) FROM series s JOIN editions e ON e.series_id=s.id JOIN volumes v ON v.edition_id=e.id WHERE v.number BETWEEN 1 AND 300 GROUP BY s.series_key"):
    maxvol[k]=mx or 0
con.close()

EDMARK=re.compile(r"(文庫版?|愛蔵版|新装版|完全版|ワイド版|新装|デラックス|新版|廉価版|コンビニ|総愛蔵|傑作選集?|カラー版)")
DROPHINT=re.compile(r"COLOR WALK|THE \d+|LOG|画集|原画|アニメ|映画|劇場|総集編|ファンブック|ガイド|画報|大全|設定")

def lcp(ss):
    if not ss: return ""
    s1,s2=min(ss),max(ss); i=0
    while i<len(s1) and i<len(s2) and s1[i]==s2[i]: i+=1
    return s1[:i]
def lcsuf(ss):
    r=[s[::-1] for s in ss]; return lcp(r)[::-1]

# ★page単位に畳む(merge兄弟を1ページに=衝突は異ページ間のみ)
import yaml
key2page={}
for g in json.load(open("data/seeds/series-merge-auto.json",encoding="utf-8"))["merges"]:
    mk=g.get("merge_keys") or []
    if len(mk)>=2:
        for k in mk: key2page[k]=mk[0]
for em in (yaml.safe_load(open("data/seeds/series-merge.yml",encoding="utf-8")) or []):
    mk=em.get("merge_keys") or []
    if len(mk)>=2:
        for k in mk: key2page[k]=mk[0]
page_members=defaultdict(list)
for k in k2s: page_members[key2page.get(k,k)].append(k)
def _rep(p,ms):
    return p if p in info else max(ms,key=lambda m:maxvol.get(m,0))
P_slug={}; P_title={}; P_qid={}; P_vol={}; P_imp={}
for p,ms in page_members.items():
    rep=_rep(p,ms)
    P_slug[p]=k2s.get(p) or Counter(k2s[m] for m in ms).most_common(1)[0][0]
    t,q=info.get(rep,("",None)); P_title[p]=t or ""; P_qid[p]=q
    P_vol[p]=maxvol.get(rep,0); P_imp[p]=imp_of.get(rep)
slug2pages=defaultdict(list)
for p,s in P_slug.items():
    if s: slug2pages[s].append(p)

cats=defaultdict(list)
for s,keys in slug2pages.items():
    if len(keys)<2: continue
    titles=[P_title[p] for p in keys]
    qids=[P_qid[p] for p in keys]
    vols=[P_vol[p] for p in keys]
    imps={P_imp[p] for p in keys}
    same_q = len(set(q for q in qids if q))<=1 and any(qids)
    pre,suf=lcp(titles),lcsuf(titles)
    stem=pre if len(pre)>=len(suf) else suf
    stemlen=len(stem.strip())
    drophits=[t for t in titles if DROPHINT.search(t)]
    norm_titles={EDMARK.sub("",t).strip() for t in titles}
    rec={"slug":s,"n":len(keys),"same_qid":same_q,"stem":stem.strip(),
         "vols":sorted(vols),"imprints":[x for x in imps if x],"titles":titles,
         "drophits":drophits}
    # 分類(慎重: 確信あるものだけ強型、 残はAMBIG)
    if same_q and stemlen>=3 and all(v<=1 for v in vols) and len(keys)>=3:
        cats["VOLUME_SPLIT"].append(rec)           # 巻割れ=merge最有力
    elif same_q and len(norm_titles)==1 and len(set(vols))>1:
        cats["MULTI_EDITION"].append(rec)          # 同題・別巻数=別版
    elif len(drophits)>=max(1,len(keys)//2):
        cats["DROP_CAND"].append(rec)              # 画集/LOG等が過半
    elif same_q and stemlen>=3:
        cats["SPINOFF_OR_SPLIT"].append(rec)       # 同著者・共通語幹だが巻数まちまち=要判断
    else:
        cats["OTHER"].append(rec)                  # 別作品が偶然同slug 等
json.dump(cats,open(".cache/collision-classified.json","w",encoding="utf-8"),ensure_ascii=False)
print("=== 衝突グループ 4型分類 ===")
tot=0
for c in ["VOLUME_SPLIT","MULTI_EDITION","SPINOFF_OR_SPLIT","DROP_CAND","OTHER"]:
    n=len(cats[c]); g=sum(r["n"] for r in cats[c]); tot+=n
    print(f"  {c:18}: {n:4}組 / {g:5}ページ")
print(f"  合計 {tot}組")
