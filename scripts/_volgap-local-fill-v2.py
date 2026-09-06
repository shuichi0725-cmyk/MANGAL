# -*- coding: utf-8 -*-
"""【巻抜け充填 v2】充填ターゲット(_volgap-gap-targets.py)を ローカル楽天種だけで埋める提案を作る。

旧 _volgap-rakuten-local-fill.py からの改良:
 - ★先頭欠け(LEAD = 頁の最小巻>1)も対象(旧版は版内 min..max の穴しか見ず 751巻を取りこぼしていた)
 - ★ルビ括弧/別題の**題variant**で引く(「皆様の玩具(オモチャ)です」型が完全一致で0件になる罠)
 - ★経路(seed4/canon:*/overrides)を持ち回る(canonical頁は種4が promote で潰される)
 - ★既に本番/種2に在るISBNは EXISTS として分離(= under-merge。 埋めると二重化する)

ゲート(5層):
 G1 既存ISBN     : 本番索引/種2に在る = 取込もれでない
 G2 版元prefix   : その版の主ISBN登録者記号と一致(別社の版を弾く)
 G3 発売日       : 前後巻の日付の間に入る
 G4 著者         : 楽天itemの author と頁の著者が重なる
 G5 ISBN連番     : ★決定打。 前巻ISBN < 候補ISBN < 次巻ISBN(先頭欠けは < 次巻、末尾は > 前巻)。
                   同じ社の**別レーベル**(プレミア=文庫版ISBN)や**別年代版**(復讐の兇獣=1982年版、
                   ハード&ルーズ=原版のISBN)を、版元prefixだけでは弾けないので これで落とす。

出力: docs/production-diagnostics/volgap-local-fill-v2.tsv + .cache/volgap-local-fill-v2.json
使用: python scripts/_volgap-local-fill-v2.py [--targets TSV]
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
TARGETS = (sys.argv[sys.argv.index("--targets") + 1] if "--targets" in sys.argv
           else os.path.join(ROOT, "docs", "production-diagnostics", "volgap-fill-targets.tsv"))
TAG = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "volgap-local-fill-v2"

DROP_WORDS = ["ガイドブック", "ファンブック", "設定資料集", "公式読本", "公式ファン", "アンソロジー",
              "画集", "原画集", "大全集", "大百科", "大事典", "解体新書", "傑作選", "傑作集",
              "総集編", "名作集", "名作選", "ノベライズ", "アニメコミック", "劇場版", "攻略",
              "完全ガイド", "コミックガイド", "小説版", "ドラマCD", "カレンダー", "DVD",
              "Blu-ray", "フィギュア", "タペストリー", "分冊版", "合本版"]

_PAREN = re.compile(r"[(（][^()（）]{1,20}[)）]")
_AUTHNORM = re.compile(r"[\s　,、/／・:：;；\.。\-−ー]")
_PD = re.compile(r"(\d{4})-?(\d{2})?-?(\d{2})?")


def nisbn(s):
    return re.sub(r"[^0-9X]", "", str(s or "").upper())


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


def main():
    lines = open(TARGETS, encoding="utf-8").read().splitlines()
    cols_in = lines[0].split("\t")
    tg = [dict(zip(cols_in, l.split("\t"))) for l in lines[1:] if l.strip()]
    stems = sorted({r["stem"] for r in tg})
    print("ターゲット {:,} 巻 / {} 頁".format(len(tg), len(stems)), flush=True)

    pages, allvars = {}, set()
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
        allvars |= vs
    print("題variant {:,} 種".format(len(allvars)), flush=True)

    prod_isbns = set(json.load(open(os.path.join(ROOT, ".cache", "isbn-page-index.json"),
                                    encoding="utf-8")).keys())
    con = sqlite3.connect(os.path.join(ROOT, ".cache", "db-v2.sqlite"))
    db_isbns = {nisbn(r[0]) for r in con.execute(
        "SELECT isbn13 FROM volumes WHERE isbn13 IS NOT NULL")}
    print("既存ISBN: 本番索引 {:,} / 種2 {:,}".format(len(prod_isbns), len(db_isbns)), flush=True)

    index = defaultdict(list)
    n = 0
    for isbn, it in R.iter_items((R.DELTA, R.OLD)):
        n += 1
        if n % 200000 == 0:
            print("  ...{:,} item 走査".format(n), flush=True)
        raw = R.clean_title(it.get("title", ""))
        vol, residual = R.parse_vol(raw)
        base = R.norm(residual)
        if base not in allvars:
            continue
        cov = (it.get("largeImageUrl") or "").split("?")[0]
        index[(base, 1 if vol is None else vol)].append({
            "isbn": isbn,
            "date": R.parse_salesdate(it.get("salesDate", "")),
            "raw": raw,
            "sub": R.clean_title(it.get("subTitle", "")),
            "publisher": it.get("publisherName", ""),
            "author": R.clean_title(it.get("author", "")),
            "cover": "" if "noimage" in cov else cov,
            "has_vol_token": vol is not None,
        })
    print("走査 {:,} item / 該当索引 {:,} キー".format(n, len(index)), flush=True)

    rows = []
    for r in tg:
        stem, num = r["stem"], int(r["number"])
        pg = pages.get(stem)
        if not pg:
            continue
        row = dict(r)
        row.update(isbn="", date="", rak_title="", rak_author="", rak_publisher="", cover="",
                   n_cands=0, g_pub="", g_date="", g_author="", g_isbn="", g_token="")
        cands = []
        for v in pg["vars"]:
            cands += index.get((v, num), [])
        if not cands:
            row.update(tier="NOHIT", why="楽天ローカルに該当巻なし")
            rows.append(row)
            continue
        cands = [c for c in cands if not any(w in (c["raw"] + c["sub"]) for w in DROP_WORDS)]
        if not cands:
            row.update(tier="DROPPED", why="候補が非漫画/関連書/分冊版の語を含む")
            rows.append(row)
            continue
        exists = [c for c in cands if c["isbn"] in prod_isbns or c["isbn"] in db_isbns]
        fresh = [c for c in cands if c["isbn"] not in prod_isbns and c["isbn"] not in db_isbns]

        mp = r["main_prefix"]
        lo = parse_prod_date(r["prev_date"]) if r["prev_date"] else None
        hi = parse_prod_date(r["next_date"]) if r["next_date"] else None
        pi = r.get("prev_isbn") or ""
        ni = r.get("next_isbn") or ""

        def g_pub(c):
            return None if not mp else (c["isbn"][:7] == mp)

        def g_date(c):
            if not c["date"]:
                return None
            if lo and c["date"] < lo:
                return False
            if hi and c["date"] > hi:
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

        # ★候補は **fresh と exists を合わせた全体から同じスコアで**選ぶ(2026-09-07 是正)。
        #   旧実装は ①exists は「最古の日付」で選ぶ ②fresh が1件でも在れば fresh だけ見る、
        #   の2つの穴があり、正解を取り逃がしていた(鉄腕アトム 版[7]=講談社コミックス(1993)の
        #   v1=9784063133585 / v2=9784063133608 は種2に在るのに、朝日ソノラマ1975・秋田1995の
        #   別版が fresh として選ばれ「版元prefix不一致」で棄却されていた)。
        best_fresh = max(fresh, key=score) if fresh else None
        best_exists = max(exists, key=score) if exists else None
        if best_exists is not None and (best_fresh is None or score(best_exists) > score(best_fresh)):
            c = best_exists
            row.update(tier="EXISTS", isbn=c["isbn"], date=R.date_str(c["date"], day=True),
                       rak_title=c["raw"], rak_author=c["author"], rak_publisher=c["publisher"],
                       cover=c["cover"], n_cands=len(cands),
                       why="候補ISBNが既に本番/種2に在る=取込もれでない(under-merge)")
            rows.append(row)
            continue

        c = best_fresh
        P, I, D, A = g_pub(c), g_isbn(c), g_date(c), g_auth(c)
        tok = c["has_vol_token"]

        def mk(x):
            return "o" if x is True else ("x" if x is False else "?")

        # --- 裁定 ---
        if P is False or I is False:
            tier = "REJECT_EDITION"
            why = "版元prefix不一致" if P is False else "ISBN連番の外(別レーベル/別年代版の可能性)"
        elif num == 1 and not tok:
            tier = "REVIEW_TOKEN"
            why = "楽天題に巻番号が無い=単巻本か1巻か判別不能"
        elif P is True and I is True and (D is True or A is True):
            tier = "ACCEPT"
            why = "版元o+ISBN連番o+" + ("日付o" if D is True else "著者o")
        elif P is True and D is True and A is True:
            tier = "ACCEPT"
            why = "版元o+日付o+著者o(ISBN連番は判定不能)"
        elif I is True and A is True and P is None:
            tier = "ACCEPT"
            why = "ISBN連番o+著者o(版元prefixは頁側にISBN無しで判定不能)"
        else:
            tier = "REVIEW"
            why = "証拠不足"
        row.update(tier=tier, isbn=c["isbn"], date=R.date_str(c["date"], day=True),
                   rak_title=c["raw"], rak_author=c["author"], rak_publisher=c["publisher"],
                   cover=c["cover"], n_cands=len(fresh),
                   g_pub=mk(P), g_isbn=mk(I), g_date=mk(D), g_author=mk(A),
                   g_token=("o" if tok else "x"),
                   why=why + ("(既存候補{}件も有)".format(len(exists)) if exists else ""))
        rows.append(row)

    ORDER = ["ACCEPT", "REVIEW", "REVIEW_TOKEN", "REJECT_EDITION", "EXISTS", "DROPPED", "NOHIT"]
    rows.sort(key=lambda r: (ORDER.index(r["tier"]), r["stem"], int(r["number"])))
    cols = ["tier", "stem", "title", "route", "ei", "etype", "label", "imprint", "number", "kind",
            "isbn", "date", "rak_title", "rak_author", "rak_publisher",
            "g_pub", "g_isbn", "g_date", "g_author", "g_token",
            "main_prefix", "prev_num", "prev_isbn", "prev_date", "next_num", "next_isbn", "next_date",
            "publisher", "n_cands", "why", "cover"]
    outp = os.path.join(ROOT, "docs", "production-diagnostics", TAG + ".tsv")
    with open(outp, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(r.get(c, "")).replace("\t", " ") for c in cols) + "\n")
    json.dump(rows, open(os.path.join(ROOT, ".cache", TAG + ".json"), "w",
                         encoding="utf-8"), ensure_ascii=False)
    cnt = Counter(r["tier"] for r in rows)
    print("=== 裁定(巻) ===")
    for t in ORDER:
        pgs = len({r["stem"] for r in rows if r["tier"] == t})
        print("  {:16} {:5}   頁 {}".format(t, cnt.get(t, 0), pgs))
    print("合計 {} 巻".format(len(rows)))
    print("ACCEPT の経路:", dict(Counter(r["route"] for r in rows if r["tier"] == "ACCEPT")))
    print("→ " + outp)


if __name__ == "__main__":
    main()
