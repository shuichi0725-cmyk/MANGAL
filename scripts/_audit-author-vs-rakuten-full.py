"""★著者誤紐付け監査(全本番): 頁の著者が楽天の著者と**1人も一致しない**頁を検出。

背景(2026-07-25): 取りこぼし頁化で作った155頁のうち **18頁(12%)** で種2の著者が
全くの別人だった(例 恋ひ恋ひて: series_key は `name:ito|…` なのに series_authors は
「ハルチカ」= 種2内で自己矛盾)。 種2の著者クラスタリングは既知の弱点
([[series_fragmentation_rootcause]])なので、**本番全体にも同型が居る**はず。

★live照会は不要: 楽天の全件キャッシュ(rakuten-isbn.jsonl + -delta.jsonl)が
本番ISBNの99%(253,179/255,282)を被覆している([[rakuten_cover_data_asset]])。 1パス走査で足りる。

判定:
  頁の authors/original_authors と 楽天 item.author を正規化して比較。
  **共通が1人も無い**頁だけ flag。 ★表記ゆれ(かな/漢字・姓名空白)は正規化+部分一致で吸収し、
  それでも重ならないものだけ出す(= ももちゃん先生型の偽陽性を避ける)。
出力: docs/production-diagnostics/author-vs-rakuten.tsv (read-only)

usage: python scripts/_audit-author-vs-rakuten-full.py [--limit N]
"""
import glob
import json
import re
import sys
import unicodedata
from pathlib import Path

import difflib

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "manga.v2"
CACHES = [ROOT / ".cache" / "rakuten-isbn.jsonl", ROOT / ".cache" / "rakuten-isbn-delta.jsonl"]
OUT = ROOT / "docs" / "production-diagnostics" / "author-vs-rakuten.tsv"
ISBN = re.compile(r"97[89]\d{10}")
try:
    from yaml import CSafeLoader as L
except ImportError:
    L = yaml.SafeLoader


sys.path.insert(0, str(Path(__file__).resolve().parent))
from _kana_romaji import kana2romaji   # noqa: E402  ★ラテン↔カナ照合用(単一ソース)

# ★偽陽性型1: 楽天側が「総称」= 個人名でない(当方の個別著者と重ならなくて当然)
GENERIC = re.compile(r"アンソロジー|オムニバス|編集部|製作委員会|委員会|チーム|"
                     r"^ほか$|^他$|^作者不明$|^各種$|^-$|公式|監修|"
                     r"^[^\s]*(社|書店|書房|出版|新聞|文庫|コミックス)$")
ROLE_PAREN = re.compile(r"[（(][^）)]*[）)]")     # 「国友やすゆき(原案)」等の役割注記


def _skel(s):
    """子音骨格(ラテン↔カナの音写判定用)。"""
    return re.sub(r"[aeiou\W_]", "", (s or "").lower())


def _translit_match(ours, theirs):
    """★偽陽性型2: 同一人物のラテン表記 vs カナ表記(アナ・C・サンチェス ↔ SanchezAnaC)。
    カナ側をローマ字化し、子音骨格の類似度>=0.6 なら同一とみなす。"""
    for o in ours:
        for t in theirs:
            a, b = o, t
            if re.search(r"[ァ-ヶー]", a) and re.search(r"[A-Za-z]", b):
                a = kana2romaji(a)
            elif re.search(r"[A-Za-z]", a) and re.search(r"[ァ-ヶー]", b):
                b = kana2romaji(b)
            else:
                continue
            sa, sb = _skel(a), _skel(b)
            if sa and sb and difflib.SequenceMatcher(None, sa, sb).ratio() >= 0.6:
                return True
    return False


def norm(s):
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = re.sub(r"[\s　・,、/／。\.\-_｜|]", "", s)
    return s.lower()


def kana_only(s):
    """カタカナ/ひらがなを片仮名に寄せた骨格(かな表記 vs 漢字表記の照合は不可なので別軸)。"""
    s = norm(s)
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ん" else c for c in s)


def main():
    limit = 0
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    print("[1/3] 本番頁の著者とISBNを読む ...", flush=True)
    pages = {}
    want = set()
    for n, p in enumerate(glob.glob(str(SRC / "*.yml")), 1):
        if limit and n > limit:
            break
        if n % 20000 == 0:
            print(f"    ...{n:,}", flush=True)
        try:
            d = yaml.load(open(p, encoding="utf-8"), Loader=L)
        except Exception:
            continue
        if not d:
            continue
        aus = [a.get("name") for a in (d.get("authors") or [])] + \
              [a.get("name") for a in (d.get("original_authors") or [])]
        aus = [a for a in aus if a and a != "(unknown)"]
        if not aus:
            continue
        ibs = [v.get("isbn13") for e in (d.get("editions") or []) for v in (e.get("volumes") or [])
               if v.get("isbn13")]
        if not ibs:
            continue
        pages[d.get("slug")] = {"title": d.get("title"), "authors": aus, "isbns": ibs[:6],
                                "year": d.get("year_started")}
        want.update(ibs[:6])
    print(f"  頁 {len(pages):,} / 照合ISBN {len(want):,}", flush=True)

    print("[2/3] 楽天キャッシュを1パス走査 ...", flush=True)
    rk = {}
    for c in CACHES:
        if not c.exists():
            continue
        n = 0
        for ln in c.open(encoding="utf-8"):
            n += 1
            if n % 400000 == 0:
                print(f"    ...{c.name} {n:,}", flush=True)
            try:
                d = json.loads(ln)
            except Exception:
                continue
            ib = str(d.get("isbn") or "")
            if ib in want and ib not in rk:
                it = d.get("item") or {}
                a = (it.get("author") or "").strip()
                if a:
                    rk[ib] = a
    print(f"  楽天著者が取れたISBN {len(rk):,}", flush=True)

    print("[3/3] 突合 ...", flush=True)
    rows = []
    for slug, p in pages.items():
        rak = []
        for ib in p["isbns"]:
            if ib in rk:
                rak = [ROLE_PAREN.sub("", x).strip() for x in re.split(r"[/／]", rk[ib]) if x.strip()]
                break
        rak = [x for x in rak if x and not GENERIC.search(x)]
        if not rak:
            continue        # ★楽天が総称のみ = 判定不能(当方が正しいことが多い)
        ours = {norm(a) for a in p["authors"]}
        ours_k = {kana_only(a) for a in p["authors"]}
        theirs = {norm(a) for a in rak}
        theirs_k = {kana_only(a) for a in rak}
        if ours & theirs or ours_k & theirs_k:
            continue
        # ★部分一致も許容(「緒川千世」vs「緒川 千世」等は norm で吸収済。 姓のみ表記の揺れ用)
        if any(o and t and (o in t or t in o) for o in ours for t in theirs):
            continue
        if _translit_match(p["authors"], rak):
            continue        # ★ラテン↔カナの同一人物
        rows.append((slug, p["title"], " / ".join(p["authors"]), " / ".join(rak),
                     str(p["year"] or ""), p["isbns"][0]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        f.write("slug\ttitle\tours\trakuten\tyear\tisbn\n")
        for r in sorted(rows, key=lambda r: r[4], reverse=True):
            f.write("\t".join(r) + "\n")
    print(f"\n=== 著者不一致(楽天と1人も重ならない) ===")
    print(f"  ★{len(rows):,} 頁 / 照合できた {sum(1 for p in pages.values() if any(i in rk for i in p['isbns'])):,} 頁")
    print(f"  → {OUT}")
    for r in sorted(rows, key=lambda r: r[4], reverse=True)[:15]:
        print(f"   {r[1][:22]:24s} 当方={r[2][:20]:22s} 楽天={r[3][:24]:26s} {r[4]}")


if __name__ == "__main__":
    main()
