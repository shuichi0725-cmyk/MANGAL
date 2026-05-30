"""C = slug 生成の正確性 調査(プロトタイプ)。

現 makeSlug は display(漢字含む)を wanakana で romaji 化 = 漢字非対応で破綻。
CLAUDE.md 新規則 = title_kana を起点にヘボン化。 本ツールは新規則の一部
(基本ヘボン)を pykakasi で試作し、 全76,435件で:
  - カバレッジ(非空 slug 生成率)
  - slug 衝突(同名異作品)
  - 種a romaji との不一致(= 読み崩れ=誤 slug の温床)
  - title 字種分布(漢字/かな/カタカナ/数字)別の難所
を実測。 ※調査専用。 本番 slug は変更しない。

出力: .cache/slug-proto-*.tsv + stdout サマリ
"""
import pickle, csv, re, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import pykakasi

PKL = Path(".cache/seed3-promote.pkl")
TSV = Path(".cache/match-v9-all.tsv")

_kks = pykakasi.kakasi()
KATA = re.compile(r"[゠-ヿ]")
HIRA = re.compile(r"[぀-ゟ]")
KANJI = re.compile(r"[一-鿿]")
LATIN = re.compile(r"[A-Za-z]")
DIGIT = re.compile(r"[0-9０-９]")


def hepburn(kana: str) -> str:
    out = []
    for item in _kks.convert(kana):
        out.append(item["hepburn"])
    return "".join(out)


def kana_to_slug(seg: str) -> str:
    """segmented kana(空白区切り)→ ヘボン hyphen slug。"""
    parts = []
    for w in seg.split():
        r = hepburn(w).lower()
        r = re.sub(r"[^a-z0-9]+", "", r)
        if r:
            parts.append(r)
    slug = "-".join(parts)
    return slug


def base_title(key: str) -> str:
    names = [p[5:] for p in key.split("|") if p.startswith("name:")]
    return names[-1] if names else ""


def classify(title: str) -> str:
    has_k = bool(KANJI.search(title))
    has_kata = bool(KATA.search(title))
    has_hira = bool(HIRA.search(title))
    has_lat = bool(LATIN.search(title))
    has_dig = bool(DIGIT.search(title))
    if has_dig:
        return "数字含む"
    if has_lat and not (has_k or has_hira or has_kata):
        return "英字のみ"
    if has_k:
        return "漢字含む"
    if has_kata and not has_hira:
        return "カタカナ主体"
    if has_hira:
        return "ひらがな主体"
    return "その他"


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def main():
    d = pickle.load(PKL.open("rb"))
    ser = list(d.values())
    n = len(ser)

    # 種a romaji per key
    a_romaji = {}
    with TSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["verdict"].startswith("S") and r.get("a_romaji"):
                a_romaji[r["s3_key"]] = r["a_romaji"]

    cls_count = Counter()
    empty_slug = []
    slug_owners = defaultdict(list)
    mismatch = []  # (title, slug_from_kana, a_romaji_norm)
    agree = 0
    compared = 0

    for e in ser:
        key = e["key"]
        title = base_title(key)
        cls = classify(title)
        cls_count[cls] += 1
        seg = e.get("title_kana_segmented") or e.get("title_kana") or ""
        slug = kana_to_slug(seg) if seg else ""
        if not slug:
            if len(empty_slug) < 50:
                empty_slug.append((title, cls, seg))
            continue
        slug_owners[slug].append((title, key))
        # 種a romaji と比較(読み崩れ検出)
        ar = a_romaji.get(key)
        if ar:
            compared += 1
            if norm(slug) == norm(ar):
                agree += 1
            elif len(mismatch) < 400:
                mismatch.append((title, slug, ar))

    print(f"=== 全 {n:,} 件 slug プロトタイプ ===")
    print(f"非空 slug 生成: {n - sum(1 for e in ser if not (e.get('title_kana_segmented') or e.get('title_kana')))} / kana有 から")
    empty_n = sum(1 for e in ser if (e.get('title_kana_segmented') or e.get('title_kana')) and not kana_to_slug(e.get('title_kana_segmented') or e.get('title_kana') or ''))
    print(f"kana有るのに slug 空: 約 {len(empty_slug)}+ (サンプル)")

    print("\n=== title 字種分布 ===")
    for k, v in cls_count.most_common():
        print(f"  {k}: {v:,} ({v*100//n}%)")

    # 衝突
    collisions = {s: o for s, o in slug_owners.items() if len(o) > 1}
    coll_entries = sum(len(o) for o in collisions.values())
    print(f"\n=== slug 衝突 ===")
    print(f"  衝突 slug 種類: {len(collisions):,}")
    print(f"  衝突に巻き込まれた entry: {coll_entries:,}")

    print(f"\n=== 種a romaji との一致(読み崩れ検出) ===")
    print(f"  比較対象(種aマッチ有): {compared:,}")
    if compared:
        print(f"  一致: {agree:,} ({agree*100//compared}%)")
        print(f"  不一致(=読み崩れ/別表記候補): {compared - agree:,} ({(compared-agree)*100//compared}%)")

    # 出力
    with open(".cache/slug-proto-collisions.tsv", "w", encoding="utf-8") as f:
        f.write("slug\tcount\ttitles\n")
        for s, o in sorted(collisions.items(), key=lambda x: -len(x[1]))[:500]:
            f.write(f"{s}\t{len(o)}\t{' || '.join(t for t,_ in o[:6])}\n")
    with open(".cache/slug-proto-mismatch.tsv", "w", encoding="utf-8") as f:
        f.write("title\tslug_from_kana\ta_romaji\n")
        for t, s, ar in mismatch:
            f.write(f"{t}\t{s}\t{ar}\n")
    print("\nwrote .cache/slug-proto-collisions.tsv / slug-proto-mismatch.tsv")


if __name__ == "__main__":
    main()
