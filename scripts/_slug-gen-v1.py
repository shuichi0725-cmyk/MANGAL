"""slug 生成器 v1 = title_kana_segmented 起点ヘボン + 確定4ルール + 種a候補並記。

確定ルール(★2026-06-10 ユーザ裁定 = 5/31裁定を上書き。 _slug_rules.py 共用):
  ① 長音保持: おう→ou / うう→uu 逐字(mahouka-koukou)。 定着固有名詞(tokyo等)は定着綴り
  ② 助詞「を」= o(ヘボン標準。 旧 wo を反転)
  ③ 敬称ハイフン: サマ/サン/チャン/クン/ドノ/センパイ を独立 hyphen part に
  ④ カタカナ外来語: 種a romaji/english の元綴り(本スクリプトは候補並記、 採否は分岐で)

出力 .cache/slug-gen-v1.tsv に kana_slug / a_romaji_slug / a_english_slug を並記 →
実データで分岐(どれを採るか)を裁定する。 ※適用しない(レビュー用)。
"""
import pickle, csv, re, sys, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import pykakasi

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _slug_rules as SR

PKL = Path(".cache/seed3-promote.pkl")
MATCH = Path(".cache/match-v14-all.tsv")
S = {"S180", "S150", "S130", "S100"}
_kks = pykakasi.kakasi()

KATA = re.compile(r"[゠-ヿ]")
HIRA = re.compile(r"[぀-ゟ]")
KANJI = re.compile(r"[一-鿿]")
LATIN = re.compile(r"[A-Za-z]")
DIGIT = re.compile(r"[0-9０-９]")
HONORIFICS = ("サマ", "サン", "チャン", "クン", "ドノ", "センパイ", "タン")


def hep(kana):
    return "".join(it["hepburn"] for it in _kks.convert(kana)).lower()


def drop_long(r):
    """旧①長音落とし(5/31裁定=廃止)。 ★slug生成では使わない。
    音写骨格比較(v2 is_onsha)等の正規化用途でのみ残存。"""
    r = re.sub(r"ou", "o", r)
    r = re.sub(r"oo", "o", r)
    r = re.sub(r"uu", "u", r)
    return r


def split_honorific(word):
    """確定③ 敬称を語末で分離(独立 hyphen part 化)。"""
    for h in HONORIFICS:
        if word.endswith(h) and len(word) > len(h):
            return [word[: -len(h)], word[-len(h):]]
    return [word]


def kana_slug(seg):
    """segmented kana → ヘボン hyphen slug(★2026-06-10 規則: 長音保持/ヲ=o)。"""
    parts = []
    for w in seg.split():
        for sub in split_honorific(w):
            r = SR.token_roman(sub)
            if r:
                parts.append(r)
    return "-".join(parts)


def slugify_latin(s):
    """ラテン文字列 → slug(空白/記号 hyphen)。"""
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def classify(title):
    has_k = bool(KANJI.search(title)); has_kata = bool(KATA.search(title))
    has_hira = bool(HIRA.search(title)); has_lat = bool(LATIN.search(title))
    has_dig = bool(DIGIT.search(title))
    if has_lat and not (has_k or has_hira or has_kata):
        return "latin"
    if has_dig:
        return "num"
    if has_kata and not (has_k or has_hira):
        return "kata"
    if has_k:
        return "kanji"
    if has_hira:
        return "hira"
    return "other"


def base_title(key):
    ns = [p[5:] for p in key.split("|") if p.startswith("name:")]
    return ns[-1] if ns else ""


def main():
    d = pickle.load(PKL.open("rb"))
    a_rom, a_eng = {}, {}
    with MATCH.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["verdict"] in S:
                if r.get("a_romaji"): a_rom[r["s3_key"]] = r["a_romaji"]
                if r.get("a_english"): a_eng[r["s3_key"]] = r["a_english"]

    rows = []
    cls_count = Counter()
    for e in d.values():
        key = e["key"]; title = base_title(key)
        seg = e.get("title_kana_segmented") or e.get("title_kana") or ""
        cls = classify(title); cls_count[cls] += 1
        ks = kana_slug(seg) if seg else ""
        ar = a_rom.get(key, ""); ae = a_eng.get(key, "")
        rows.append((key, title, cls, seg, ks, ar, slugify_latin(ar), ae, slugify_latin(ae)))

    with open(".cache/slug-gen-v1.tsv", "w", encoding="utf-8") as f:
        f.write("key\ttitle\tclass\tkana_seg\tkana_slug\ta_romaji\ta_romaji_slug\ta_english\ta_english_slug\n")
        for row in rows:
            f.write("\t".join(str(x) for x in row) + "\n")

    print(f"=== 全 {len(rows):,} 件 ===")
    for k, v in cls_count.most_common():
        print(f"  {k}: {v:,} ({v*100//len(rows)}%)")
    print("wrote .cache/slug-gen-v1.tsv")

    # 検証: CLAUDE.md 既知例
    print("\n=== 既知例の検証 ===")
    want = ["鬼滅の刃","進撃の巨人","七つの大罪","ベルセルク","ワンピース","ONE PIECE","ナルト",
            "東京喰種","鋼の錬金術師","らんま", "幽☆遊☆白書","ドラゴンボール"]
    by_title = {}
    for row in rows:
        by_title.setdefault(row[1], row)
    for w in want:
        hit = [row for row in rows if w in row[1]]
        if hit:
            row = sorted(hit, key=lambda r: len(r[1]))[0]
            print(f"  {row[1][:20]:<20} [{row[2]}] kana={row[4]}  a_rom={row[6]}  a_eng={row[8]}")


if __name__ == "__main__":
    main()
