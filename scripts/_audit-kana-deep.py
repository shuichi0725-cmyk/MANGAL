"""Q2 深掘り: ④(種3≠MADB・種a裁定不可)から真の base 読み誤りを絞る。

種3 は権威 MADB と違う。 副題/長音/英語題ノイズを除き、 base 読みが乖離してる
= 種3 誤読候補。 ★ただし MADB 自体も誤あり(②/GS美神)なので、 ここでは
「種3 が MADB と base から乖離」を抽出するだけ(確定訂正は Wikipedia 等3ソース後)。
出力: .cache/kana-deep-suspect.tsv(乖離度順)。 調査のみ。
"""
import pickle, csv, sqlite3, re, sys, unicodedata, difflib
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import pykakasi

PKL = Path(".cache/seed3-promote.pkl")
MADB_KANA = Path(".cache/madb-isbn-kana.tsv")
MATCH = Path(".cache/match-v14-all.tsv")
DB = Path(".cache/db-v2.sqlite")
S = {"S180", "S150", "S130", "S100"}
_kks = pykakasi.kakasi()
SMALL = str.maketrans("ァィゥェォッャュョ", "アイウエオツヤユヨ")


def kata_norm(s):
    if not s: return ""
    s = unicodedata.normalize("NFKC", s)
    s = "".join(chr(ord(c)+0x60) if "ぁ" <= c <= "ゖ" else c for c in s)
    s = "".join(ch for ch in s if unicodedata.category(ch)[0] != "P" and ch not in "ー―‐~〜　 ")
    return s.translate(SMALL)


def hep(kana):
    return "".join(it["hepburn"] for it in _kks.convert(kana)).lower()


def a_norm(r):
    r = re.sub(r"[^a-z]", "", r.lower())
    r = r.replace("wo", "o")
    r = re.sub(r"(.)\1+", r"\1", r).replace("ou", "o").replace("ei", "e")
    return re.sub(r"(.)\1+", r"\1", r)


def base_title(key):
    ns = [p[5:] for p in key.split("|") if p.startswith("name:")]
    return ns[-1] if ns else ""


def prefix_ok(a, b):
    """一方が他方の prefix(=副題差)なら True。"""
    if not a or not b: return False
    s, l = (a, b) if len(a) <= len(b) else (b, a)
    return l.startswith(s) and len(s) >= len(l) * 0.5


def main():
    d = pickle.load(PKL.open("rb"))
    isbn_kana = {}
    with MADB_KANA.open(encoding="utf-8") as f:
        for r in csv.reader(f, delimiter="\t"):
            if len(r) >= 3 and r[2]:
                isbn_kana[r[0]] = [k for k in r[2].split("|") if k]
    con = sqlite3.connect(DB); con.text_factory = lambda b: b.decode("utf-8", "replace")
    sk_madb = defaultdict(list)
    for sk, isbn in con.execute("""SELECT s.series_key, v.isbn13 FROM series s
        JOIN editions e ON e.series_id=s.id JOIN volumes v ON v.edition_id=e.id WHERE v.isbn13 IS NOT NULL"""):
        for k in isbn_kana.get(str(isbn).replace("-", "").strip(), []):
            sk_madb[sk].append((k, kata_norm(k)))
    con.close()
    sk_a = {}
    with MATCH.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["verdict"] in S and r.get("a_romaji"):
                sk_a[r["s3_key"]] = a_norm(re.split(r"[:：]\s", r["a_romaji"], 1)[0])

    suspect = []
    for e in d.values():
        key = e["key"]; kana = e.get("title_kana") or ""
        if not kana: continue
        k3 = kata_norm(kana)
        madb = sk_madb.get(key, [])
        if not madb: continue
        norms = {m for _, m in madb}
        if k3 in norms: continue                       # ① 正当
        a = sk_a.get(key)
        if a and (k3 == a or any(m == a for m in madb)):  # ②③ は別処理済/種3正
            continue
        # ④: MADB と base 乖離? 最良MADBとの類似 + prefix判定
        best = max(madb, key=lambda mo: difflib.SequenceMatcher(None, k3, mo[1]).ratio())
        ratio = difflib.SequenceMatcher(None, k3, best[1]).ratio()
        if prefix_ok(k3, best[1]):                     # 副題差 = 除外
            continue
        # ★種a が独立に MADB を支持(種3でなく)なら強い誤り
        a_supports_madb = a and difflib.SequenceMatcher(None, a, best[1]).ratio() >= 0.8
        if ratio < 0.55:
            suspect.append((round(ratio, 2), "★種a支持" if a_supports_madb else "", base_title(key), kana, best[0]))
    suspect.sort()
    print(f"④由来 base乖離 suspect: {len(suspect):,}")
    strong = [s for s in suspect if s[1]]
    print(f"  うち 種a が MADB を支持(=種3誤の強候補): {len(strong):,}")
    print(f"\n=== 強候補サンプル20(類似, 題, 種3kana, MADB読み)===")
    for ratio, mark, t, k, mb in strong[:20]:
        print(f"  {ratio} {t[:16]:<16} 種3[{k[:14]}] → MADB[{mb[:18]}]")
    with open(".cache/kana-deep-suspect.tsv", "w", encoding="utf-8") as f:
        f.write("ratio\ta_supports_madb\ttitle\ts3_kana\tmadb_kana\n")
        for row in suspect:
            f.write("\t".join(str(x) for x in row) + "\n")
    print(f"\nwrote .cache/kana-deep-suspect.tsv ({len(suspect)}, 強候補{len(strong)})")


if __name__ == "__main__":
    main()
