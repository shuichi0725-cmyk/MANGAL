"""フリガナ正当性 3ソース突合 = 種3 title_kana vs MADB ja-hrkt vs 種a romaji。

種3 kana は基本 MADB由来 + AI fill。 検証:
  - 種3 kana ∈ MADB読み      → MADB一致(正当、 当て字でもMADBにあればOK)
  - 種3 kana ∉ MADB(MADB有)  → 種3≠MADB(AI差替/種3誤/MADB誤の疑い)
  - MADB読み無               → AI fill(MADBに読み無) → 種a で検証
さらに 種a romaji と突合し suspect を絞る。
出力: .cache/kana-3source.tsv。 調査のみ。
"""
import pickle, csv, sqlite3, re, sys, unicodedata
from collections import defaultdict, Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
PKL = Path(".cache/seed3-promote.pkl")
MADB_KANA = Path(".cache/madb-isbn-kana.tsv")
MATCH = Path(".cache/match-v14-all.tsv")
DB = Path(".cache/db-v2.sqlite")
S = {"S180", "S150", "S130", "S100"}

# --- 種a romaji → カタカナ(v9 流用・簡易) ---
CONSONANTS = set("kgsztcdnhfbpmyrwvj")
SYL_3 = {"kya":"キャ","kyu":"キュ","kyo":"キョ","sha":"シャ","shu":"シュ","sho":"ショ","shi":"シ",
 "cha":"チャ","chu":"チュ","cho":"チョ","chi":"チ","tsu":"ツ","nya":"ニャ","nyu":"ニュ","nyo":"ニョ",
 "hya":"ヒャ","hyu":"ヒュ","hyo":"ヒョ","gya":"ギャ","gyu":"ギュ","gyo":"ギョ","ja":"ジャ","ju":"ジュ","jo":"ジョ",
 "rya":"リャ","ryu":"リュ","ryo":"リョ","bya":"ビャ","byu":"ビュ","byo":"ビョ","pya":"ピャ","pyu":"ピュ","pyo":"ピョ",
 "mya":"ミャ","myu":"ミュ","myo":"ミョ"}
SYL_2 = {"ka":"カ","ki":"キ","ku":"ク","ke":"ケ","ko":"コ","ga":"ガ","gi":"ギ","gu":"グ","ge":"ゲ","go":"ゴ",
 "sa":"サ","su":"ス","se":"セ","so":"ソ","za":"ザ","ji":"ジ","zu":"ズ","ze":"ゼ","zo":"ゾ","ta":"タ","te":"テ","to":"ト",
 "da":"ダ","de":"デ","do":"ド","na":"ナ","ni":"ニ","nu":"ヌ","ne":"ネ","no":"ノ","ha":"ハ","hi":"ヒ","fu":"フ","he":"ヘ","ho":"ホ",
 "ba":"バ","bi":"ビ","bu":"ブ","be":"ベ","bo":"ボ","pa":"パ","pi":"ピ","pu":"プ","pe":"ペ","po":"ポ","ma":"マ","mi":"ミ","mu":"ム","me":"メ","mo":"モ",
 "ya":"ヤ","yu":"ユ","yo":"ヨ","ra":"ラ","ri":"リ","ru":"ル","re":"レ","ro":"ロ","wa":"ワ","wo":"ヲ"}
SYL_1 = {"a":"ア","i":"イ","u":"ウ","e":"エ","o":"オ","n":"ン"}


def romaji_to_kata(s):
    if not s: return ""
    s = s.lower(); out = []; i = 0
    while i < len(s):
        c = s[i]
        if not c.isalpha(): i += 1; continue
        if i+1 < len(s) and c == s[i+1] and c in CONSONANTS: out.append("ッ"); i += 1; continue
        if s[i:i+3] in SYL_3: out.append(SYL_3[s[i:i+3]]); i += 3; continue
        if s[i:i+2] in SYL_2: out.append(SYL_2[s[i:i+2]]); i += 2; continue
        if c in SYL_1: out.append(SYL_1[c]); i += 1; continue
        i += 1
    return "".join(out)


SMALL = str.maketrans("ァィゥェォッャュョ", "アイウエオツヤユヨ")  # 小書き→大(揺れ吸収)


def kata_norm(s):
    if not s: return ""
    s = unicodedata.normalize("NFKC", s)
    s = "".join(chr(ord(c)+0x60) if "ぁ" <= c <= "ゖ" else c for c in s)  # hira→kata
    # 句読点(Unicode P)+ 長音/波線/空白 を全除去(、。「」・〜 等も)
    s = "".join(ch for ch in s if unicodedata.category(ch)[0] != "P"
                and ch not in "ー―‐~〜　 ")
    s = s.translate(SMALL)               # 小書きカナ揺れ吸収
    return s


def base_title(key):
    ns = [p[5:] for p in key.split("|") if p.startswith("name:")]
    return ns[-1] if ns else ""


def main():
    d = pickle.load(PKL.open("rb"))
    # ISBN → MADB読み(set)
    isbn_kana = {}
    with MADB_KANA.open(encoding="utf-8") as f:
        for r in csv.reader(f, delimiter="\t"):
            if len(r) >= 3 and r[2]:
                isbn_kana[r[0]] = [k for k in r[2].split("|") if k]
    # series_key → MADB読み(set, 正規化)
    con = sqlite3.connect(DB); con.text_factory = lambda b: b.decode("utf-8", "replace")
    sk_madb = defaultdict(set)
    for sk, isbn in con.execute("""
        SELECT s.series_key, v.isbn13 FROM series s
        JOIN editions e ON e.series_id=s.id JOIN volumes v ON v.edition_id=e.id
        WHERE v.isbn13 IS NOT NULL"""):
        for k in isbn_kana.get(str(isbn).replace("-", "").strip(), []):
            sk_madb[sk].add(kata_norm(k))
    con.close()
    # series_key → 種a romaji(kata正規化)
    sk_a = {}
    with MATCH.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["verdict"] in S and r.get("a_romaji"):
                ar = re.split(r"[:：]\s", r["a_romaji"], 1)[0]
                sk_a[r["s3_key"]] = kata_norm(romaji_to_kata(ar))

    cat = Counter()
    suspect = []
    for e in d.values():
        key = e["key"]
        kana = e.get("title_kana") or ""
        if not kana: continue
        k3 = kata_norm(kana)
        madb = sk_madb.get(key, set())
        a = sk_a.get(key)
        if madb:
            if k3 in madb:
                cat["①MADB一致(正当)"] += 1
            else:
                # 種a で裁定
                if a and (k3 == a):
                    cat["②種3≠MADB だが 種3=種a (MADB誤 or 当て字)"] += 1
                    suspect.append(("MADB誤?", base_title(key), kana, "|".join(list(madb)[:2]), a or ""))
                elif a and any(m == a for m in madb):
                    cat["③MADBに種a一致読み有・種3は別(種3誤?)"] += 1
                    suspect.append(("種3誤?", base_title(key), kana, "|".join(list(madb)[:2]), a or ""))
                else:
                    cat["④種3≠MADB・種a裁定不可"] += 1
        else:
            if a:
                if k3 == a:
                    cat["⑤AI fill・種a一致(正当)"] += 1
                else:
                    cat["⑥AI fill・種a不一致(要確認)"] += 1
                    suspect.append(("AIfill≠種a", base_title(key), kana, "(MADB無)", a or ""))
            else:
                cat["⑦MADB無・種aマッチ無(裁定不可)"] += 1

    tot = sum(cat.values())
    print(f"=== フリガナ正当性 3ソース突合 (種3 kana有 {tot:,}) ===")
    for k, v in sorted(cat.items()):
        print(f"  {k}: {v:,} ({v*100//tot}%)")
    print(f"\n=== suspect(裁定可) サンプル20 (区分, 題, 種3kana, MADB読み, 種a) ===")
    for typ, t, k, m, a in suspect[:20]:
        print(f"  [{typ}] {t[:16]:<16} 種3[{k[:14]}] MADB[{m[:14]}] 種a[{a[:14]}]")
    with open(".cache/kana-3source.tsv", "w", encoding="utf-8") as f:
        f.write("type\ttitle\ts3_kana\tmadb_kana\ta_kata\n")
        for row in suspect:
            f.write("\t".join(str(x) for x in row) + "\n")
    print(f"\nwrote .cache/kana-3source.tsv ({len(suspect)} suspect)")


if __name__ == "__main__":
    main()
