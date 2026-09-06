# -*- coding: utf-8 -*-
"""【1巻が無い頁】楽天live+NDLの収穫(_volgap-lead-live-probe.py)を 充填ターゲットに照合する。

出力は _volgap-local-fill-v2.py と**同じ行の形**にして、同じ裁定器
(_volgap-adjudicate.py --in ... --source live)にそのまま渡せるようにする。

★異体字ゆれを吸収する(2026-09-07): 頁題「アドニスの憂欝な日々」に対し NDL は
  「アドニスの憂鬱な日々」。 NFKC では 欝/鬱 は統一されないので、書誌照合で標準的に
  使われる異体字の対だけを畳む(意味が変わらないものに限る)。

ゲートは他の充填器と同じ5層(G1既存ISBN/G2版元prefix/G3発売日/G4著者/G5 ISBN連番)。
出力: docs/production-diagnostics/volgap-lead-live-fill.tsv + .cache/volgap-lead-live-fill.json
使用: python scripts/_volgap-lead-live-match.py [--targets TSV[,TSV]]
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
HARVEST = os.path.join(ROOT, ".cache", "volgap-lead-live.jsonl")
TARGETS = (sys.argv[sys.argv.index("--targets") + 1] if "--targets" in sys.argv
           else ",".join([os.path.join(ROOT, "docs", "production-diagnostics", "volgap-fill-targets.tsv"),
                          os.path.join(ROOT, "docs", "production-diagnostics", "edition-lead-targets.tsv")]))

DROP_WORDS = ["ガイドブック", "ファンブック", "設定資料集", "公式読本", "公式ファン", "アンソロジー",
              "画集", "原画集", "大全集", "大百科", "大事典", "解体新書", "傑作選", "傑作集",
              "総集編", "名作集", "名作選", "ノベライズ", "アニメコミック", "劇場版", "攻略",
              "完全ガイド", "コミックガイド", "小説", "分冊版", "合本版", "録音資料", "点字",
              "紙芝居", "ハンドブック", "名鑑", "イラストブック", "カレンダー", "DVD", "Blu-ray"]

# ★書誌照合で畳んでよい異体字(意味が変わらないもののみ)
VARIANT = str.maketrans({
    "欝": "鬱", "曾": "曽", "藝": "芸", "澤": "沢", "邊": "辺", "邉": "辺", "齋": "斎",
    "齊": "斉", "髙": "高", "﨑": "崎", "濵": "浜", "濱": "浜", "眞": "真", "德": "徳",
    "瀨": "瀬", "來": "来", "國": "国", "會": "会", "體": "体", "戀": "恋", "醫": "医",
})
_PAREN = re.compile(r"[(（][^()（）]{1,20}[)）]")
_AUTHNORM = re.compile(r"[\s　,、/／・:：;；\.。\-−ー]")
_PD = re.compile(r"(\d{4})-?(\d{2})?-?(\d{2})?")
_VOLNUM = re.compile(r"^\s*(?:第)?\s*(\d{1,4})\s*(?:巻|冊)?\s*$")
_ERA = {"明治": 1867, "大正": 1911, "昭和": 1925, "平成": 1988, "令和": 2018}


def nisbn(s):
    return re.sub(r"[^0-9X]", "", str(s or "").upper())


def isbn13(s):
    v = nisbn(s)
    if len(v) == 13 and v.startswith("97"):
        return v
    if len(v) == 10:
        core = "978" + v[:9]
        t = sum((1 if i % 2 == 0 else 3) * int(c) for i, c in enumerate(core))
        return core + str((10 - t % 10) % 10)
    return ""


def norm(s):
    return R.norm(str(s or "").translate(VARIANT))


def variants(title):
    t = R.nfkc(title or "")
    out = {norm(t)}
    s = _PAREN.sub("", t)
    if s.strip():
        out.add(norm(s))
    return {v for v in out if v}


def anorm(s):
    return _AUTHNORM.sub("", unicodedata.normalize("NFKC", str(s or ""))).lower()


def parse_prod_date(s):
    m = _PD.match(str(s or ""))
    return (int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0)) if m else None


def parse_ndl_date(s):
    s = unicodedata.normalize("NFKC", str(s or "")).replace("．", ".").strip("[] ")
    for era, base in _ERA.items():
        m = re.match(r"^" + era + r"\s*(\d{1,2})", s)
        if m:
            return (base + int(m.group(1)), 0, 0)
    m = re.match(r"(\d{4})[.\-/年]?\s*(\d{1,2})?[.\-/月]?\s*(\d{1,2})?", s)
    return (int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0)) if m else None


def ndl_vol(rec):
    v = unicodedata.normalize("NFKC", str(rec.get("vol") or "")).strip()
    m = _VOLNUM.match(v)
    if m:
        return int(m.group(1))
    m = re.match(r"^\s*vol\.?\s*(\d{1,4})\s*$", v, re.I)
    if m:
        return int(m.group(1))
    t = R.nfkc(rec.get("title") or "").split(" : ")[0]
    n, _ = R.parse_vol(t)
    return n


def ndl_base(rec):
    t = R.nfkc(rec.get("title") or "").split(" : ")[0].split(" = ")[0]
    t = re.sub(r"[.\s]+$", "", t)
    _, residual = R.parse_vol(t)
    residual = re.sub(r"[.。]\s*\d{1,3}$", "", residual)
    return norm(residual)


def main():
    tg = []
    for path in TARGETS.split(","):
        if not os.path.exists(path):
            continue
        lines = open(path, encoding="utf-8").read().splitlines()
        cols = lines[0].split("\t")
        tg += [dict(zip(cols, l.split("\t"))) for l in lines[1:] if l.strip()]
    tg = [r for r in tg if r.get("kind") in ("LEAD", "ELEAD")]
    seen = set()
    uniq = []
    for r in tg:
        k = (r["stem"], r["ei"], r["number"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    tg = uniq
    stems = sorted({r["stem"] for r in tg})
    print("先頭欠けターゲット {:,} 巻 / {} 頁".format(len(tg), len(stems)), flush=True)

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

    index = defaultdict(list)
    nrak = nndl = 0
    for line in open(HARVEST, encoding="utf-8"):
        try:
            h = json.loads(line)
        except Exception:
            continue
        stem = h.get("stem")
        pg = pages.get(stem)
        if not pg:
            continue
        for it in h.get("rakuten") or []:
            nrak += 1
            raw = R.clean_title(it.get("title", ""))
            sub = R.clean_title(it.get("subTitle", ""))
            if any(w in (raw + " " + sub) for w in DROP_WORDS):
                continue
            vol, residual = R.parse_vol(raw)
            if norm(residual) not in pg["vars"]:
                continue
            ib = isbn13(it.get("isbn"))
            if not ib:
                continue
            cov = (it.get("largeImageUrl") or "").split("?")[0]
            index[(stem, 1 if vol is None else vol)].append({
                "isbn": ib, "date": R.parse_salesdate(it.get("salesDate", "")), "raw": raw,
                "publisher": it.get("publisherName") or "", "author": R.clean_title(it.get("author", "")),
                "cover": "" if (not cov or "noimage" in cov) else cov,
                "has_vol_token": vol is not None, "src": "rakuten-live"})
        for rec in h.get("ndl") or []:
            nndl += 1
            t = str(rec.get("title") or "")
            if any(w in (t + " " + str(rec.get("series") or "")) for w in DROP_WORDS):
                continue
            if ndl_base(rec) not in pg["vars"]:
                continue
            v = ndl_vol(rec)
            ib = isbn13(rec.get("isbn"))
            if v is None or not ib:
                continue
            index[(stem, int(v))].append({
                "isbn": ib, "date": parse_ndl_date(rec.get("date")), "raw": t,
                "publisher": str(rec.get("pub") or ""), "author": "/".join(rec.get("creators") or []),
                "cover": "", "has_vol_token": True, "src": "ndl"})
    print("収穫 楽天{:,} / NDL{:,} → 題+巻が一致した索引 {:,} キー".format(nrak, nndl, len(index)), flush=True)

    rows = []
    for r in tg:
        stem, num = r["stem"], int(r["number"])
        pg = pages.get(stem)
        if not pg:
            continue
        row = dict(r)
        row.update(isbn="", date="", rak_title="", rak_author="", rak_publisher="", cover="",
                   n_cands=0, g_pub="", g_date="", g_author="", g_isbn="", g_token="", src="")
        cands = index.get((stem, num), [])
        if not cands:
            row.update(tier="NOHIT", why="楽天live/NDLにも該当巻なし")
            rows.append(row)
            continue
        exists = [c for c in cands if c["isbn"] in prod_isbns or c["isbn"] in db_isbns]
        fresh = [c for c in cands if c["isbn"] not in prod_isbns and c["isbn"] not in db_isbns]
        mp = r["main_prefix"]
        lo = parse_prod_date(r["prev_date"]) if r.get("prev_date") else None
        hi = parse_prod_date(r["next_date"]) if r.get("next_date") else None
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
                    1 if c["src"] == "rakuten-live" else 0)

        best_fresh = max(fresh, key=score) if fresh else None
        best_exists = max(exists, key=score) if exists else None
        if best_exists is not None and (best_fresh is None or score(best_exists) > score(best_fresh)):
            c = best_exists
            row.update(tier="EXISTS", isbn=c["isbn"], date=R.date_str(c["date"], day=True),
                       rak_title=c["raw"], rak_author=c["author"], rak_publisher=c["publisher"],
                       cover=c["cover"], n_cands=len(cands), src=c["src"],
                       why="候補ISBNが既に本番/種2に在る=取込もれでない(under-merge)")
            rows.append(row)
            continue
        c = best_fresh
        P, I, D, A = g_pub(c), g_isbn(c), g_date(c), g_auth(c)
        tok = c["has_vol_token"]

        def mk(x):
            return "o" if x is True else ("x" if x is False else "?")

        if P is False or I is False:
            tier = "REJECT_EDITION"
            why = "版元prefix不一致" if P is False else "ISBN連番の外(別レーベル/別年代版の可能性)"
        elif num == 1 and not tok:
            tier, why = "REVIEW_TOKEN", "題に巻番号が無い=単巻本か1巻か判別不能"
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
                   cover=c["cover"], n_cands=len(fresh), src=c["src"],
                   g_pub=mk(P), g_isbn=mk(I), g_date=mk(D), g_author=mk(A),
                   g_token=("o" if tok else "x"),
                   why=why + ("(既存候補{}件も有)".format(len(exists)) if exists else ""))
        rows.append(row)

    ORDER = ["ACCEPT", "REVIEW", "REVIEW_TOKEN", "REJECT_EDITION", "EXISTS", "NOHIT"]
    rows.sort(key=lambda r: (ORDER.index(r["tier"]), r["stem"], int(r["number"])))
    cols = ["tier", "stem", "title", "route", "ei", "etype", "label", "imprint", "number", "kind",
            "isbn", "date", "src", "rak_title", "rak_author", "rak_publisher",
            "g_pub", "g_isbn", "g_date", "g_author", "g_token",
            "main_prefix", "prev_num", "prev_isbn", "prev_date", "next_num", "next_isbn",
            "next_date", "publisher", "n_cands", "why", "cover"]
    outp = os.path.join(ROOT, "docs", "production-diagnostics", "volgap-lead-live-fill.tsv")
    with open(outp, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(r.get(c, "")).replace("\t", " ") for c in cols) + "\n")
    json.dump(rows, open(os.path.join(ROOT, ".cache", "volgap-lead-live-fill.json"), "w",
                         encoding="utf-8"), ensure_ascii=False)
    cnt = Counter(r["tier"] for r in rows)
    print("=== 裁定前(巻) ===")
    for t in ORDER:
        print("  {:16} {:5}   頁 {}".format(t, cnt.get(t, 0),
                                            len({r["stem"] for r in rows if r["tier"] == t})))
    print("  ACCEPT の情報源:", dict(Counter(r["src"] for r in rows if r["tier"] == "ACCEPT")))
    print("→ " + outp)


if __name__ == "__main__":
    main()
