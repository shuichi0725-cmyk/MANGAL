"""正しい順番(① drop → ② merge → ③ slug)で「最終ページ」の slug 衝突を数える監査。

★背景: slug-firstpass は 種3 の生 key 全部に slug を振っていた(= drop/merge 前)。
そのため衝突集合に「外国語版・編集本・版違い・系統」が紛れ、 件数が水増しされていた。
本 script は promote と同じ drop/merge を ★先に適用してから、 残った本物ページだけで
衝突を数える(= 正しい順番の真の残数)。 read-only。

funnel: 全 key → ①drop → ②merge → 最終ページ → ③ slug 衝突。
"""
import csv
import json
import sys
import yaml
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent

# promote と同一の drop パターン(_promote-bulk-v2.py より)
DROP_TITLE_PREFIX = ["テレビアニメ版", "TVアニメ版", "TVアニメ", "アニメコミック",
                     "劇場版", "映画", "OVA", "ノベライズ", "ノベル", "英訳・", "英訳"]
DROP_TITLE_CONTAINS = ["ガイドブック", "ファンブック", "設定資料集", "公式図録", "公式読本",
                       "公式ファン", "公式コミックガイド", "アンソロジー", "キャラクター名鑑",
                       "人物名鑑", "キャラクターブック", "心理分析", "心理解析", "完全解析",
                       "完全攻略", "攻略本", "解析書", "解体新書", "解体全書", "大研究",
                       "最終研究", "超研究", "大事典", "大百科", "大解剖", "パーフェクトガイド",
                       "完全読本", "完全ガイド", "必勝法", "の秘密", "の謎", "コミック大全",
                       "コミックスペシャル", "ナビゲーション", "考察", "傑作選", "傑作集",
                       "ベストセレクション", "特集号", "特別総集編", "名作集", "名作選",
                       "自選", "総集編", "原画集", "画集", "ポケット画廊", "うちあけ話"]
DROP_SUBTITLE = ["傑作集", "傑作選", "ベストセレクション", "名作集", "名作選", "自選", "総集編"]
# 外国語版マーカー(題に [韓国語] 等。 promote は imprint/非掲載 list で拾うが題でも明示)
FOREIGN_MARKERS = ["[韓国語]", "[中国語]", "[英語]", "[フランス語]", "[ドイツ語]", "[スペイン語]"]


def title_of(key):
    names = [s[5:] for s in key.split("|") if s.startswith("name:")]
    return names[-1] if names else key


def sub_of(key, seed3):
    for seg in key.split("|"):
        if seg.startswith("sub:"):
            return seg[4:]
    e = seed3.get(key) or {}
    return e.get("subtitle") or ""


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    # key → slug
    key2slug = {}
    for r in csv.reader((ROOT / ".cache/slug-firstpass.tsv").open(encoding="utf-8"), delimiter="\t"):
        if len(r) >= 3 and r[0] != "key":
            key2slug[r[0]] = r[1]

    seed3 = {}
    import pickle
    p = ROOT / ".cache/seed3-promote.pkl"
    if p.exists():
        seed3 = pickle.load(p.open("rb"))

    # 非掲載 drop list
    nm = yaml.safe_load((ROOT / "data/seeds/non-manga-drop.yml").read_text(encoding="utf-8"))
    non_manga = {e["series_key"] for e in (nm.get("non_manga") or []) if e.get("series_key")}

    # merge: key → group 代表
    key2grp = {}
    auto = json.load((ROOT / "data/seeds/series-merge-auto.json").open(encoding="utf-8"))["merges"]
    for g in auto:
        mk = g.get("merge_keys") or []
        for k in mk:
            key2grp[k] = mk[0]
    hand = yaml.safe_load((ROOT / "data/seeds/series-merge.yml").read_text(encoding="utf-8")) or []
    for e in hand:
        if isinstance(e, dict):
            mk = e.get("merge_keys") or []
            if len(mk) >= 2:
                for k in mk:
                    key2grp[k] = mk[0]

    funnel = defaultdict(int)
    funnel["total_keys"] = len(key2slug)
    survivors = []   # (group_rep, slug)
    seen_groups = set()
    for key, slug in key2slug.items():
        title = title_of(key)
        sub = sub_of(key, seed3)
        # ① drop
        if any(title.startswith(p) for p in DROP_TITLE_PREFIX):
            funnel["drop_title_prefix"] += 1; continue
        if any(p in title for p in DROP_TITLE_CONTAINS):
            funnel["drop_title_contains"] += 1; continue
        if any(m in title for m in FOREIGN_MARKERS):
            funnel["drop_foreign_marker"] += 1; continue
        if key in non_manga:
            funnel["drop_non_manga_list"] += 1; continue
        if any(p in sub for p in DROP_SUBTITLE):
            funnel["drop_subtitle"] += 1; continue
        # ② merge: group 代表へ畳む(1ページ1回だけ)
        grp = key2grp.get(key, key)
        if grp in seen_groups:
            funnel["merged_into_existing"] += 1; continue
        seen_groups.add(grp)
        # 代表の slug は代表 key の slug を優先(無ければ自身)
        rep_slug = key2slug.get(grp, slug)
        survivors.append((grp, rep_slug))

    funnel["final_pages"] = len(survivors)

    # ③ 最終ページ間の slug 衝突
    slug2pages = defaultdict(list)
    for grp, slug in survivors:
        slug2pages[slug].append(grp)
    collisions = {s: ps for s, ps in slug2pages.items() if len(ps) >= 2}
    n_collide_slugs = len(collisions)
    n_collide_pages = sum(len(ps) for ps in collisions.values())

    print("=== 正しい順番(drop→merge→slug)funnel ===")
    print(f"  全 key:                    {funnel['total_keys']:,}")
    print(f"  ① drop(題接頭):            -{funnel['drop_title_prefix']:,}")
    print(f"  ① drop(題包含=関連書):     -{funnel['drop_title_contains']:,}")
    print(f"  ① drop(外国語マーカー):    -{funnel['drop_foreign_marker']:,}")
    print(f"  ① drop(非掲載list):        -{funnel['drop_non_manga_list']:,}")
    print(f"  ① drop(副題抜粋本):        -{funnel['drop_subtitle']:,}")
    print(f"  ② merge で畳まれた:        -{funnel['merged_into_existing']:,}")
    print(f"  ── 最終ページ:             {funnel['final_pages']:,}")
    print()
    print(f"  ★③ slug衝突(最終ページ間): {n_collide_slugs:,} slug / {n_collide_pages:,} ページ")

    out = [{"slug": s, "pages": ps} for s, ps in sorted(collisions.items(), key=lambda x: -len(x[1]))]
    json.dump(out, (ROOT / ".cache/final-slug-collisions.json").open("w", encoding="utf-8"), ensure_ascii=False)
    print("\n■ 最終ページ衝突の例(上位):")
    for s, ps in sorted(collisions.items(), key=lambda x: -len(x[1]))[:18]:
        ts = list(dict.fromkeys(title_of(k)[:14] for k in ps))
        print(f"   [{s}] ×{len(ps)}: " + " / ".join(ts))


if __name__ == "__main__":
    main()
