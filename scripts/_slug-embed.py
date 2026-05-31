"""#3 埋込外来語 = 漢字/かな題の中の loanword トークンだけ 種a 英語綴りに差替。

トークン単位ハイブリッド:
  kana_slug と a_romaji_slug を hyphen 分割 → 同数なら token 整列。
  各 token: canon 一致(長音/wo差)→ kana 維持 / 種a が英語構造 → 種a 差替。
英語構造判定 = 'l'/'x'/'q' を含む or n以外の子音で終わる(romaji は CV+n 構造)。
  → collection/armor/bear/night/blood は差替、 候(soro vs kou=読み差)は差替えない。
token 数不一致 = v14 ずれの恐れ → kana 維持(安全)。 出力 .cache/slug-embed.tsv。
"""
import csv, re, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
SRC = Path(".cache/slug-gen-v1.tsv")
VOWEL = "aeiou"
FOREIGN = re.compile(r"[゠-ヿA-Za-z]")  # カタカナ or latin = 外来語が実在する signal


def drop_long(r):
    while True:
        n = re.sub(r"ou", "o", r); n = re.sub(r"oo", "o", n); n = re.sub(r"uu", "u", n)
        if n == r: return r
        r = n


def canon(s):
    return drop_long(s.replace("wo", "o"))


def english_like(t):
    """romaji 構造でない=英語綴り候補。"""
    if not t:
        return False
    if "l" in t or "x" in t or "q" in t:   # romaji に無い字
        return True
    if t[-1] not in VOWEL and t[-1] != "n" and not t[-1].isdigit():
        return True   # n以外の子音で終わる
    return False


def hybridize(kana_slug, a_slug):
    """token 整列して埋込外来語のみ差替。 差替えなければ None。"""
    kt = kana_slug.split("-"); at = a_slug.split("-")
    if len(kt) != len(at) or not kt:
        return None
    out = []; swapped = False
    for k, a in zip(kt, at):
        if canon(k) == canon(a):
            out.append(k)
        elif english_like(a) and not english_like(k):
            out.append(a); swapped = True
        else:
            out.append(k)   # 読み差等 = kana 維持
    return "-".join(out) if swapped else None


def main():
    rows = list(csv.DictReader(SRC.open(encoding="utf-8"), delimiter="\t"))
    fixes = []
    for r in rows:
        if r["class"] not in ("kanji", "hira", "other"):
            continue
        if not FOREIGN.search(r["title"]):
            continue   # display に外来語(カタカナ/latin)が無い = 埋込外来語は存在しない
        ks = r["kana_slug"]; ars = r["a_romaji_slug"]
        if not ks or not ars:
            continue
        hy = hybridize(ks, ars)
        if hy and hy != ks:
            fixes.append((r["title"], ks, ars, hy))

    with open(".cache/slug-embed.tsv", "w", encoding="utf-8") as f:
        f.write("title\tkana_slug\ta_romaji_slug\thybrid\n")
        for t, ks, ars, hy in fixes:
            f.write(f"{t}\t{ks}\t{ars}\t{hy}\n")
    print(f"埋込外来語 差替: {len(fixes):,} 件 → .cache/slug-embed.tsv")
    print("\n=== サンプル30(title / kana → hybrid)===")
    for t, ks, ars, hy in fixes[:30]:
        print(f"  {t[:24]:<24} {ks[:26]:<26} → {hy[:30]}")


if __name__ == "__main__":
    main()
