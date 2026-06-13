"""ジャンル品質 監査(read-only)。 品質改善4段の第1段([[genre_quality_improvement]])。
本番 data/manga.v2 全頁を1回読みで集計。 ★本番不変。 出力 .cache/genre-audit/。

測る: ①ジャンル数分布/0件/other ②master別頁数 ③AniList照合カバレッジ
  ④AI⇄AniList一致率(両方ある頁で、 mapped AniList genre が genres に入っているか)
  ⑤off-vocabulary(masterに無いキー) ⑥AI単独キー(AniList語彙に無い=未検証)の規模
"""
import os, sys, json, yaml
from collections import Counter
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
try:
    from yaml import CSafeLoader as L
except ImportError:
    from yaml import SafeLoader as L
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".cache" / "genre-audit"; OUT.mkdir(parents=True, exist_ok=True)

MASTER = set(yaml.safe_load((ROOT/"data/genres.yml").read_text(encoding="utf-8")).keys())
A2M = {"Romance":"romance","Comedy":"comedy","Drama":"drama","Action":"action","Fantasy":"fantasy",
 "Slice of Life":"slice-of-life","Adventure":"adventure","Sci-Fi":"sci-fi","Mystery":"mystery",
 "Horror":"horror","Sports":"sports","Mecha":"mecha","Music":"music","Thriller":"suspense",
 "Supernatural":"supernatural","Ecchi":"ecchi","Psychological":"mind-game","Mahou Shoujo":"mahou-shoujo"}
ANILIST_MAPPED_MASTER = set(A2M.values())  # AniListで裏取りできるmasterキー

def main():
    SRC = ROOT/"data/manga.v2"
    n=0; gcount=Counter(); has_anilist=0; only_other=0; zero=0
    keycount=Counter(); offvocab=Counter(); other_samples=[]
    agree=0; disagree=0; disagree_samples=[]
    ai_only_key_pages=0  # AI単独キーのみ(AniList裏取りキー0)の頁
    for e in os.scandir(SRC):
        if not e.name.endswith(".yml"): continue
        d = yaml.load(open(e.path,encoding="utf-8"), Loader=L) or {}
        n+=1
        g = d.get("genres") or []
        ga = d.get("genres_anilist") or []
        gcount[min(len(g),5)] += 1
        if not g: zero+=1
        if g == ["other"]: only_other+=1
        if ga: has_anilist+=1
        for k in g:
            keycount[k]+=1
            if k not in MASTER:
                offvocab[k]+=1
                if k=="other" and len(other_samples)<25: other_samples.append((e.name[:-4], d.get("title")))
        # AI単独キーのみか(masterだがAniList裏取り不能キーだけ)
        if g and all(k in MASTER and k not in ANILIST_MAPPED_MASTER for k in g):
            ai_only_key_pages+=1
        # 一致率: genres_anilist を master にマップ→ genres に入っているか
        if ga:
            mapped = {A2M[x] for x in ga if x in A2M}
            if mapped:
                if mapped & set(g): agree+=1
                else:
                    disagree+=1
                    if len(disagree_samples)<25:
                        disagree_samples.append((d.get("title"), g[:4], sorted(mapped)))
        if n%10000==0: print(f"  ...{n:,}",flush=True)

    print(f"\n{'='*60}\nジャンル品質監査: 全 {n:,} 頁")
    print(f"{'='*60}")
    print(f"ジャンル数分布: " + " / ".join(f"{k}個:{gcount[k]:,}" for k in sorted(gcount)))
    print(f"  ジャンル0件: {zero:,} / 'other'のみ: {only_other:,}")
    print(f"  AniList照合あり(genres_anilist有): {has_anilist:,} ({has_anilist*100//n}%) → 残り{n-has_anilist:,}はAI単独")
    print(f"  ★AI単独キーのみの頁(AniListで裏取り不能なキーだけ): {ai_only_key_pages:,}")
    print(f"\noff-vocabulary(masterに無いキー): {sum(offvocab.values()):,} 出現 / {len(offvocab)} 種")
    for k,c in offvocab.most_common(15): print(f"    {k}: {c:,}")
    print(f"\nAI⇄AniList 一致率(genres_anilist有 {agree+disagree:,}頁): 一致 {agree:,} / 不一致 {disagree:,} ({agree*100//max(agree+disagree,1)}%一致)")
    print(f"\nmaster別 頁数(多い順):")
    for k,c in keycount.most_common(40):
        tag = "" if k in ANILIST_MAPPED_MASTER else ("★AI単独" if k in MASTER else "❌off-vocab")
        print(f"    {c:>7,}  {k:<16}{tag}")
    json.dump({"keycount":dict(keycount),"offvocab":dict(offvocab),
               "disagree_samples":disagree_samples,"other_samples":other_samples,
               "n":n,"zero":zero,"only_other":only_other,"has_anilist":has_anilist,
               "agree":agree,"disagree":disagree},
              open(OUT/"summary.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n不一致サンプル(genres vs AniListマップ):")
    for t,g,m in disagree_samples[:12]: print(f"    「{t}」 genres={g} ⇔ AniList={m}")
    print(f"→ {OUT/'summary.json'}")

if __name__=="__main__":
    main()
