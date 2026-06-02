"""全種3 entry の slug 一括生成(first pass、 衝突無視)。
ソース優先: ①種3.slug override ②AniList romaji(マッチ済=最良) ③title_kana_segmented→ヘボン。
出力: .cache/slug-firstpass.tsv(key, slug, source)+ 衝突/破綻レポート。
★launch前の問題洗い出し用。 衝突suffix等は後続で対応。
"""
import json, gzip, sys, re, unicodedata, yaml
from collections import Counter, defaultdict
import pykakasi
sys.stdout.reconfigure(encoding="utf-8")
try: from yaml import CSafeLoader as L
except ImportError: from yaml import SafeLoader as L
kks = pykakasi.kakasi()
SUBSEP = re.compile(r"\s*[:：〜～].*$")  # romaji の副題部を除去

def slugify(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")

def kana_slug(seg):
    if not seg: return ""
    parts=[]
    for tok in seg.split():
        parts.append("".join(x["hepburn"] for x in kks.convert(tok)))
    return slugify("-".join(p for p in parts if p))

print("種3 load...", file=sys.stderr)
s3={}
for e in yaml.load(open("data/seeds/series-supplement-v2.yml",encoding="utf-8"),Loader=L)["series"]:
    s3[e["key"]]=e
print(f"  {len(s3):,}", file=sys.stderr)

en=json.load(open(".cache/anilist-enrich-map.json",encoding="utf-8"))
key2aid={k:v["anilist_id"] for k,v in en.items() if isinstance(v,dict) and v.get("anilist_id")}
romaji={}
for line in gzip.open(".cache/anilist-manga-dump-v3.jsonl.gz","rt",encoding="utf-8"):
    d=json.loads(line); t=d.get("title") or {}
    if t.get("romaji"): romaji[d["id"]]=t["romaji"]

src_cnt=Counter()
rows=[]
for key,e in s3.items():
    if e.get("slug"):
        sl=e["slug"]; src="override"
    else:
        aid=key2aid.get(key)
        rj=romaji.get(int(aid)) if aid else None
        sl=slugify(SUBSEP.sub("",rj)) if rj else ""
        if sl: src="anilist_romaji"
        else:
            sl=kana_slug(e.get("title_kana_segmented") or e.get("title_kana") or "")
            src="kana_hepburn" if sl else "EMPTY"
    rows.append((key,sl,src)); src_cnt[src]+=1

with open(".cache/slug-firstpass.tsv","w",encoding="utf-8") as f:
    f.write("key\tslug\tsource\n")
    for k,s,src in rows: f.write(f"{k}\t{s}\t{src}\n")

slugs=[s for _,s,_ in rows]
c=Counter(slugs)
dups={s:n for s,n in c.items() if n>1 and s}
empty=sum(1 for s in slugs if not s)
print("=== slug first pass ===")
print(f"総数: {len(rows):,}")
print(f"source内訳: {dict(src_cnt)}")
print(f"空/破綻(EMPTY slug): {empty:,}")
print(f"★衝突 slug(同名フォルダ): {len(dups):,}種 / 該当entry {sum(dups.values()):,}件")
print("=== 衝突トップ15(slug: 件数)===")
for s,n in sorted(dups.items(),key=lambda x:-x[1])[:15]:
    print(f"  {s}: {n}")
