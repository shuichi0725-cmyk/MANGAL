"""種2 ISBN誤join 監査 = 巻のISBN由来読みが series 題と乖離する外れ巻を検出。

例: 上杉謙信のISBNがゴルゴ13 series に紐付く型。 MADB ISBN→ja-hrkt 読みを使い、
各 series の各巻について「巻ISBNの読み」vs「series題の読み」を比較。
  - 巻ISBN読みが series題読みと大きく乖離(kata正規化で不一致)
  - かつ その巻ISBN読みが別 series の題読みと一致(=本来そっちの巻)
  - かつ series 内で少数派(多数巻は series題と一致)
を満たす巻を「誤join候補」として出力。 ※調査のみ・本番不変。
出力: .cache/isbn-misjoin.tsv
"""
import sqlite3, csv, sys, re, unicodedata, difflib
from collections import defaultdict
from pathlib import Path


def sim(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0

sys.stdout.reconfigure(encoding="utf-8")
DB = Path(".cache/db-v2.sqlite")
MADB = Path(".cache/madb-isbn-kana.tsv")
SMALL = str.maketrans("ァィゥェォッャュョ", "アイウエオツヤユヨ")


def kata_norm(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)
    s = "".join(ch for ch in s if unicodedata.category(ch)[0] != "P" and ch not in "ー―‐~〜　 ")
    return s.translate(SMALL)


def prefix_match(a, b):
    """一方が他方の先頭部分(>=60%)= 同作の副題差。"""
    if not a or not b:
        return False
    s, l = (a, b) if len(a) <= len(b) else (b, a)
    return l.startswith(s) and len(s) >= len(l) * 0.6


def main():
    # ISBN -> [読み(kata-norm)]
    isbn_kana = {}
    with MADB.open(encoding="utf-8") as f:
        for r in csv.reader(f, delimiter="\t"):
            if len(r) >= 3 and r[2]:
                ks = {kata_norm(k) for k in r[2].split("|") if k}
                isbn_kana[r[0]] = {k for k in ks if k}

    con = sqlite3.connect(DB); con.text_factory = lambda b: b.decode("utf-8", "replace")
    c = con.cursor()
    # series -> title_kana(norm), title
    s_kana = {}; s_title = {}
    for sid, t, tk in c.execute("SELECT id, title, title_kana FROM series"):
        s_title[sid] = t
        s_kana[sid] = kata_norm(tk) if tk else ""
    # series -> [(isbn, set(kana))]
    s_vols = defaultdict(list)
    for sid, isbn in c.execute("""SELECT s.id, v.isbn13 FROM series s
        JOIN editions e ON e.series_id=s.id JOIN volumes v ON v.edition_id=e.id
        WHERE v.isbn13 IS NOT NULL"""):
        key = str(isbn).replace("-", "").strip()
        ks = isbn_kana.get(key)
        if ks:
            s_vols[sid].append((key, ks))
    con.close()

    # 逆引き: kata-norm 題読み -> [sid](誤join先の特定用、 短すぎる読みは除外)
    kana2sids = defaultdict(list)
    for sid, kn in s_kana.items():
        if len(kn) >= 3:
            kana2sids[kn].append(sid)

    def vol_matches_series(ks, skana):
        """巻読み set が series題読みと一致 or prefix。"""
        if not skana:
            return True  # series題読み無し=判定不能、 外れ扱いしない
        for k in ks:
            if k == skana or prefix_match(k, skana):
                return True
        return False

    suspects = []
    for sid, vols in s_vols.items():
        skana = s_kana.get(sid, "")
        if not skana or len(vols) < 2:
            continue
        # series内で series題と一致する巻が多数か(=基準が正しい)
        n_match = sum(1 for _, ks in vols if vol_matches_series(ks, skana))
        if n_match < len(vols) * 0.5:
            continue  # 多数が不一致 = title_kana 自体が怪しい(別問題)、 ここでは除外
        for isbn, ks in vols:
            if vol_matches_series(ks, skana):
                continue
            # ★巻読みのどれかが series題と類似(表記揺れ/副題)なら誤joinでない
            if max((sim(k, skana) for k in ks), default=0) >= 0.5:
                continue
            # 外れ巻: その読みが別 series 題と一致 かつ その別題は series題と非類似
            #   (= 分裂/表記揺れ/副題でなく、 真に無関係な作品 = 誤join)
            real = []
            for k in ks:
                for osid in kana2sids.get(k, []):
                    if osid == sid:
                        continue
                    if sim(s_kana.get(osid, ""), skana) >= 0.5:
                        continue  # 別sidだが題が類似=分裂/変種、 誤joinでない
                    real.append(s_title[osid])
            real = list(dict.fromkeys(real))
            if not real:
                continue  # 真の誤join元が特定できない=確度低、 除外
            suspects.append((s_title[sid], isbn, " / ".join(sorted(ks))[:24],
                             skana[:20], " | ".join(real[:2])))

    suspects.sort(key=lambda x: (x[0], x[1]))
    with open(".cache/isbn-misjoin.tsv", "w", encoding="utf-8") as f:
        f.write("series_title\tvol_isbn\tvol_kana\tseries_kana\tlikely_real_series\n")
        for row in suspects:
            f.write("\t".join(str(x) for x in row) + "\n")
    with_real = [s for s in suspects if s[4]]
    print(f"=== ISBN誤join 監査 ===")
    print(f"  外れ巻(series題と乖離): {len(suspects):,}")
    print(f"  ★うち別seriesに一致(誤join元特定=高確度): {len(with_real):,}")
    print(f"  wrote .cache/isbn-misjoin.tsv")
    print("\n=== 高確度サンプル20(series / 巻ISBN読み → 本来のseries)===")
    for t, isbn, vk, sk, real in with_real[:20]:
        print(f"  「{t[:18]}」← 巻[{vk[:16]}] = 本来「{real[:24]}」")


if __name__ == "__main__":
    main()
