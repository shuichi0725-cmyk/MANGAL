"""STEP 3: 取込もれ候補 (= 単一巻欠け) を分類 + NDL で ISBN 裏取り → 種4 ドラフト生成。

入力: .cache/seed4-candidates.csv (= _audit-volume-gaps が出す単一欠けリスト)
分類 (DB自己照合、 無料):
  - missing 巻 が db に同正規化title で 存在する → "unmerged" (= 未統合fragment、 merge改善案件)
  - db に無い → "absent" (= 真の取込もれ候補 = 種4 行き)
NDL照合 (absent のみ、 throttle):
  - NDL Search OpenSearch API で title 照会 → dcndl:volume==N かつ ISBN付き item を取得
  - 見つかれば 種4 ドラフト entry を出力 (= needs-review、 自動適用しない)

出力:
  .cache/seed4-classified.csv     = 全候補 + 分類
  .cache/seed4-drafts.yml         = NDL 確認済 種4 ドラフト (= レビュー後 手で volumes-supplement.yml へ)

使い方:
  python scripts/_seed4-candidates.py                 # 分類のみ (NDL なし)
  python scripts/_seed4-candidates.py --ndl --limit 30  # absent 上位30件を NDL 照合
"""
from __future__ import annotations
import csv
import re
import sqlite3
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
CAND = ROOT / ".cache" / "seed4-candidates.csv"
OUT_CLS = ROOT / ".cache" / "seed4-classified.csv"
OUT_DRAFT = ROOT / ".cache" / "seed4-drafts.yml"
UA = "MANGAL-research/0.1 (mailto:shuichi0725@gmail.com)"

DO_NDL = "--ndl" in sys.argv
LIMIT = 30
for i, a in enumerate(sys.argv):
    if a == "--limit" and i + 1 < len(sys.argv):
        LIMIT = int(sys.argv[i + 1])


def clean(s: str) -> str:
    """句読点/空白/横棒を除去 + lower (= audit の _clean 相当)。"""
    if not s:
        return ""
    out = []
    for ch in s:
        cat = unicodedata.category(ch)
        if cat[0] in ("P", "Z") or ch in "ー―~〜":
            continue
        out.append(ch.lower())
    return "".join(out)


def build_volume_index(con) -> dict:
    """(正規化title, vol番号) → [sid,...] の索引を 1回で構築 (= per候補SQL回避)。"""
    from collections import defaultdict
    idx: dict[tuple, list] = defaultdict(list)
    for sid, title, num in con.execute(
        """SELECT s.id, s.title, v.number
           FROM volumes v JOIN editions e ON e.id=v.edition_id JOIN series s ON s.id=e.series_id
           WHERE v.number IS NOT NULL"""
    ):
        n = re.match(r"^\s*(\d+)\s*$", str(num))
        if n:
            idx[(clean(title), int(n.group(1)))].append(sid)
    return idx


def ndl_lookup(title: str, vol: int) -> dict | None:
    """NDL OpenSearch で title 照会 → dcndl:volume==vol かつ ISBN付き の book を返す。
    title は NDL の base-title (= ' : ' サブ前) と **正規化 完全一致** を要求
    (= 'Q.E.D.' が 'Q.E.D.iff' を誤マッチするのを防ぐ)。 長編対応で cnt=200。"""
    q = urllib.parse.urlencode({"title": title, "cnt": "200"})
    url = "https://ndlsearch.ndl.go.jp/api/opensearch?" + q
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        data = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}"}
    items = re.findall(r"<item>.*?</item>", data, re.S)
    ntitle = clean(title)
    for it in items:
        vm = re.search(r"<dcndl:volume>(.*?)</dcndl:volume>", it)
        if not vm:
            continue
        vnum = re.match(r"\s*(\d+)", vm.group(1))
        if not vnum or int(vnum.group(1)) != vol:
            continue
        isbns = re.findall(r'<dc:identifier[^>]*ISBN[^>]*>(.*?)</dc:identifier>', it)
        if not isbns:
            continue
        t = re.search(r"<dc:title>(.*?)</dc:title>", it)
        bt = t.group(1) if t else ""
        # title 妥当性: NDL title の base (= ' : ' サブ前) が 候補 title と 正規化完全一致
        base = bt.split(" : ", 1)[0]
        if clean(base) != ntitle:
            continue
        iss = re.search(r"<dcterms:issued[^>]*>(.*?)</dcterms:issued>", it)
        pub = re.search(r"<dc:publisher>(.*?)</dc:publisher>", it)
        ext = re.search(r"<dc:extent>(.*?)</dc:extent>", it)
        return {
            "ndl_title": bt,
            "isbn13": isbns[0].replace("-", ""),
            "issued": iss.group(1) if iss else "",
            "publisher": pub.group(1) if pub else "",
            "extent": ext.group(1) if ext else "",
        }
    return None


def main():
    con = sqlite3.connect(DB)
    rows = list(csv.DictReader(CAND.open(encoding="utf-8")))
    print(f"候補 (単一欠け): {len(rows):,}", file=sys.stderr)
    print("  巻索引 構築中 ...", file=sys.stderr)
    vol_idx = build_volume_index(con)

    classified = []
    n_absent = n_unmerged = 0
    for r in rows:
        title = r["series_title"]
        try:
            miss = int(r["missing"])
        except ValueError:
            continue
        nt = clean(title)
        hits = vol_idx.get((nt, miss), [])
        kind = "unmerged" if hits else "absent"
        if hits:
            n_unmerged += 1
        else:
            n_absent += 1
        classified.append({
            "kind": kind,
            "series_title": title,
            "missing": miss,
            "max_vol": r["max_vol"],
            "edition_type": r["edition_type"],
            "db_hit_sids": ";".join(str(h) for h in hits),
            "cluster_key": r["cluster_key"],
        })

    classified.sort(key=lambda x: (x["kind"] != "absent", -int(x["max_vol"])))
    with OUT_CLS.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["kind", "series_title", "missing", "max_vol",
                                          "edition_type", "db_hit_sids", "cluster_key"])
        w.writeheader()
        w.writerows(classified)
    print(f"=== 分類 ===", file=sys.stderr)
    print(f"  absent (真の取込もれ候補 = 種4): {n_absent:,}", file=sys.stderr)
    print(f"  unmerged (未統合fragment = merge改善): {n_unmerged:,}", file=sys.stderr)
    print(f"  → {OUT_CLS}", file=sys.stderr)

    if not DO_NDL:
        print("\n(NDL 照合は --ndl で実行)", file=sys.stderr)
        return

    absent = [c for c in classified if c["kind"] == "absent"][:LIMIT]
    print(f"\n=== NDL 照合 (absent 上位 {len(absent)}) ===", file=sys.stderr)
    drafts = []
    for i, c in enumerate(absent):
        res = ndl_lookup(c["series_title"], c["missing"])
        time.sleep(1.5)  # throttle
        if not res:
            print(f"  [{i+1}] {c['series_title']} {c['missing']}巻 → NDL 該当なし", file=sys.stderr)
            continue
        if "_error" in res:
            print(f"  [{i+1}] {c['series_title']} → {res['_error']}", file=sys.stderr)
            continue
        pages = re.search(r"(\d+)\s*p", res.get("extent", ""))
        drafts.append({
            "series_title": c["series_title"],
            "number": c["missing"],
            "isbn13": res["isbn13"],
            "issued": res["issued"],
            "publisher": res["publisher"],
            "pages": int(pages.group(1)) if pages else None,
            "ndl_title": res["ndl_title"],
        })
        print(f"  [{i+1}] ✓ {c['series_title']} {c['missing']}巻 → ISBN {res['isbn13']} ({res['issued']})", file=sys.stderr)

    import yaml
    OUT_DRAFT.write_text(
        "# NDL 確認済 種4 ドラフト (= 要レビュー、 自動適用しない)\n"
        "# series_keys は手で確認して volumes-supplement.yml へ移すこと\n"
        + yaml.dump(drafts, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"\n  種4 ドラフト {len(drafts)} 件 → {OUT_DRAFT}", file=sys.stderr)


if __name__ == "__main__":
    main()
