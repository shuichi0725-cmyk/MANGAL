"""最終ページの slug 衝突(.cache/final-slug-collisions.json)を、 ★著者qid を主軸に
4 バケットへ分類する (dry-run, read-only)。 ★id でなく著者qid で判定(誤分類の教訓)。

判定:
  共通base題 = 最短norm題が他全部に embed (= 系統 franchise の証拠)
  著者共通    = 全ページの著者qid集合の積が非空 (= 同一作者が全部に居る)
  同一aid     = 全ページの非None anilist_id が1つに一致 (= AniList同一作)
バケット:
  MERGE_franchise = 共通base ∧ 著者共通          (こわい本/みこすり半 = 同作者の系統 → 統合)
  MERGE_samework  = 同一aid ∧ 著者共通 (base無)   (ONE PIECE=ワンピース = 表記違い → 統合)
  ANTHOLOGY       = 共通base ∧ 著者バラバラ        (on BLUE = アンソロジー誌の号 → 要レビュー)
  SUFFIX          = 上記以外                        (鬼/男弐, 別作の同音 → 別slug)
出力: .cache/final-collision-buckets.json
"""
import json
import sys
import re
import unicodedata
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HIRA = str.maketrans({chr(c): chr(c + 0x60) for c in range(0x3041, 0x3097)})
STRIP = re.compile(r"[・･\s　.\-,，。!！?？=~〜:：\"'’]")


def title_of(key):
    names = [s[5:] for s in key.split("|") if s.startswith("name:")]
    return names[-1] if names else key


def norm(t):
    t = unicodedata.normalize("NFKC", t or "").lower().translate(HIRA)
    return STRIP.sub("", t)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    collisions = json.load((ROOT / ".cache/final-slug-collisions.json").open(encoding="utf-8"))
    en = json.load((ROOT / ".cache/anilist-enrich-map.json").open(encoding="utf-8"))

    con = sqlite3.connect(ROOT / ".cache/db-v2.sqlite")
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    key2sid = {k: s for s, k in con.execute("SELECT id, series_key FROM series")}

    def author_qids(key):
        sid = key2sid.get(key)
        if not sid:
            return set()
        return {q for (q,) in con.execute(
            "SELECT m.qid FROM series_authors sa JOIN mangaka m ON m.id=sa.mangaka_id "
            "WHERE sa.series_id=? AND m.qid IS NOT NULL AND m.qid!=''", (sid,))}

    buckets = {"MERGE_franchise": [], "MERGE_samework": [], "ANTHOLOGY": [], "SUFFIX": []}
    for c in collisions:
        slug, pages = c["slug"], c["pages"]
        titles = [norm(title_of(k)) for k in pages]
        nz = [t for t in titles if t]
        short = min(nz, key=len) if nz else ""
        common_base = len(short) >= 2 and all(short in t for t in nz)
        # 著者共通 = 積が非空
        auth_sets = [author_qids(k) for k in pages]
        auth_sets_nonempty = [a for a in auth_sets if a]
        author_common = bool(auth_sets_nonempty) and bool(set.intersection(*auth_sets_nonempty)) \
            if len(auth_sets_nonempty) == len(pages) and auth_sets_nonempty else False
        # 同一aid
        aids = {(en.get(k) or {}).get("anilist_id") for k in pages}
        aids = {a for a in aids if a}
        same_aid = len(aids) == 1

        rec = {"slug": slug, "pages": pages, "titles": [title_of(k) for k in pages]}
        if common_base and author_common:
            buckets["MERGE_franchise"].append(rec)
        elif same_aid and author_common:
            buckets["MERGE_samework"].append(rec)
        elif common_base and not author_common:
            buckets["ANTHOLOGY"].append(rec)
        else:
            buckets["SUFFIX"].append(rec)

    print(f"最終衝突 {len(collisions)} slug の分類(著者qid主軸):")
    for k, v in buckets.items():
        print(f"  {k:16}: {len(v):,} slug / {sum(len(r['pages']) for r in v):,} ページ")
    for bk in buckets:
        print(f"\n■ {bk} の例:")
        for r in sorted(buckets[bk], key=lambda x: -len(x["pages"]))[:8]:
            ts = list(dict.fromkeys(t[:14] for t in r["titles"]))
            print(f"   [{r['slug']}] ×{len(r['pages'])}: " + " / ".join(ts[:6]))
    json.dump(buckets, (ROOT / ".cache/final-collision-buckets.json").open("w", encoding="utf-8"), ensure_ascii=False)
    print(f"\n→ .cache/final-collision-buckets.json")


if __name__ == "__main__":
    main()
