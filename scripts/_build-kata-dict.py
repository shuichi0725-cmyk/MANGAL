"""カタカナ→英語綴り 辞書を 種aマッチ済み題から学習(#4 kata fallback 用)。

種aマッチ題は a_romaji が元綴り(ソード アート→sword art)。 title_kana_segmented
(カタカナ token)と a_romaji_slug(hyphen token)を同数時に整列し、
  katakana_token → english_token(英語構造のもの)
を頻度集計。 → .cache/kata-dict.json。 未マッチ kata 題に適用して phonetic を改善。
"""
import csv, json, re, sys
from collections import defaultdict, Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import pykakasi
_kks = pykakasi.kakasi()
SRC = Path(".cache/slug-gen-v1.tsv")
VOWEL = "aeiou"


def hep(kana):
    return "".join(it["hepburn"] for it in _kks.convert(kana)).lower()


def drop_long(r):
    while True:
        n = re.sub(r"ou", "o", r); n = re.sub(r"oo", "o", n); n = re.sub(r"uu", "u", n)
        if n == r: return r
        r = n


def phon(tok):
    return re.sub(r"[^a-z0-9]+", "", drop_long(hep(tok)))


def english_like(t):
    if not t: return False
    if "l" in t or "x" in t or "q" in t: return True
    if t[-1] not in VOWEL and t[-1] != "n" and not t[-1].isdigit(): return True
    return False


def main():
    rows = list(csv.DictReader(SRC.open(encoding="utf-8"), delimiter="\t"))
    pairs = defaultdict(Counter)   # katakana_token → Counter(english_token)
    used = 0
    for r in rows:
        seg = r["kana_seg"]; ars = r["a_romaji_slug"]
        if not seg or not ars:
            continue
        ktoks = seg.split()
        atoks = ars.split("-")
        if len(ktoks) != len(atoks):
            continue
        used += 1
        for kt, at in zip(ktoks, atoks):
            if not re.search(r"[゠-ヿ]", kt):   # カタカナ token のみ
                continue
            # ★真の loanword 綴りのみ学習: phonetic と異なり、 かつ「長音を戻しただけ」
            #   (ショウジョ→shoujo 等の日本語長音語)は除外(drop_long(英)==phonetic)。
            p = phon(kt)
            if at and at != p and drop_long(at) != p:
                pairs[kt][at] += 1

    # 確定辞書: 最頻 english が支配的(>=60%) かつ count>=2
    d = {}
    for kt, c in pairs.items():
        top, n = c.most_common(1)[0]
        total = sum(c.values())
        if n >= 2 and n / total >= 0.6 and top:
            d[kt] = top
    Path(".cache/kata-dict.json").write_text(json.dumps(d, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"整列に使った題: {used:,}")
    print(f"学習 katakana→english 辞書: {len(d):,} エントリ → .cache/kata-dict.json")
    print("\n=== 高頻度マッピング サンプル40 ===")
    freq = sorted(pairs.items(), key=lambda x: -sum(x[1].values()))
    shown = 0
    for kt, c in freq:
        if kt in d:
            print(f"  {kt:<10} → {d[kt]:<16} (n={c.most_common(1)[0][1]}/{sum(c.values())})")
            shown += 1
            if shown >= 40: break


if __name__ == "__main__":
    main()
