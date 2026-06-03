"""本番DB前 最終見直し監査(read-only)。 slug/フリガナ/漫画名/副題 の4軸で
★候補をflag(直さない)。 出力 = .cache/preprod/*.tsv + サマリ。 朝レポート素材。

最終ページ = merge(series-merge.yml + auto)+ drop(non-manga-drop.yml + title patterns)適用後の代表key。
"""
import csv
import json
import sys
import re
import unicodedata
import pickle
import sqlite3
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".cache" / "preprod"
OUT.mkdir(exist_ok=True)

DROP_TITLE_PREFIX = ["テレビアニメ版", "TVアニメ版", "TVアニメ", "アニメコミック", "劇場版", "映画",
                     "OVA", "ノベライズ", "ノベル", "英訳・", "英訳"]
DROP_TITLE_CONTAINS = ["ガイドブック", "ファンブック", "設定資料集", "公式図録", "公式読本", "公式ファン",
                       "公式コミックガイド", "アンソロジー", "キャラクター名鑑", "人物名鑑", "キャラクターブック",
                       "心理分析", "心理解析", "完全解析", "完全攻略", "攻略本", "解析書", "解体新書",
                       "解体全書", "大研究", "最終研究", "超研究", "大事典", "大百科", "大解剖",
                       "パーフェクトガイド", "完全読本", "完全ガイド", "必勝法", "の秘密", "の謎",
                       "コミック大全", "コミックスペシャル", "ナビゲーション", "考察", "傑作選", "傑作集",
                       "ベストセレクション", "特集号", "特別総集編", "名作集", "名作選", "自選", "総集編",
                       "原画集", "画集", "ポケット画廊", "うちあけ話"]

PUA = re.compile(r"[-�]")
LATIN_ONLY = re.compile(r"^[\x00-\x7f｡-ﾟ\s]+$")
HAS_JP = re.compile(r"[ぁ-んァ-ヶ一-龠]")
AUTHOR_LEAK = re.compile(r" ; |；| illustrated| translated| ＆ .* ;|avec |couleur")
PUB_IN_SUB = re.compile(r"出版|社$|コミックス$|comics|文庫$|新聞|書店|プロダクション|スタジオ", re.I)


def title_of(key):
    names = [s[5:] for s in key.split("|") if s.startswith("name:")]
    return names[-1] if names else key


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    key2slug = {}
    for r in csv.reader((ROOT / ".cache/slug-firstpass.tsv").open(encoding="utf-8"), delimiter="\t"):
        if len(r) >= 3 and r[0] != "key":
            key2slug[r[0]] = (r[1], r[2])
    seed3 = pickle.load((ROOT / ".cache/seed3-promote.pkl").open("rb"))
    import yaml
    nm = yaml.safe_load((ROOT / "data/seeds/non-manga-drop.yml").read_text(encoding="utf-8"))
    non_manga = {e["series_key"] for e in (nm.get("non_manga") or []) if e.get("series_key")}
    key2grp = {}
    auto = json.load((ROOT / "data/seeds/series-merge-auto.json").open(encoding="utf-8"))["merges"]
    for g in auto:
        for k in (g.get("merge_keys") or []):
            key2grp[k] = g["merge_keys"][0]
    hand = yaml.safe_load((ROOT / "data/seeds/series-merge.yml").read_text(encoding="utf-8")) or []
    for e in hand:
        if isinstance(e, dict) and len(e.get("merge_keys") or []) >= 2:
            for k in e["merge_keys"]:
                key2grp[k] = e["merge_keys"][0]
    con = sqlite3.connect(ROOT / ".cache/db-v2.sqlite")
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    key2sub = {}
    sid2key = {}
    for sid, key, sub in con.execute("SELECT id, series_key, subtitle FROM series"):
        key2sub[key] = sub or ""
        sid2key[key] = sid

    # 最終ページ
    final = {}   # grp -> rep key
    seen = set()
    for key in key2slug:
        title = title_of(key)
        if any(title.startswith(p) for p in DROP_TITLE_PREFIX):
            continue
        if any(p in title for p in DROP_TITLE_CONTAINS):
            continue
        if key in non_manga:
            continue
        grp = key2grp.get(key, key)
        if grp in seen:
            continue
        seen.add(grp)
        final[grp] = key

    flags = defaultdict(list)
    slug2pages = defaultdict(list)
    for grp, key in final.items():
        slug, src = key2slug.get(grp, key2slug.get(key, ("", "")))
        e = seed3.get(grp) or seed3.get(key) or {}
        title = title_of(grp)
        kana = e.get("title_kana", "") or ""
        seg = e.get("title_kana_segmented", "") or ""
        sub = e.get("subtitle") or key2sub.get(grp, "") or ""
        slug2pages[slug].append((grp, title))
        # SLUG
        if not slug:
            flags["slug_empty"].append((slug, title, kana))
        if slug and not re.fullmatch(r"[a-z0-9-]+", slug):
            flags["slug_badchar"].append((slug, title, kana))
        if slug and len(slug) > 60:
            flags["slug_toolong"].append((slug, title, kana))
        # フリガナ
        if HAS_JP.search(title) and not kana:
            flags["kana_empty"].append((slug, title, kana))
        if kana and (" " in kana or "　" in kana):
            flags["kana_hasspace"].append((slug, title, kana))
        if PUA.search(kana) or PUA.search(seg):
            flags["kana_pua"].append((slug, title, kana))
        # 漫画名
        if PUA.search(title):
            flags["title_pua"].append((slug, title, kana))
        if title and LATIN_ONLY.match(title) and len(title) > 3:
            flags["title_latinonly"].append((slug, title, kana))
        if AUTHOR_LEAK.search(title):
            flags["title_authorleak"].append((slug, title, kana))
        # 副題
        if sub and PUA.search(sub):
            flags["sub_pua"].append((slug, title, sub))
        if sub and PUB_IN_SUB.search(sub):
            flags["sub_publisher"].append((slug, title, sub))
        if sub and sub == title:
            flags["sub_equaltitle"].append((slug, title, sub))

    collisions = {s: ps for s, ps in slug2pages.items() if len(ps) >= 2}
    n_col_pages = sum(len(ps) for ps in collisions.values())

    print(f"最終ページ: {len(final):,}")
    print(f"\n★slug衝突: {len(collisions):,} slug / {n_col_pages:,} ページ")
    print("\n=== flag件数 ===")
    for k in sorted(flags):
        print(f"  {k:20}: {len(flags[k]):,}")
        with (OUT / f"{k}.tsv").open("w", encoding="utf-8") as f:
            for row in flags[k]:
                f.write("\t".join(str(x) for x in row) + "\n")
    json.dump([{"slug": s, "pages": [p[0] for p in ps], "titles": [p[1] for p in ps]}
               for s, ps in sorted(collisions.items(), key=lambda x: -len(x[1]))],
              (OUT / "collisions.json").open("w", encoding="utf-8"), ensure_ascii=False)
    print(f"\n→ .cache/preprod/*.tsv + collisions.json")


if __name__ == "__main__":
    main()
