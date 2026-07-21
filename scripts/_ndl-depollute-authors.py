"""著者汚染をNDL by-ISBNで除去候補化。安全策=NDLに無い∩疑著者(単独0,総≤3)のみ。ISBN分散6本。適用せず候補CSV出力。中断耐性。"""
import sqlite3,sys,re,html,json,os,time,csv,urllib.request,urllib.parse
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
# 疑著者集合(本番index: 単独作0 ∧ 総≤3)
idx=json.load(open(ROOT+"/.cache/v2-index.json",encoding="utf-8"))
total=Counter(); solo=Counter()
for x in idx:
    aus=list(dict.fromkeys(a[0] for a in x["oau"]+x["au"] if a[0]))
    for a in aus: total[a]+=1
    if len(aus)==1: solo[aus[0]]+=1
suspect=lambda a: solo[a]==0 and total[a]<=3
con=sqlite3.connect(ROOT+"/.cache/db-v2.sqlite"); con.row_factory=sqlite3.Row
# ≥4著者のseries
sids=[r[0] for r in con.execute("""SELECT series_id FROM series_authors GROUP BY series_id HAVING count(DISTINCT mangaka_id)>=4""")]
NC=ROOT+"/.cache/ndl-isbn-creators.json"
ndlc=json.load(open(NC,encoding="utf-8")) if os.path.exists(NC) else {}
def norm(s):
    s=re.sub(r"\s*(著|作|画|作画|原作|漫画|監修|訳|編著|編集|編|構成|原案|脚本|イラスト|まんが|シナリオ|脚色|ed)\s*$","",s.strip())
    return re.sub(r"[\s　・･\.,]","",s).lower()
def ndl_isbn(isbn):
    if isbn in ndlc: return ndlc[isbn]
    url="https://ndlsearch.ndl.go.jp/api/sru?operation=searchRetrieve&recordSchema=dcndl&maximumRecords=2&query="+urllib.parse.quote('isbn="%s"'%isbn)
    out=[]
    try:
        x=html.unescape(urllib.request.urlopen(url,timeout=25).read().decode("utf-8"))
        for c in re.findall(r"<dc:creator>(.*?)</dc:creator>",x):
            for nm in re.split(r"[,、，;／]",c):
                n=norm(nm)
                if n: out.append(n)
    except Exception: pass
    ndlc[isbn]=out; return out
rows=[]
for i,sid in enumerate(sids,1):
    sr=con.execute("SELECT title,series_key FROM series WHERE id=?",(sid,)).fetchone()
    ours=[a[0] for a in con.execute("SELECT DISTINCT m.name FROM series_authors sa JOIN mangaka m ON m.id=sa.mangaka_id WHERE sa.series_id=?",(sid,))]
    isbns=[r[0] for r in con.execute("SELECT v.isbn13 FROM volumes v JOIN editions e ON e.id=v.edition_id WHERE e.series_id=? AND v.isbn13 IS NOT NULL ORDER BY v.number",(sid,)).fetchall()]
    pick=isbns[::max(1,len(isbns)//6)][:6] if isbns else []
    ndl=set()
    for isb in pick: ndl|=set(ndl_isbn(isb)); time.sleep(0.15)
    if not ndl: continue                       # NDL空=触らない
    kept=[a for a in ours if norm(a) in ndl or any(norm(a) in n or n in norm(a) for n in ndl if len(n)>=2)]
    if not kept: continue                      # NDLに本物が残らない=照合失敗→触らない
    rem=[a for a in ours if a not in kept and suspect(a)]   # ★NDL無 ∩ 疑著者 のみ
    if rem:
        rows.append([sr["series_key"],sr["title"],"|".join(rem),"|".join(kept)])
    if i%100==0:
        json.dump(ndlc,open(NC,"w",encoding="utf-8"),ensure_ascii=False)
        print("  %d/%d 除去候補作=%d"%(i,len(sids),len(rows)),flush=True)
json.dump(ndlc,open(NC,"w",encoding="utf-8"),ensure_ascii=False)
with open(ROOT+"/.cache/author-depollute-proposed.csv","w",encoding="utf-8-sig",newline="") as f:
    w=csv.writer(f); w.writerow(["series_key","タイトル","除去候補著者","NDLで残す著者"])
    for r in rows: w.writerow(r)
print("完了: 除去候補作 %d / 除去候補延べ %d人"%(len(rows),sum(len(r[2].split('|')) for r in rows)),flush=True)
