"""種3 フリガナ(title_kana)正当性チェック = 種a romaji(公式読み)を真値に崩れ抽出。

slug は title_kana 起点なので、 その前にフリガナの読み崩れを潰す。
対象: 漢字含む題(=読みが非自明)で v14 マッチ有。
  種3 title_kana → ローマ字(pykakasi) vs 種a romaji を difflib 比較。
  系統差(長音/を/ハイフン)を正規化で吸収 → 低類似 = 真の読み崩れ候補。
※カタカナ主体は対象外(種a が英語綴り=別軸=slug の話)。
出力: .cache/kana-validity-suspect.tsv(類似度順)。 調査のみ。
"""
import pickle, csv, re, sys, difflib
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import pykakasi

PKL = Path(".cache/seed3-promote.pkl")
MATCH = Path(".cache/match-v14-all.tsv")
S = {"S180", "S150", "S130", "S100"}
_kks = pykakasi.kakasi()
KANJI = re.compile(r"[一-鿿]")


def hep(kana):
    return "".join(it["hepburn"] for it in _kks.convert(kana)).lower()


def norm(r):
    """系統差を吸収: lower / 非英数除去 / 長音圧縮 / wo→o / ヘボン揺れ。"""
    r = r.lower()
    r = re.sub(r"[^a-z0-9]", "", r)
    r = r.replace("wo", "o")
    r = re.sub(r"(.)\1+", r"\1", r)          # 連続同字(長音 oo/uu 等)を1つに
    r = r.replace("ou", "o").replace("ei", "e")
    r = re.sub(r"(.)\1+", r"\1", r)
    return r


def base_title(key):
    ns = [p[5:] for p in key.split("|") if p.startswith("name:")]
    return ns[-1] if ns else ""


def main():
    d = pickle.load(PKL.open("rb"))
    # series_key → 種a romaji
    a_romaji = {}
    with MATCH.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["verdict"] in S and r.get("a_romaji"):
                a_romaji[r["s3_key"]] = r["a_romaji"]

    suspect = []
    checked = 0
    for e in d.values():
        key = e["key"]
        title = base_title(key)
        kana = e.get("title_kana") or ""
        ar = a_romaji.get(key)
        if not (KANJI.search(title) and kana and ar):
            continue
        checked += 1
        s3r = norm(hep(kana))
        # 種a romaji は副題前まで(: 以降除外)
        ar0 = norm(re.split(r"[:：]", ar, 1)[0])
        if not s3r or not ar0:
            continue
        ratio = difflib.SequenceMatcher(None, s3r, ar0).ratio()
        if ratio < 0.6:
            suspect.append((round(ratio, 2), title, kana, ar, s3r, ar0))

    suspect.sort()
    print(f"漢字題×マッチ有 チェック: {checked:,}")
    print(f"★読み崩れ候補(類似<0.6): {len(suspect):,} ({len(suspect)*100//max(checked,1)}%)")
    print("\n=== 最も崩れてる 25件(類似, 題, 種3kana, 種a romaji)===")
    for ratio, t, k, ar, s3r, ar0 in suspect[:25]:
        print(f"  {ratio} {t[:18]:<18} 種3[{k[:16]}] vs 種a[{ar[:22]}]")
    with open(".cache/kana-validity-suspect.tsv", "w", encoding="utf-8") as f:
        f.write("ratio\ttitle\ts3_kana\ta_romaji\ts3_romaji_norm\ta_romaji_norm\n")
        for row in suspect:
            f.write("\t".join(str(x) for x in row) + "\n")
    print(f"\nwrote .cache/kana-validity-suspect.tsv ({len(suspect)})")


if __name__ == "__main__":
    main()
