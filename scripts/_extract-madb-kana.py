"""MADB raw から ISBN→ja-hrkt読み を全抽出(フリガナ正当性チェックの権威ソース)。

種3 title_kana は基本 MADB ja-hrkt 由来。 検証のため per-ISBN 読みを抽出してキャッシュ。
出力: .cache/madb-isbn-kana.tsv (isbn \t title \t kana)。 1 ISBN 複数読みは | 区切り。
"""
import json, csv, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
RAW = Path(".cache/madb/metadata101-clean.json")
OUT = Path(".cache/madb-isbn-kana.tsv")


def readings(nm):
    """schema:name → (title, [ja-hrkt読み...])"""
    title = ""
    kana = []
    if isinstance(nm, str):
        return nm, []
    if isinstance(nm, dict):
        if nm.get("@language") == "ja-hrkt":
            return "", [nm.get("@value")]
        return str(nm.get("@value", "")), []
    if isinstance(nm, list):
        for x in nm:
            if isinstance(x, str):
                if not title:
                    title = x
            elif isinstance(x, dict):
                if x.get("@language") == "ja-hrkt":
                    v = x.get("@value")
                    if v:
                        kana.append(v)
                elif not title:
                    title = str(x.get("@value", ""))
    return title, kana


def main():
    print("MADB raw 読込(~1-2分)...", flush=True)
    data = json.load(RAW.open(encoding="utf-8"))
    recs = data if isinstance(data, list) else data.get("@graph", [])
    n = 0
    nk = 0
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        for r in recs:
            isbn = r.get("schema:isbn")
            if not isbn:
                continue
            isbn = str(isbn).replace("-", "").strip()
            title, kana = readings(r.get("schema:name"))
            n += 1
            if kana:
                nk += 1
            w.writerow([isbn, title, "|".join(k for k in kana if k)])
    print(f"抽出: {n:,} ISBN, うち ja-hrkt読み有 {nk:,} ({nk*100//max(n,1)}%)")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
