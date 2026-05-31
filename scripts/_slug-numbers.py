"""数字タイトル(2,943件)の slug 4分岐(CLAUDE.md 規則3)。

segmented kana は数字を読みに展開(2020→ニセン ニジュウ)し、 数字部を独立
セグメント化する。 これを利用し、 表示題の算用数字(digit-run)と kana の
数字読みグループを「出現順」で対応付け、 読みの種類で分岐:
  - 音読み数詞(ジュウ/ヒャク/セン/イチ/ニ/ゴ…)→ 算用数字 keep(15歳→15-sai, 2020 keep)
  - 訓読み(ヨン/ナナ/…ツ)→ ヘボン(4コマ→yonkoma, 七つ→nanatsu)
  - 英語読み(ワン/ティーン/シックスティ…)→ 算用数字 keep(persona-5, ak-69)
  - 分数(表示に "/")→ ヘボン(らんま1/2→nibunnoichi)
表示にラテン文字があれば keep(AK→ak)。 ※調査用、 .cache/slug-numbers.tsv に出力。
"""
import pickle, re, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import pykakasi
_kks = pykakasi.kakasi()
PKL = Path(".cache/seed3-promote.pkl")

DIGIT = re.compile(r"[0-9０-９]")
LATIN = re.compile(r"[A-Za-z]")

# 数字読み形態素
ON = ["ジュウ", "ヒャク", "ビャク", "ピャク", "セン", "ゼン", "マン",
      "イチ", "ニ", "サン", "シ", "ゴ", "ロク", "シチ", "ハチ", "キュウ", "ク",
      "ゼロ", "レイ", "マル"]
KUN_TSU = ["ヒトツ", "フタツ", "ミッツ", "ヨッツ", "イツツ", "ムッツ", "ナナツ",
           "ヤッツ", "ココノツ", "トオ"]
KUN_NUM = ["ヨン", "ナナ", "ヒト", "フタ", "ミ", "ヨ", "イツ", "ム", "ヤ", "ココノ"]
EN_NUM = ["ゼロ", "ワン", "ツー", "スリー", "フォー", "フォア", "ファイブ", "ファイヴ",
          "シックス", "セブン", "エイト", "ナイン", "テン", "イレブン", "トゥエルブ",
          "ティーン", "トゥエンティ", "サーティ", "フォーティ", "フィフティ",
          "シックスティ", "セブンティ", "エイティ", "ナインティ", "ハンドレッド"]


def hep(kana):
    return "".join(it["hepburn"] for it in _kks.convert(kana)).lower()


def drop_long(r):
    while True:
        n = re.sub(r"ou", "o", r); n = re.sub(r"oo", "o", n); n = re.sub(r"uu", "u", n)
        if n == r: return r
        r = n


def romaji(kana):
    r = drop_long(hep(kana))
    return re.sub(r"[^a-z0-9]+", "", r)


def starts_any(s, lst):
    for w in lst:
        if s.startswith(w):
            return w
    return None


def classify_seg(seg):
    """数字読みセグメントを分類。 返り: (type, number_kana_prefix, counter_rest) or None。
    type ∈ 'en'/'kun'/'on'。 数字読みで始まらなければ None。"""
    # english は ティーン/シックスティ 等を含むので contains も見る
    if any(w in seg for w in ("ティーン",)) or starts_any(seg, EN_NUM):
        return ("en", seg, "")
    if starts_any(seg, KUN_TSU):
        return ("kun", seg, "")
    k = starts_any(seg, KUN_NUM)
    if k:
        return ("kun", seg, "")
    # on'yomi: 先頭から on 形態素を貪欲に消費
    i = 0; consumed = False
    while i < len(seg):
        w = None
        for cand in ON:
            if seg.startswith(cand, i):
                w = cand; break
        if not w:
            break
        i += len(w); consumed = True
    if consumed:
        return ("on", seg[:i], seg[i:])
    return None


def base_title(key):
    ns = [p[5:] for p in key.split("|") if p.startswith("name:")]
    return ns[-1] if ns else ""


def make_slug(title, seg):
    # 表示題の digit-run を順に
    digit_runs = re.findall(r"[0-9０-９]+", title)
    is_fraction = bool(re.search(r"[0-9０-９]\s*[/／]\s*[0-9０-９]", title))
    di = 0
    parts = []
    segs = seg.split()
    j = 0
    while j < len(segs):
        s = segs[j]
        cl = classify_seg(s)
        if cl and not is_fraction:
            typ, numk, rest = cl
            # 連続する数字読みセグメントを同一 number にまとめる(ニセン ニジュウ=2020)
            grp = [s]; jj = j + 1
            while jj < len(segs) and classify_seg(segs[jj]) and not rest:
                # rest(=counter付)が出たら打ち切り
                nxt = classify_seg(segs[jj])
                grp.append(segs[jj]); jj += 1
                if nxt[2]:
                    break
            digit = digit_runs[di] if di < len(digit_runs) else ""
            if typ in ("on", "en") and digit:
                # 数字 keep。 counter rest があれば romanize して付与
                out = digit
                if rest:
                    rr = romaji(rest)
                    if rr: out = f"{digit}-{rr}"
                parts.append(out)
                di += 1
            else:  # kun / 数字無 → 読みromanize
                rr = romaji("".join(grp))
                if rr: parts.append(rr)
                if typ in ("on", "en"):
                    di += 1
            j = jj
            continue
        # 非数字セグメント
        if LATIN.search(s):
            parts.append(re.sub(r"[^a-z0-9]+", "", s.lower()))
        else:
            rr = romaji(s)
            if rr: parts.append(rr)
        j += 1
    # 分数は読みそのまま(nibunnoichi)= 上の通常romanizeで処理済
    return "-".join(p for p in parts if p)


def main():
    d = pickle.load(PKL.open("rb"))
    rows = []
    for e in d.values():
        t = base_title(e["key"])
        if not DIGIT.search(t):
            continue
        seg = e.get("title_kana_segmented") or e.get("title_kana") or ""
        if not seg:
            continue
        rows.append((t, seg, make_slug(t, seg)))
    with open(".cache/slug-numbers.tsv", "w", encoding="utf-8") as f:
        f.write("title\tseg\tslug\n")
        for t, s, sl in rows:
            f.write(f"{t}\t{s}\t{sl}\n")
    print(f"数字タイトル: {len(rows):,}  → .cache/slug-numbers.tsv")
    print("\n=== サンプル ===")
    tests = ["麻雀放浪記2020", "AK-69の泣きメシ", "ペルソナ5", "255の5コマ",
             "公爵夫人の50のお茶レシピ", "秘蜜なbody 21", "カラスマ0条探題",
             "ソードアート・オンライン 4コマ公式アンソロジー", "139"]
    by = {t: sl for t, s, sl in rows}
    for t in tests:
        hit = [sl for tt, s, sl in rows if tt == t]
        if hit:
            print(f"  {t[:30]:<30} → {hit[0]}")
    # 1/2 系 / 七つ 系も探す
    print("\n=== 分数/訓 サンプル ===")
    n = 0
    for t, s, sl in rows:
        if "/" in t or "／" in t:
            print(f"  {t[:30]:<30} → {sl}"); n += 1
            if n >= 6: break


if __name__ == "__main__":
    main()
