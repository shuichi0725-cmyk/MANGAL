"""slug 最終アセンブル = #1〜#4 統合 + #2 衝突 suffix。 ※未適用・全件レビュー TSV。

base slug 分岐:
  num            → 数字4分岐(_slug-numbers ロジック)
  kata/latin     → 種a romaji / 無ければ kata-dict 英語化 / 無ければ phonetic
  kanji/hira     → 埋込外来語ハイブリッド / 無ければ kana_slug
衝突 suffix(CLAUDE.md): 主版(巻数多→古い)=無印、 従版= -姓ローマ字+発売年。
  二重衝突は -姓年-2… の index。 出力 .cache/slug-final.tsv。
"""
import pickle, csv, json, re, sqlite3, sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import pykakasi
_kks = pykakasi.kakasi()
PKL = Path(".cache/seed3-promote.pkl")
V1 = Path(".cache/slug-gen-v1.tsv")
DICT = json.loads(Path(".cache/kata-dict.json").read_text(encoding="utf-8"))
DB = Path(".cache/db-v2.sqlite")
VOWEL = "aeiou"

# ---- 共通ローマ字 ----
def hep(kana): return "".join(it["hepburn"] for it in _kks.convert(kana)).lower()
def drop_long(r):
    while True:
        n = re.sub(r"ou","o",r); n=re.sub(r"oo","o",n); n=re.sub(r"uu","u",n)
        if n==r: return r
        r=n
def phon(tok): return re.sub(r"[^a-z0-9]+","",drop_long(hep(tok)))
def canon(s): return drop_long(s.replace("wo","o"))
def english_like(t):
    if not t: return False
    if "l" in t or "x" in t or "q" in t: return True
    if t[-1] not in VOWEL and t[-1]!="n" and not t[-1].isdigit(): return True
    return False

# ---- #3 埋込外来語ハイブリッド ----
FOREIGN = re.compile(r"[゠-ヿA-Za-z]")
def hybridize(kana_slug, a_slug, title):
    if not FOREIGN.search(title): return None
    kt=kana_slug.split("-"); at=a_slug.split("-")
    if len(kt)!=len(at) or not kt: return None
    out=[]; sw=False
    for k,a in zip(kt,at):
        if canon(k)==canon(a): out.append(k)
        elif english_like(a) and not english_like(k): out.append(a); sw=True
        else: out.append(k)
    return "-".join(out) if sw else None

# ---- #1 数字4分岐 ----
ON=["ジュウ","ヒャク","ビャク","ピャク","セン","ゼン","マン","イチ","ニ","サン","シ","ゴ","ロク","シチ","ハチ","キュウ","ク","ゼロ","レイ","マル"]
KUN_TSU=["ヒトツ","フタツ","ミッツ","ヨッツ","イツツ","ムッツ","ナナツ","ヤッツ","ココノツ","トオ"]
KUN_NUM=["ヨン","ナナ","ヒト","フタ","ミ","ヨ","イツ","ム","ヤ","ココノ"]
EN_NUM=["ゼロ","ワン","ツー","スリー","フォー","フォア","ファイブ","ファイヴ","シックス","セブン","エイト","ナイン","テン","イレブン","トゥエルブ","ティーン","トゥエンティ","サーティ","フォーティ","フィフティ","シックスティ","セブンティ","エイティ","ナインティ","ハンドレッド"]
LATIN=re.compile(r"[A-Za-z]")
def _sa(s,lst):
    for w in lst:
        if s.startswith(w): return w
    return None
def classify_seg(seg):
    if "ティーン" in seg or _sa(seg,EN_NUM): return ("en",seg,"")
    if _sa(seg,KUN_TSU) or _sa(seg,KUN_NUM): return ("kun",seg,"")
    i=0; c=False
    while i<len(seg):
        w=None
        for cand in ON:
            if seg.startswith(cand,i): w=cand; break
        if not w: break
        i+=len(w); c=True
    return ("on",seg[:i],seg[i:]) if c else None
def number_slug(title, seg):
    runs=re.findall(r"[0-9０-９]+",title)
    frac=bool(re.search(r"[0-9０-９]\s*[/／]\s*[0-9０-９]",title))
    di=0; parts=[]; segs=seg.split(); j=0
    while j<len(segs):
        s=segs[j]; cl=classify_seg(s)
        if cl and not frac:
            typ,_,rest=cl; grp=[s]; jj=j+1
            while jj<len(segs) and classify_seg(segs[jj]) and not rest:
                nx=classify_seg(segs[jj]); grp.append(segs[jj]); jj+=1
                if nx[2]: break
            dg=runs[di] if di<len(runs) else ""
            if typ in ("on","en") and dg:
                out=dg
                if rest:
                    rr=phon(rest);  out=f"{dg}-{rr}" if rr else dg
                parts.append(out); di+=1
            else:
                rr=phon("".join(grp))
                if rr: parts.append(rr)
                if typ in ("on","en"): di+=1
            j=jj; continue
        if LATIN.search(s): parts.append(re.sub(r"[^a-z0-9]+","",s.lower()))
        else:
            rr=phon(s)
            if rr: parts.append(rr)
        j+=1
    return "-".join(p for p in parts if p)

# ---- #4 kata-dict ----
def kata_dict_slug(seg):
    parts=[]
    for tok in seg.split():
        if tok in DICT: parts.append(DICT[tok])
        else:
            p=phon(tok)
            if p: parts.append(p)
    return "-".join(p for p in parts if p)

def base_title(key):
    ns=[p[5:] for p in key.split("|") if p.startswith("name:")]
    return ns[-1] if ns else ""
def author_of(key):
    ns=[p[5:] for p in key.split("|") if p.startswith("name:")]
    return ns[0] if len(ns)>=2 else ""
SKIP_AUTHOR=re.compile(r"編集部|編集|アンソロジー|製作|スタジオ")
def surname_romaji(author):
    """著者名→姓ローマ字(先頭token)。 編集部/数字主体は除外。"""
    if not author or SKIP_AUTHOR.search(author): return ""
    # 記号・数字を除いた本体
    core=re.sub(r"[0-9０-９「」『』・,，\s]","",author)
    if not core: return ""
    for it in _kks.convert(core):
        r=re.sub(r"[^a-z]","",drop_long(it["hepburn"].lower()))
        if r and len(r)>=2: return r
    return ""


def main():
    d=pickle.load(PKL.open("rb"))
    # slug-gen-v1: key→(class, kana_seg, kana_slug, a_romaji_slug)
    v1={}
    with V1.open(encoding="utf-8") as f:
        for r in csv.DictReader(f,delimiter="\t"):
            v1[r["key"]]=r
    # match-v14: series_key→a_authors(姓 tiebreak 用)
    a_auth={}
    with open(".cache/match-v14-all.tsv",encoding="utf-8") as f:
        for r in csv.DictReader(f,delimiter="\t"):
            if r["verdict"].startswith("S") and r.get("a_authors"):
                a_auth[r["s3_key"]]=r["a_authors"].split("|")[0]
    # 種2: series_key→(vols, first_year)
    con=sqlite3.connect(DB); con.text_factory=lambda b:b.decode("utf-8","replace")
    meta={}
    for sk,vols,fy in con.execute("""SELECT s.series_key, COUNT(v.id),
        MIN(CAST(substr(v.release_date,1,4) AS INT))
        FROM series s JOIN editions e ON e.series_id=s.id JOIN volumes v ON v.edition_id=e.id
        GROUP BY s.series_key"""):
        meta[sk]=(vols or 0, fy or 9999)
    con.close()

    ent=[]   # (key, title, base_slug, vols, year, author_surname)
    for e in d.values():
        key=e["key"]; r=v1.get(key)
        if not r: continue
        cls=r["class"]; title=r["title"]; seg=r["kana_seg"]
        ks=r["kana_slug"]; ars=r["a_romaji_slug"]
        if cls=="num":
            base=number_slug(title,seg)
        elif cls in ("kata","latin"):
            base = ars if ars else (kata_dict_slug(seg) if seg else ks)
        else:
            base = hybridize(ks,ars,title) or ks
        if not base: base=ks or phon(seg)
        vols,year=meta.get(key,(0,9999))
        sur=surname_romaji(a_auth.get(key,"")) or surname_romaji(author_of(key))
        ent.append([key,title,base,vols,year,sur])

    # 衝突 suffix
    groups=defaultdict(list)
    for row in ent: groups[row[2]].append(row)
    final={}
    suffixed=0
    for base,members in groups.items():
        if len(members)==1:
            final[members[0][0]]=base; continue
        # 主版 = 巻数多い→古い、 無印。 従版= -発売年(主)、 同年衝突は -年-姓 / -年-index
        ms=sorted(members,key=lambda x:(-x[3],x[4]))
        seen=set()
        for i,row in enumerate(ms):
            if i==0:
                final[row[0]]=base; seen.add(base); continue
            yr=row[4] if row[4]!=9999 else ""
            cand=f"{base}-{yr}" if yr else base
            if cand in seen:                       # 同年衝突 → 姓で tie-break
                sur=row[5]
                cand=f"{base}-{yr}-{sur}" if sur else f"{base}-{yr}"
            k=2
            while cand in seen:
                cand=f"{base}-{yr}-{k}"; k+=1
            final[row[0]]=cand; seen.add(cand); suffixed+=1

    with open(".cache/slug-final.tsv","w",encoding="utf-8") as f:
        f.write("key\ttitle\tbase_slug\tfinal_slug\tvols\tyear\n")
        for key,title,base,vols,year,sur in ent:
            f.write(f"{key}\t{title}\t{base}\t{final[key]}\t{vols}\t{year if year!=9999 else ''}\n")
    # stats
    allslugs=list(final.values())
    dup=len(allslugs)-len(set(allslugs))
    print(f"全 {len(ent):,} 件 → 最終 slug 生成")
    print(f"  suffix 付与(従版): {suffixed:,}")
    print(f"  残存衝突(本来0): {dup}")
    print("wrote .cache/slug-final.tsv")
    # サンプル: suffix された群
    print("\n=== suffix サンプル ===")
    shown=0
    for base,members in groups.items():
        if len(members)>1 and shown<12:
            ms=sorted(members,key=lambda x:(-x[3],x[4]))
            disp=[(m[1][:14],final[m[0]],m[3],m[4]) for m in ms[:4]]
            print(f"  base={base[:24]}")
            for t,sl,v,y in disp:
                print(f"      {t:<14} v{v} {y} → {sl}")
            shown+=1


if __name__=="__main__":
    main()
