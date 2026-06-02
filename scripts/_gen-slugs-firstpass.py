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


def strip_subtitle(rj):
    """romaji の副題部のみ除去。 ★正規副題区切り = 「: 」(コロン+空白) と 「〜」波線。
    Re:Zero / Re:CREATORS の ':'(直後非空白)や 時刻 5:00 は **除去しない**(本題の一部)。"""
    s = re.sub(r"[〜～].*$", "", rj)        # 〜副題〜
    s = re.sub(r"[:：]\s.*$", "", s)         # コロン+空白 以降(Re:Zero の : は非空白で残る)
    return s.strip()


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

# 非漫画drop(外国版書誌)= slug生成からも除外
import sqlite3
drop_keys=set()
try:
    for e2 in (yaml.safe_load(open("data/seeds/non-manga-drop.yml",encoding="utf-8")) or {}).get("non_manga",[]):
        if e2.get("series_key"): drop_keys.add(e2["series_key"])
except FileNotFoundError:
    pass
# 種2 title(Latin題の直接slug化 fallback 用)
con=sqlite3.connect(".cache/db-v2.sqlite"); con.text_factory=lambda b:b.decode("utf-8","replace")
title_of=dict(con.execute("SELECT series_key,title FROM series"))
con.close()

src_cnt=Counter()
rows=[]
for key,e in s3.items():
    if key in drop_keys:
        src_cnt["dropped"]+=1; continue   # 外国版=ページにならない=slug不要
    if e.get("slug"):
        sl=e["slug"]; src="override"
    else:
        aid=key2aid.get(key)
        rj=romaji.get(int(aid)) if aid else None
        sl=slugify(strip_subtitle(rj)) if rj else ""
        if sl: src="anilist_romaji"
        else:
            sl=kana_slug(e.get("title_kana_segmented") or e.get("title_kana") or "")
            if sl: src="kana_hepburn"
            else:
                t2=title_of.get(key) or ""
                # ★Latin題の直接slug化は「日本語文字を含まない」題のみ(Page 1→page-1)。
                #   日本語混在(復讐の毒鼓REWIND等)はLatin部だけ残す誤りになるのでkana補完に回す。
                if t2 and not re.search(r"[ぁ-んァ-ヶ一-龯]", t2):
                    sl=slugify(t2); src="title_latin" if sl else "EMPTY"
                else:
                    sl=""; src="EMPTY"
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
