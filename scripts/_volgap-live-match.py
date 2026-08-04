# -*- coding: utf-8 -*-
"""【楽天live収穫 → 巻抜けfill提案】_volgap-rakuten-local-fill.py と同じ4層ゲート+著者照合をlive itemに適用。

ゲート:
  G0 題完全一致  : 巻トークンを剥がした残差題 == 頁題(norm)
  G1 既存ISBN除外: 本番索引 or 種2に在るISBNは候補にしない(under-merge領域)
  G2 版一致      : 候補ISBNの出版者記号(978-4-RRR)が その版の主prefixと一致
  G3 日付整合    : 直前巻 <= 候補 <= 直後巻
  G4 drop題      : ガイド/画集/アンソロ等を含む題は捨てる
  A  著者照合    : live itemのauthorと頁著者(空白除去)の包含判定

出力: docs/production-diagnostics/volgap-live.tsv / .cache/volgap-live-match.json
使用: python scripts/_volgap-live-match.py
"""
import os, sys, re, json, sqlite3, unicodedata, yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
import _rakuten_match_lib as R

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "manga.v2")
HARV = os.path.join(ROOT, ".cache", "volgap-live-rakuten.jsonl")

DROP_WORDS = ["ガイドブック", "ファンブック", "設定資料集", "公式読本", "アンソロジー", "画集", "原画集",
              "大全集", "大百科", "大事典", "解体新書", "傑作選", "傑作集", "総集編", "名作集", "名作選",
              "ノベライズ", "小説", "アニメコミック", "劇場版", "攻略", "完全ガイド", "コミックガイド"]


def norm_isbn(s):
    return re.sub(r"[^0-9X]", "", str(s or "").upper())


def akey(s):
    return re.sub(r"[\s　・,、/]", "", unicodedata.normalize("NFKC", str(s or "")))


prod = set(json.load(open(os.path.join(ROOT, ".cache", "isbn-page-index.json"), encoding="utf-8")).keys())
con = sqlite3.connect(os.path.join(ROOT, ".cache", "db-v2.sqlite"))
db = {norm_isbn(r[0]) for r in con.execute("SELECT isbn13 FROM volumes WHERE isbn13 IS NOT NULL")}
print(f"既存ISBN: 本番 {len(prod)} / 種2 {len(db)}", flush=True)

rows = []
n_page = 0
for line in open(HARV, encoding="utf-8"):
    if not line.strip():
        continue
    h = json.loads(line)
    stem = h["stem"]
    p = os.path.join(SRC, stem + ".yml")
    if not os.path.exists(p):
        continue
    d = yaml.safe_load(open(p, encoding="utf-8")) or {}
    n_page += 1
    base = R.norm(R.nfkc(d.get("title", "")))
    pauth = [akey(a.get("name") if isinstance(a, dict) else str(a)) for a in (d.get("authors") or [])]
    pauth = [x for x in pauth if x]

    # live item を (vol -> [rec]) に整理(題完全一致=G0)
    byvol = {}
    for it in h.get("items") or []:
        raw = R.clean_title(it.get("title", ""))
        v, res = R.parse_vol(raw)
        if R.norm(res) != base:
            continue
        if any(w in raw for w in DROP_WORDS):
            continue
        isbn = norm_isbn(it.get("isbn", ""))
        if len(isbn) != 13:
            continue
        byvol.setdefault(1 if v is None else v, []).append({
            "isbn": isbn, "date": R.parse_salesdate(it.get("salesDate", "")),
            "raw": raw, "publisher": it.get("publisherName", ""), "author": it.get("author", ""),
            "series": it.get("seriesName", ""),
        })

    for e in (d.get("editions") or []):
        vols = [v for v in (e.get("volumes") or []) if v.get("number")]
        if len(vols) < 2:
            continue
        have = {}
        for v in vols:
            n = int(v["number"])
            rd = str(v.get("release_date") or "")
            m = re.match(r"(\d{4})-?(\d{2})?-?(\d{2})?", rd)
            dt = (int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0)) if m else None
            have.setdefault(n, (dt, norm_isbn(v.get("isbn13"))))
        ns = sorted(have)
        prefixes = {}
        for _dt, ib in have.values():
            if ib:
                prefixes[ib[:7]] = prefixes.get(ib[:7], 0) + 1
        main_prefix = max(prefixes, key=prefixes.get) if prefixes else None
        for n in [x for x in range(ns[0], ns[-1] + 1) if x not in have]:
            cands = byvol.get(n) or []
            cands = [c for c in cands if c["isbn"] not in prod and c["isbn"] not in db]  # G1
            if not cands:
                continue
            same_pub = [c for c in cands if main_prefix and c["isbn"][:7] == main_prefix]  # G2
            pool = same_pub or cands
            rec = min(pool, key=lambda c: c["date"] or (9999, 0, 0))
            prevs = [have[x][0] for x in ns if x < n and have[x][0]]
            nexts = [have[x][0] for x in ns if x > n and have[x][0]]
            lo, hi = (max(prevs) if prevs else None), (min(nexts) if nexts else None)
            dt = rec["date"]
            date_ok = bool(dt) and not (lo and dt < lo) and not (hi and dt > hi)  # G3
            ra = akey(rec["author"])
            aok = "OK" if (ra and any(x in ra for x in pauth)) else ("NO_AUTHOR" if not ra else "MISMATCH")
            tier = "STRICT" if (same_pub and date_ok) else ("PUB_ONLY" if same_pub else ("DATE_ONLY" if date_ok else "WEAK"))
            rows.append({"tier": tier, "author_ok": aok, "stem": stem, "title": d.get("title", ""),
                         "etype": e.get("type") or "standard", "number": n, "isbn": rec["isbn"],
                         "date": R.date_str(rec["date"]), "publisher": rec["publisher"],
                         "rakuten_title": rec["raw"], "rakuten_author": rec["author"],
                         "page_authors": " / ".join(pauth), "series_name": rec["series"],
                         "main_prefix": main_prefix or "", "cand_prefix": rec["isbn"][:7], "n_cands": len(cands)})

order = {"STRICT": 0, "PUB_ONLY": 1, "DATE_ONLY": 2, "WEAK": 3}
rows.sort(key=lambda r: (order[r["tier"]], r["stem"], r["number"]))
json.dump(rows, open(os.path.join(ROOT, ".cache", "volgap-live-match.json"), "w", encoding="utf-8"), ensure_ascii=False)
outp = os.path.join(ROOT, "docs", "production-diagnostics", "volgap-live.tsv")
cols = ("tier", "author_ok", "stem", "title", "etype", "number", "isbn", "date", "publisher",
        "rakuten_title", "rakuten_author", "page_authors", "series_name", "main_prefix", "cand_prefix", "n_cands")
with open(outp, "w", encoding="utf-8", newline="") as f:
    f.write("\t".join(cols) + "\n")
    for r in rows:
        f.write("\t".join(str(r.get(c, "")) for c in cols) + "\n")
from collections import Counter
c = Counter((r["tier"], r["author_ok"]) for r in rows)
print(f"収穫頁 {n_page} / 提案 {len(rows)} 巻 / {len({r['stem'] for r in rows})} 頁")
for k in sorted(c, key=lambda x: (order[x[0]], x[1])):
    print(f"  {k[0]:9} {k[1]:9} {c[k]}")
print(f"→ {outp}")
