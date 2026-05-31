"""Wikipedia サンプルテスト = フリガナ suspect を日本語Wikipediaの冒頭よみがなで裁定。

歩留まり実測用。 ④ suspect から漢字主体の短い題を取り、 ja.wikipedia の
冒頭「タイトル（よみがな）は…」を抽出 → 種3 / MADB どちらが正しいか判定。
出力: stdout(各件 + 歩留まり集計)。
"""
import csv, re, sys, json, time, urllib.request, urllib.parse, unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
SUSPECT = Path(".cache/kana-deep-suspect.tsv")
API = "https://ja.wikipedia.org/w/api.php"
UA = {"User-Agent": "MANGAL-research-bot/0.1 (mailto:shuichi0725@gmail.com)"}
KANJI = re.compile(r"[一-鿿]")
LATIN = re.compile(r"[A-Za-z]")
KANA = re.compile(r"[ぁ-ゟ゠-ヿ]")
SMALL = str.maketrans("ァィゥェォッャュョ", "アイウエオツヤユヨ")


def kata_norm(s):
    if not s: return ""
    s = unicodedata.normalize("NFKC", s)
    s = "".join(chr(ord(c)+0x60) if "ぁ" <= c <= "ゖ" else c for c in s)
    s = "".join(ch for ch in s if unicodedata.category(ch)[0] != "P" and ch not in "ー―‐~〜　 ")
    return s.translate(SMALL)


def wiki_reading(title):
    """ja.wikipedia 冒頭から よみがな(katakana norm)を抽出。 無ければ None。"""
    q = urllib.parse.urlencode({"action": "query", "format": "json", "prop": "extracts",
                                "exintro": "1", "explaintext": "1", "redirects": "1", "titles": title})
    try:
        with urllib.request.urlopen(urllib.request.Request(f"{API}?{q}", headers=UA), timeout=20) as r:
            data = json.loads(r.read())
    except Exception as e:
        return None, f"err:{e}"
    pages = data.get("query", {}).get("pages", {})
    for _, p in pages.items():
        ex = p.get("extract")
        if not ex:
            return None, "記事無"
        head = ex[:200]
        # 「…（ よみがな ）…」最初の括弧内のかな
        for m in re.finditer(r"[（(]([^（）()]+)[）)]", head):
            inner = m.group(1)
            kana_only = "".join(c for c in inner if KANA.search(c) or c in "・ー、 ")
            if KANA.search(inner) and len(kana_only) >= len(inner) * 0.6:
                return kata_norm(inner), inner[:24]
        return None, "よみがな無(記事有)"
    return None, "記事無"


def main():
    rows = list(csv.DictReader(SUSPECT.open(encoding="utf-8"), delimiter="\t"))
    # 漢字主体・短め・latin無 を優先(読み誤りが意味を持つ)
    cand = [r for r in rows if KANJI.search(r["title"]) and not LATIN.search(r["title"])
            and 2 <= len(r["title"]) <= 12]
    sample = cand[:25]
    print(f"④ suspect {len(rows)} → 漢字主体短題 {len(cand)} → テスト {len(sample)} 件\n")
    s3_err = madb_err = inconcl = noart = 0
    for r in sample:
        title = r["title"]; s3 = kata_norm(r["s3_kana"]); madb = kata_norm(r["madb_kana"])
        wk, raw = wiki_reading(title)
        time.sleep(1.0)
        if wk is None:
            noart += 1; verdict = f"判定不可({raw})"
        elif wk == s3 and wk != madb:
            madb_err += 1; verdict = "★種3正(MADB誤)"
        elif wk == madb and wk != s3:
            s3_err += 1; verdict = "★種3誤(要訂正)"
        elif wk == s3 == madb:
            verdict = "全一致"
        else:
            inconcl += 1; verdict = "別読み(要目視)"
        print(f"  {title[:12]:<12} 種3[{r['s3_kana'][:10]}] MADB[{r['madb_kana'][:10]}] wiki[{raw[:12]}] → {verdict}")
    n = len(sample)
    print(f"\n=== 歩留まり ({n}件) ===")
    print(f"  ★種3誤(Wikipediaで訂正可): {s3_err}")
    print(f"  ★MADB誤(種3正と確認): {madb_err}")
    print(f"  別読み(要目視): {inconcl}")
    print(f"  Wikipedia判定不可(記事無等): {noart}")


if __name__ == "__main__":
    main()
