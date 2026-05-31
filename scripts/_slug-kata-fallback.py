"""#4 kata fallback = 種a無のカタカナ題を 学習辞書で英語綴り化。

未マッチ kata 題の title_kana_segmented を token 分割し、 kata-dict にあれば
英語綴り、 無ければ phonetic ヘボン(長音落とし)。 → .cache/slug-kata-fallback.tsv。
"""
import csv, json, re, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import pykakasi
_kks = pykakasi.kakasi()
SRC = Path(".cache/slug-gen-v1.tsv")
DICT = Path(".cache/kata-dict.json")


def hep(kana):
    return "".join(it["hepburn"] for it in _kks.convert(kana)).lower()


def drop_long(r):
    while True:
        n = re.sub(r"ou", "o", r); n = re.sub(r"oo", "o", n); n = re.sub(r"uu", "u", n)
        if n == r: return r
        r = n


def phon(tok):
    return re.sub(r"[^a-z0-9]+", "", drop_long(hep(tok)))


def main():
    d = json.loads(DICT.read_text(encoding="utf-8"))
    rows = list(csv.DictReader(SRC.open(encoding="utf-8"), delimiter="\t"))
    out = []
    hits = total = 0
    for r in rows:
        if r["class"] != "kata" or r["a_romaji_slug"]:
            continue
        seg = r["kana_seg"]
        if not seg:
            continue
        parts = []
        th = 0
        for tok in seg.split():
            total += 1
            if tok in d:
                parts.append(d[tok]); hits += 1; th += 1
            else:
                p = phon(tok)
                if p: parts.append(p)
        new = "-".join(p for p in parts if p)
        out.append((r["title"], r["kana_slug"], new, th, len(seg.split())))

    with open(".cache/slug-kata-fallback.tsv", "w", encoding="utf-8") as f:
        f.write("title\told_phonetic\tnew_dict\tdict_hits\ttokens\n")
        for t, o, n, th, nt in out:
            f.write(f"{t}\t{o}\t{n}\t{th}\t{nt}\n")
    changed = sum(1 for t, o, n, th, nt in out if n != o)
    print(f"kata fallback: {len(out):,} 件  / 辞書改善あり: {changed:,}")
    print(f"token 辞書ヒット率: {hits:,}/{total:,} ({hits*100//max(total,1)}%)")
    print("\n=== 改善サンプル35(title / 旧phonetic → 新dict)===")
    shown = 0
    for t, o, n, th, nt in out:
        if n != o:
            print(f"  {t[:22]:<22} {o[:26]:<26} → {n[:30]}")
            shown += 1
            if shown >= 35: break


if __name__ == "__main__":
    main()
