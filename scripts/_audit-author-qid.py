#!/usr/bin/env python3
"""頁の著者QID(wikidata_qid = series.qid)× 頁の著者欄の突合と、不一致の裏取り (2026-10-22 新設)

背景: 作品頁下部「著者: Wikidata Qxx」リンクと JSON-LD は頁の wikidata_qid を使うが、これは種2 series.qid
(MADB 由来の著者QID)で、頁の著者欄(AniList 補正後)と一致する保証がない。

判定(外部へは1リクエストも出さない = 手元の作家表・AniList dump・種2 だけ):
  MATCH_AUTHOR   著者欄に QID の人物が居る
  MATCH_ORIGINAL 原作者欄に居る(正当)
  不一致は裏取りして3つに分ける:
  MISSING_CREDIT QID の人物が AniList staff か 種2 の著者(頁の巻ISBNから辿ったシリーズ)に居る
                 = 作品に関わる人物なのに頁の著者欄/原作者欄に載っていない(頁データの欠け)。役割を併記
  WRONG_PERSON   どちらにも居ない = QID が無関係な別人(リンクを出すと誤り)
  NO_EVIDENCE    AniList も 種2 シリーズも引けず判定材料が無い

出力: docs/production-diagnostics/author-qid-audit.tsv(不一致分のみ・証拠つき) + stdout 集計
使い方: python scripts/_audit-author-qid.py
"""
import collections, csv, glob, gzip, json, os, re, sqlite3, sys, unicodedata

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, ".cache", "db-v2.sqlite")
DUMP = os.path.join(ROOT, ".cache", "anilist-manga-dump-v3.jsonl.gz")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "author-qid-audit.tsv")
# 作品頁が import する非表示一覧(app/manga/[slug]/page.tsx)。 不一致の頁(slug)= 著者: Wikidata リンクを出さない
HIDE = os.path.join(ROOT, "data", "author-qid-hide.json")

VAR = str.maketrans({"齋": "斎", "齊": "斉", "邊": "辺", "邉": "辺", "髙": "高", "﨑": "崎", "嶋": "島", "濱": "浜",
                     "澤": "沢", "國": "国", "廣": "広", "櫻": "桜", "眞": "真", "惠": "恵", "德": "徳", "藏": "蔵"})


def norm(s):
    s = unicodedata.normalize("NFKC", s or "").casefold().translate(VAR)
    s = "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)  # ひらがな→カタカナ
    return re.sub(r"[\s・=.\-ー〜~!！?？☆★♪]", "", s)


def main():
    con = sqlite3.connect(DB)
    qnames = collections.defaultdict(set)   # qid -> 正規化名の集合(本名+別名)
    qdisp = {}
    mk_id = {}
    for mid, q, n, alt in con.execute("select id, qid, name, alt_names from mangaka"):
        qdisp[q] = n
        mk_id[q] = mid
        for a in [n] + re.split(r"[|,;/、]", alt or ""):
            if a and a.strip():
                qnames[q].add(norm(a))

    pages = []
    for f in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
        d = yaml.safe_load(open(f, encoding="utf-8")) or {}
        q = d.get("wikidata_qid")
        if not q:
            continue
        au = [a.get("name", "") for a in (d.get("authors") or []) if isinstance(a, dict)]
        oa = [a.get("name", "") for a in (d.get("original_authors") or []) if isinstance(a, dict)]
        names = qnames.get(q, set())
        if any(norm(x) in names for x in au):
            continue
        if any(norm(x) in names for x in oa):
            continue
        isbns = []
        for e in d.get("editions") or []:
            for vs in [e.get("volumes") or []] + [v.get("volumes") or [] for v in (e.get("versions") or [])]:
                isbns += [str(v["isbn13"]) for v in vs if v.get("isbn13")]
        pages.append({"slug": d.get("slug"), "stem": os.path.splitext(os.path.basename(f))[0], "title": d.get("title", ""), "qid": q, "au": au, "oa": oa,
                      "anilist": d.get("anilist_id"), "isbns": isbns[:30]})
    print(f"不一致(著者欄にも原作者欄にも居ない): {len(pages)}頁")

    want = {p["anilist"] for p in pages if p["anilist"]}
    staff = {}
    with gzip.open(DUMP, "rt", encoding="utf-8") as fh:
        for ln in fh:
            try:
                m = json.loads(ln)
            except Exception:
                continue
            if m.get("id") in want:
                staff[m["id"]] = [(e.get("role", ""), (e.get("node") or {}).get("name") or {})
                                  for e in ((m.get("staff") or {}).get("edges") or [])]

    res = collections.Counter()
    rows = []
    for p in pages:
        q = p["qid"]
        names = qnames.get(q, set())
        ev = []
        for role, nm in staff.get(p["anilist"], []):
            if norm(nm.get("native")) in names or norm(nm.get("full")) in names:
                ev.append(f"AniList:{role}")
        # 種2: 頁の巻ISBN → シリーズ → 著者(役割)
        sids = set()
        for ib in p["isbns"]:
            for (sid,) in con.execute("select e.series_id from volumes v join editions e on v.edition_id=e.id"
                                      " where v.isbn13=?", (ib,)):
                sids.add(sid)
        if q in mk_id and sids:
            for (role,) in con.execute(f"select role from series_authors where mangaka_id=? and series_id in"
                                       f" ({','.join('?' * len(sids))})", (mk_id[q], *sids)):
                ev.append(f"種2:{role}")
        if ev:
            v = "MISSING_CREDIT"
        elif not staff.get(p["anilist"]) and not sids:
            v = "NO_EVIDENCE"
        else:
            v = "WRONG_PERSON"
        res[v] += 1
        rows.append((v, p["slug"], p["stem"], p["title"], q, qdisp.get(q, ""), "|".join(p["au"]), "|".join(p["oa"]),
                     ";".join(sorted(set(ev)))))
    print(dict(res))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as fo:
        w = csv.writer(fo, delimiter="\t")
        w.writerow(["verdict", "slug", "stem", "title", "qid", "qid_name", "authors", "original_authors", "evidence"])
        w.writerows(sorted(rows))
    with open(HIDE, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(sorted({r[1] for r in rows}), fh, ensure_ascii=False, indent=0)
        fh.write("\n")
    print(f"→ {os.path.relpath(OUT, ROOT)} / {os.path.relpath(HIDE, ROOT)}({len(rows)}頁)")


if __name__ == "__main__":
    main()
