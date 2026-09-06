# -*- coding: utf-8 -*-
"""【巻抜け充填 第2段-b】NDL収穫(_volgap-ndl-harvest2.py)を 充填ターゲットに照合する。

楽天ローカルで埋まらなかった巻(tier=NOHIT/DROPPED)だけが対象。
出力は _volgap-local-fill-v2.py と**同じ行の形**にして、同じ裁定器
(_volgap-adjudicate.py --in ... --source ndl)にそのまま渡せるようにする。

NDL固有の処理:
 - ISBN10 → ISBN13 変換(古典はISBN10で入っている)
 - 巻 = dcndl:volume(「2」「第4巻」)。空なら題の末尾から拾う(「0戦はやと 1」型)
 - 日付 = 「1978.08」「2012.8」「1964.04.01」「[1978]」「昭和58」等 → (Y,M,D)
 - 題 = 「題 : 副題」の副題を落としてから 巻トークンを剥がし、頁の題と完全一致を要求
 - ★分冊版/合本版/録音資料/小説 は除外語で落とす

出力: docs/production-diagnostics/volgap-ndl-fill.tsv + .cache/volgap-ndl-fill-rows.json
使用: python scripts/_volgap-ndl-match.py
"""
import os
import sys
import re
import json
import sqlite3
import unicodedata
from collections import defaultdict, Counter

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
import _rakuten_match_lib as R

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "manga.v2")
TARGETS = os.path.join(ROOT, "docs", "production-diagnostics", "volgap-fill-targets.tsv")
PREV = os.path.join(ROOT, ".cache", "volgap-local-fill-v2.json")
HARVEST = os.path.join(ROOT, ".cache", "volgap-ndl-fill.jsonl")

DROP_WORDS = ["ガイドブック", "ファンブック", "設定資料集", "公式読本", "アンソロジー", "画集",
              "原画集", "大全集", "大百科", "大事典", "解体新書", "傑作選", "傑作集", "総集編",
              "名作集", "名作選", "ノベライズ", "アニメコミック", "劇場版", "攻略", "完全ガイド",
              "コミックガイド", "小説", "分冊版", "合本版", "録音資料", "点字", "紙芝居",
              "ハンドブック", "名鑑"]

_PAREN = re.compile(r"[(（][^()（）]{1,20}[)）]")
_AUTHNORM = re.compile(r"[\s　,、/／・:：;；\.。\-−ー]")
_PD = re.compile(r"(\d{4})-?(\d{2})?-?(\d{2})?")
_VOLNUM = re.compile(r"^\s*(?:第)?\s*(\d{1,4})\s*(?:巻|冊)?\s*$")
_ERA = {"明治": 1867, "大正": 1911, "昭和": 1925, "平成": 1988, "令和": 2018}


def nisbn(s):
    return re.sub(r"[^0-9X]", "", str(s or "").upper())


def isbn13(s):
    """ISBN10 → ISBN13(978接頭)。13桁ならそのまま。それ以外は空。"""
    v = nisbn(s)
    if len(v) == 13 and v.startswith("97"):
        return v
    if len(v) == 10:
        core = "978" + v[:9]
        t = sum((1 if i % 2 == 0 else 3) * int(c) for i, c in enumerate(core))
        return core + str((10 - t % 10) % 10)
    return ""


def variants(title):
    t = R.nfkc(title or "")
    out = {R.norm(t)}
    s = _PAREN.sub("", t)
    if s.strip():
        out.add(R.norm(s))
    return {v for v in out if v}


def anorm(s):
    return _AUTHNORM.sub("", unicodedata.normalize("NFKC", str(s or ""))).lower()


def parse_prod_date(s):
    m = _PD.match(str(s or ""))
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0))


def parse_ndl_date(s):
    """「1978.08」「2012.8」「1964.04.01」「[1978]」「1978年」「昭和58」→ (Y,M,D)"""
    s = unicodedata.normalize("NFKC", str(s or "")).replace("．", ".").strip("[] ")
    for era, base in _ERA.items():
        m = re.match(r"^" + era + r"\s*(\d{1,2})", s)
        if m:
            return (base + int(m.group(1)), 0, 0)
    m = re.match(r"(\d{4})[.\-/年]?\s*(\d{1,2})?[.\-/月]?\s*(\d{1,2})?", s)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0))


def ndl_vol(rec):
    """dcndl:volume → int。空なら題の末尾トークンから。"""
    v = unicodedata.normalize("NFKC", str(rec.get("vol") or "")).strip()
    m = _VOLNUM.match(v)
    if m:
        return int(m.group(1))
    t = R.nfkc(rec.get("title") or "")
    t = t.split(" : ")[0]
    n, _ = R.parse_vol(t)
    return n


def ndl_base(rec):
    """NDL題から 副題と巻トークンを落とした基底題(norm済)。"""
    t = R.nfkc(rec.get("title") or "").split(" : ")[0]
    t = re.sub(r"[.\s]+$", "", t)
    _, residual = R.parse_vol(t)
    # 「0戦はやと. 1」型の末尾ピリオド番号
    residual = re.sub(r"[.。]\s*\d{1,3}$", "", residual)
    return R.norm(residual)


def main():
    lines = open(TARGETS, encoding="utf-8").read().splitlines()
    cols_in = lines[0].split("\t")
    tg = [dict(zip(cols_in, l.split("\t"))) for l in lines[1:] if l.strip()]
    prev = json.load(open(PREV, encoding="utf-8"))
    need = {(r["stem"], r["ei"], r["number"]) for r in prev if r["tier"] in ("NOHIT", "DROPPED")}
    tg = [r for r in tg if (r["stem"], r["ei"], r["number"]) in need]
    stems = sorted({r["stem"] for r in tg})
    print("NDL照合ターゲット {:,} 巻 / {} 頁".format(len(tg), len(stems)), flush=True)

    pages = {}
    for stem in stems:
        p = os.path.join(SRC, stem + ".yml")
        if not os.path.exists(p):
            continue
        d = yaml.safe_load(open(p, encoding="utf-8")) or {}
        vs = set()
        for t in [d.get("title")] + list((d.get("alternative_titles") or {}).values()):
            if isinstance(t, str):
                vs |= variants(t)
        auth = set()
        for key in ("authors", "original_authors"):
            for a in (d.get(key) or []):
                nm = anorm(a.get("name"))
                if nm and nm != "unknown":
                    auth.add(nm)
        pages[stem] = {"vars": vs, "authors": auth}

    prod_isbns = set(json.load(open(os.path.join(ROOT, ".cache", "isbn-page-index.json"),
                                    encoding="utf-8")).keys())
    con = sqlite3.connect(os.path.join(ROOT, ".cache", "db-v2.sqlite"))
    db_isbns = {nisbn(r[0]) for r in con.execute(
        "SELECT isbn13 FROM volumes WHERE isbn13 IS NOT NULL")}

    # --- NDL収穫 → (stem, vol) 索引 ---
    index = defaultdict(list)
    nrec = 0
    for line in open(HARVEST, encoding="utf-8"):
        try:
            h = json.loads(line)
        except Exception:
            continue
        stem = h.get("stem")
        pg = pages.get(stem)
        if not pg:
            continue
        for rec in h.get("records") or []:
            nrec += 1
            ib = isbn13(rec.get("isbn"))
            if not ib:
                continue
            title = str(rec.get("title") or "")
            if any(w in (title + " " + str(rec.get("series") or "")) for w in DROP_WORDS):
                continue
            if ndl_base(rec) not in pg["vars"]:
                continue
            v = ndl_vol(rec)
            if v is None:
                continue
            index[(stem, int(v))].append({
                "isbn": ib, "date": parse_ndl_date(rec.get("date")),
                "raw": title, "publisher": str(rec.get("pub") or ""),
                "author": "/".join(rec.get("creators") or []),
                "series": str(rec.get("series") or ""), "has_vol_token": True,
            })
    print("NDLレコード {:,} / 題+巻が一致した索引 {:,} キー".format(nrec, len(index)), flush=True)

    rows = []
    for r in tg:
        stem, num = r["stem"], int(r["number"])
        pg = pages.get(stem)
        if not pg:
            continue
        row = dict(r)
        row.update(isbn="", date="", rak_title="", rak_author="", rak_publisher="", cover="",
                   n_cands=0, g_pub="", g_date="", g_author="", g_isbn="", g_token="o")
        cands = index.get((stem, num), [])
        if not cands:
            row.update(tier="NOHIT", why="NDLにも該当巻なし")
            rows.append(row)
            continue
        exists = [c for c in cands if c["isbn"] in prod_isbns or c["isbn"] in db_isbns]
        fresh = [c for c in cands if c["isbn"] not in prod_isbns and c["isbn"] not in db_isbns]
        if not fresh:
            c = exists[0]
            row.update(tier="EXISTS", isbn=c["isbn"], date=R.date_str(c["date"], day=True),
                       rak_title=c["raw"], rak_author=c["author"], rak_publisher=c["publisher"],
                       n_cands=len(cands),
                       why="候補ISBNが既に本番/種2に在る=取込もれでない(under-merge)")
            rows.append(row)
            continue

        mp = r["main_prefix"]
        lo = parse_prod_date(r["prev_date"]) if r["prev_date"] else None
        hi = parse_prod_date(r["next_date"]) if r["next_date"] else None
        pi, ni = r.get("prev_isbn") or "", r.get("next_isbn") or ""

        def g_pub(c):
            return None if not mp else (c["isbn"][:7] == mp)

        def g_date(c):
            if not c["date"]:
                return None
            if lo and c["date"][:2] < lo[:2]:
                return False
            if hi and c["date"][:2] > hi[:2]:
                return False
            return True

        def g_auth(c):
            ca = anorm(c["author"])
            if not pg["authors"] or not ca:
                return None
            return any(a and (a in ca or ca in a) for a in pg["authors"])

        def g_isbn(c):
            v = c["isbn"]
            if pi and ni:
                return pi < v < ni
            if pi:
                return v > pi
            if ni:
                return v < ni
            return None

        def score(c):
            def s(x):
                return 2 if x is True else (1 if x is None else 0)
            return (s(g_pub(c)), s(g_isbn(c)), s(g_date(c)), s(g_auth(c)),
                    -(c["date"] or (9999, 0, 0))[0])

        c = max(fresh, key=score)
        P, I, D, A = g_pub(c), g_isbn(c), g_date(c), g_auth(c)

        def mk(x):
            return "o" if x is True else ("x" if x is False else "?")

        if P is False or I is False:
            tier = "REJECT_EDITION"
            why = "版元prefix不一致" if P is False else "ISBN連番の外(別レーベル/別年代版の可能性)"
        elif P is True and I is True and (D is True or A is True):
            tier, why = "ACCEPT", "版元o+ISBN連番o+" + ("日付o" if D is True else "著者o")
        elif P is True and D is True and A is True:
            tier, why = "ACCEPT", "版元o+日付o+著者o(ISBN連番は判定不能)"
        elif I is True and A is True and P is None:
            tier, why = "ACCEPT", "ISBN連番o+著者o(版元prefixは頁側にISBN無しで判定不能)"
        else:
            tier, why = "REVIEW", "証拠不足"
        row.update(tier=tier, isbn=c["isbn"], date=R.date_str(c["date"], day=True),
                   rak_title=c["raw"], rak_author=c["author"], rak_publisher=c["publisher"],
                   n_cands=len(fresh), g_pub=mk(P), g_isbn=mk(I), g_date=mk(D), g_author=mk(A),
                   why=why + ("(既存候補{}件も有)".format(len(exists)) if exists else ""))
        rows.append(row)

    ORDER = ["ACCEPT", "REVIEW", "REJECT_EDITION", "EXISTS", "NOHIT"]
    rows.sort(key=lambda r: (ORDER.index(r["tier"]), r["stem"], int(r["number"])))
    cols = ["tier", "stem", "title", "route", "ei", "etype", "label", "imprint", "number", "kind",
            "isbn", "date", "rak_title", "rak_author", "rak_publisher",
            "g_pub", "g_isbn", "g_date", "g_author", "g_token",
            "main_prefix", "prev_num", "prev_isbn", "prev_date", "next_num", "next_isbn", "next_date",
            "publisher", "n_cands", "why", "cover"]
    outp = os.path.join(ROOT, "docs", "production-diagnostics", "volgap-ndl-fill.tsv")
    with open(outp, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(r.get(c, "")).replace("\t", " ") for c in cols) + "\n")
    json.dump(rows, open(os.path.join(ROOT, ".cache", "volgap-ndl-fill-rows.json"), "w",
                         encoding="utf-8"), ensure_ascii=False)
    cnt = Counter(r["tier"] for r in rows)
    print("=== NDL 裁定前(巻) ===")
    for t in ORDER:
        print("  {:16} {:5}   頁 {}".format(t, cnt.get(t, 0),
                                            len({r["stem"] for r in rows if r["tier"] == t})))
    print("→ " + outp)


if __name__ == "__main__":
    main()
