"""slug-gen-v1.tsv に分岐 policy を適用して chosen slug を決定 + 衝突/要レビュー集計。

policy:
  - kata/latin + 種a romaji 有 → 種a romaji_slug(外来語=元綴り、 rule④)
  - それ以外(kanji/hira) → kana_slug(ヘボン+確定ルール)
  - num → 暫定 kana_slug(★4分岐は別途)= branch=num-TODO
要レビュー: (a)kanji で kana≠a_rom(埋込外来語 tokyo-ghoul 型) (b)kata で 種a無(beruseruku fallback)
出力: .cache/slug-chosen.tsv + .cache/slug-collisions.tsv + stdout 集計。 ※適用しない。
"""
import csv, re, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
SRC = Path(".cache/slug-gen-v1.tsv")


def drop_long(r):
    """安定するまで長音畳み(比較用 canonical 化、 冪等)。"""
    while True:
        n = re.sub(r"ou", "o", r); n = re.sub(r"oo", "o", n); n = re.sub(r"uu", "u", n)
        if n == r:
            return r
        r = n


def canon(s):
    """系統的な kana↔種a 差(長音/wo/ハイフン)を吸収した比較用 canonical。"""
    return drop_long(s.replace("-", "")).replace("wo", "o")


def same_ignoring_long(a, b):
    """長音/wo/ハイフン差だけなら True(= 我々のルールで一致、 埋込外来語でない)。"""
    return canon(a) == canon(b)


def main():
    rows = list(csv.DictReader(SRC.open(encoding="utf-8"), delimiter="\t"))
    chosen = []
    branch_count = Counter()
    review_embed = []   # kanji/hira で kana≠a_rom(埋込外来語候補)
    review_katanoa = []  # kata で 種a無(fallback beruseruku)
    for r in rows:
        cls = r["class"]; ks = r["kana_slug"]; ars = r["a_romaji_slug"]
        if cls == "num":
            sl, br = ks, "num-TODO"
        elif cls in ("kata", "latin"):
            if ars:
                sl, br = ars, "anilist"
            else:
                sl, br = ks, "kana-fallback"
                if ks: review_katanoa.append(r)
        else:  # kanji/hira/other
            sl, br = ks, "kana"
            # 長音差だけは我々のルール通り=レビュー不要。 真に異なる=埋込外来語候補のみ
            if ars and ars != ks and not same_ignoring_long(ks, ars):
                review_embed.append((r, ks, ars))
        chosen.append((r["key"], r["title"], cls, br, sl))
        branch_count[br] += 1

    nonempty = sum(1 for c in chosen if c[4])
    print(f"=== chosen slug: {len(chosen):,} 件 ===")
    print(f"  非空: {nonempty:,} ({nonempty*100//len(chosen)}%) / 空: {len(chosen)-nonempty}")
    print("  branch 内訳:")
    for k, v in branch_count.most_common():
        print(f"    {k}: {v:,}")

    # 衝突
    owners = defaultdict(list)
    for k, t, cls, br, sl in chosen:
        if sl:
            owners[sl].append((t, k))
    coll = {s: o for s, o in owners.items() if len(o) > 1}
    print(f"\n=== 衝突 ===")
    print(f"  衝突 slug 種類: {len(coll):,} / 巻き込まれ entry: {sum(len(o) for o in coll.values()):,}")

    print(f"\n=== 要レビュー ===")
    print(f"  (a) kanji/hira で kana≠種a(埋込外来語 tokyo-ghoul 型): {len(review_embed):,}")
    print(f"  (b) kata で 種a無(beruseruku fallback): {len(review_katanoa):,}")

    with open(".cache/slug-chosen.tsv", "w", encoding="utf-8") as f:
        f.write("key\ttitle\tclass\tbranch\tslug\n")
        for row in chosen:
            f.write("\t".join(str(x) for x in row) + "\n")
    with open(".cache/slug-collisions.tsv", "w", encoding="utf-8") as f:
        f.write("slug\tcount\ttitles\n")
        for s, o in sorted(coll.items(), key=lambda x: -len(x[1]))[:600]:
            f.write(f"{s}\t{len(o)}\t{' || '.join(t for t,_ in o[:6])}\n")
    with open(".cache/slug-review-embed.tsv", "w", encoding="utf-8") as f:
        f.write("title\tkana_slug\ta_romaji_slug\n")
        for r, ks, ars in review_embed:
            f.write(f"{r['title']}\t{ks}\t{ars}\n")
    print("\nwrote .cache/slug-chosen.tsv / slug-collisions.tsv / slug-review-embed.tsv")

    print("\n=== 埋込外来語候補サンプル20(kana vs 種a)===")
    for r, ks, ars in review_embed[:20]:
        print(f"  {r['title'][:22]:<22} kana={ks[:24]:<24} 種a={ars[:24]}")


if __name__ == "__main__":
    main()
