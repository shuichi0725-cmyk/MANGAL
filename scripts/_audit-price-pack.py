# -*- coding: utf-8 -*-
"""廉価パック/BOXセット構成員の検出 (= 猫と竜型 2026-08-26 型化。月次サニティ級)。

型: 「スペシャルプライスパック」等の廉価再録・全巻BOXの構成員レコードが MADB に
**正規巻と同じ題・巻番号**で入り、種2クラスタに合流して本番頁の主枠を奪う
(猫と竜 1-3巻 = 2026-07パックISBNが2018原版を追い出した 1.2.19実害)。

★署名は series/edition 層に存在しない: 題も巻番号も正規と同一で、パック標識は
  (1) schema:alternativeHeadline (スペシャルプライスパック等)
  (2) schema:description 内の「ISBN(set)」
  にしか無い → metadata101.json (種1 raw) を直接走査するしかない。

出力: docs/production-diagnostics/price-pack.tsv
運用: 月次蒸留のサニティ監査で実行し、**本番頁掲載(=主枠奪取疑い)の新規増加**を見る。
      是正は volume-exclude(パックISBN) or edition-overrides(BOX幽霊)。
      ※imprint "collection box" は promote の DROP_IMPRINT_LOWER_PATTERNS で恒久drop済み。

  python scripts/_audit-price-pack.py
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
META = os.path.join(ROOT, ".cache", "madb", "metadata101.json")
PAGE_IDX = os.path.join(ROOT, ".cache", "isbn-page-index.json")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "price-pack.tsv")

RE_ALT_PACK = re.compile(r"(スペシャルプライスパック|special\s*プライスパック|プライスパック|廉価版)", re.I)
RE_SET = re.compile(r"ISBN\(set\)")


def main() -> None:
    if not os.path.exists(META):
        print(f"ABORT: {META} が無い(種1 raw)")
        sys.exit(2)
    page_idx = {}
    if os.path.exists(PAGE_IDX):
        page_idx = json.load(io.open(PAGE_IDX, encoding="utf-8"))
    else:
        print(f"WARN: {PAGE_IDX} が無い(本番掲載照合はskip。`python scripts/_exists.py --build` で作れる)")

    rows = []
    buf: list[str] = []
    in_rec = False
    n_scan = 0
    with io.open(META, encoding="utf-8") as f:
        for ln in f:
            if ln.rstrip("\n") == "    {":
                in_rec, buf = True, [ln]
                continue
            if not in_rec:
                continue
            buf.append(ln)
            if ln.rstrip("\n") in ("    },", "    }"):
                in_rec = False
                n_scan += 1
                txt = "".join(buf)
                alt_hit = RE_ALT_PACK.search(txt) and '"schema:alternativeHeadline"' in txt
                set_hit = RE_SET.search(txt)
                if not (alt_hit or set_hit):
                    continue
                try:
                    rec = json.loads(txt.rstrip().rstrip(","))
                except Exception:
                    continue
                alt = rec.get("schema:alternativeHeadline")
                alt_s = alt if isinstance(alt, str) else json.dumps(alt, ensure_ascii=False)[:60] if alt else ""
                # alternativeHeadline 本体がパック語の時だけ alt 型 (本文descの誤ヒット除外)
                marker = []
                if alt_s and RE_ALT_PACK.search(alt_s):
                    marker.append("PACK語")
                if set_hit:
                    marker.append("ISBN(set)")
                if not marker:
                    continue
                isbn = rec.get("schema:isbn") or ""
                if not isinstance(isbn, str):
                    isbn = next((x for x in isbn if isinstance(x, str)), "") if isinstance(isbn, list) else ""
                isbn = re.sub(r"[^0-9X]", "", isbn.upper())
                label = rec.get("rdfs:label") or ""
                mid = str(rec.get("@id") or "").rsplit("/", 1)[-1]
                date = rec.get("schema:datePublished") or ""
                pub = rec.get("schema:publisher") or ""
                if not isinstance(pub, str):
                    pub = next((x for x in pub if isinstance(x, str)), "") if isinstance(pub, list) else ""
                onpage = page_idx.get(isbn) if isbn else None
                if isinstance(onpage, list):
                    onpage = ",".join(str(x) for x in onpage)
                rows.append((mid, label, isbn, "+".join(marker), str(date), pub, str(onpage or "")))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write("mid\tlabel\tisbn13\tmarker\tdate\tpublisher\t本番頁\n")
        for r in sorted(rows, key=lambda r: (r[6] == "", r[0])):
            f.write("\t".join(r) + "\n")

    n_on = sum(1 for r in rows if r[6])
    print(f"廉価パック/BOX構成員: {len(rows)} 件 (走査 {n_scan:,} レコード) / ★本番頁掲載 {n_on} 件")
    print(f"→ {os.path.relpath(OUT, ROOT)}")
    if n_on:
        print("★本番掲載 = パックISBNが主枠に居る疑い(猫と竜型)。1件ずつ裁定:")
        for r in rows:
            if r[6]:
                print(f"    {r[2]}  {r[1][:40]}  [{r[3]}] → /{r[6]}")
    sys.exit(1 if n_on else 0)


if __name__ == "__main__":
    main()
