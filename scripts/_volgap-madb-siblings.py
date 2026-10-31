# -*- coding: utf-8 -*-
"""【巻抜け・MADB兄弟探し 2026-11-01】巻抜けターゲットの欠番巻を MADB 元記録の「兄弟」(同じ著者・同じ叢書/版元で、題が似ていて巻番号が欠番に当たる記録)から探す。
楽天/NDL の題名検索は頁の題で引くので、MADB が巻ごとに題を揺らした巻(9/23 の A割れ・B取込もれ型)を取りこぼす。
出力: 候補ごとに、その ISBN が本番のどこに出ているか(isbn-page-index)・種2に居るか。"""
import csv, json, os, re, sqlite3, sys, unicodedata
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import yaml


def nk(s):
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    return re.sub(r"[\s\u3000・･,，、。.!！?？'\"“”‘’()（）\[\]［］「」『』〈〉《》〔〕~〜～\-‐―ー:：;；/／&＆★☆♡♥]", "", s)


def to13(raw):
    s = re.sub(r"[^0-9X]", "", str(raw or "").upper())
    if len(s) == 23:
        s = s[10:] if s[10:13] in ("978", "979") else s[:13]
    if len(s) == 10:
        core = "978" + s[:9]
        t = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(core))
        s = core + str((10 - t % 10) % 10)
    return s if len(s) == 13 else ""


def first_str(x):
    if isinstance(x, list):
        for y in x:
            if isinstance(y, str):
                return y
        return ""
    return x if isinstance(x, str) else ""


ROLE = re.compile(r"(原作|漫画|作画|著|作|画|絵|原案|脚本|構成|キャラクター原案|監修|作・画|[:：])")


def names_of(rec):
    raw = rec.get("schema:creator")
    out = []
    items = raw if isinstance(raw, list) else [raw]
    for it in items:
        if not isinstance(it, str):
            continue
        for p in re.split(r"[／/,、，;；・]| ", it):
            p = nk(ROLE.sub("", p))
            if len(p) >= 2:
                out.append(p)
    return out


def volnum(rec):
    v = unicodedata.normalize("NFKC", str(rec.get("schema:volumeNumber") or ""))
    m = re.search(r"\d+", v)
    return int(m.group()) if m else None


print("MADB 読み込み…", flush=True)
G = json.load(open(".cache/madb/metadata101-clean.json", encoding="utf-8"))["@graph"]
by_isbn = {}
by_name = defaultdict(list)
for r in G:
    ib = to13(r.get("schema:isbn"))
    if ib:
        by_isbn[ib] = r
    for n in set(names_of(r)):
        by_name[n].append(r)
print(f"MADB {len(G):,} 記録 / ISBN {len(by_isbn):,} / 著者キー {len(by_name):,}", flush=True)

page_idx = json.load(open(".cache/isbn-page-index.json", encoding="utf-8"))
con = sqlite3.connect(".cache/db-v2.sqlite")
db = {r[0]: r[1] for r in con.execute(
    "SELECT v.isbn13, se.series_key FROM volumes v JOIN editions e ON e.id=v.edition_id JOIN series se ON se.id=e.series_id WHERE v.isbn13 IS NOT NULL")}

tg = list(csv.DictReader(open("docs/production-diagnostics/volgap-fill-targets.tsv", encoding="utf-8"), delimiter="\t"))
want = defaultdict(set)  # (stem, ei) -> 欠番
for r in tg:
    want[(r["stem"], int(r["ei"]))].add(int(r["number"]))

out = []
for (stem, ei), miss in sorted(want.items()):
    d = yaml.safe_load(open(f"data/manga.v2/{stem}.yml", encoding="utf-8"))
    eds = d.get("editions") or []
    if ei >= len(eds):
        continue
    e = eds[ei]
    vols = list(e.get("volumes") or []) + [v for x in (e.get("versions") or []) for v in (x.get("volumes") or [])]
    have = [v for v in vols if v.get("isbn13")]
    recs = [by_isbn[str(v["isbn13"])] for v in have if str(v["isbn13"]) in by_isbn]
    pnames = {nk(a.get("name")) for a in (d.get("authors") or []) if a.get("name")}
    names = set(pnames)
    brands, pubs, titles = set(), set(), {nk(d.get("title"))}
    for r in recs:
        names |= set(names_of(r))
        b = nk(first_str(r.get("schema:brand")))
        if b:
            brands.add(b)
        p = nk(first_str(r.get("schema:publisher")))
        if p:
            pubs.add(p)
        t = nk(first_str(r.get("schema:name")))
        if t:
            titles.add(t)
    if e.get("publisher"):
        pubs.add(nk(e["publisher"]))
    names.discard("")
    seen = set()
    for n in names:
        for r in by_name.get(n, []):
            ib = to13(r.get("schema:isbn"))
            key = ib or r.get("@id")
            if key in seen:
                continue
            vn = volnum(r)
            t = nk(first_str(r.get("schema:name")))
            lab = nk(r.get("rdfs:label"))
            # 巻番号: 欠番に当たるか、番号なしで欠番に1が在る(1巻が無番号で出る型)
            if not ((vn is not None and vn in miss) or (vn is None and 1 in miss)):
                continue
            # 題が似ている: 頁/既存巻の題のどれかと 4文字以上 or 全長 で重なる
            def sim(a, b):
                if not a or not b:
                    return False
                if a in b or b in a:
                    return True
                k = min(4, len(a), len(b))
                return any(a[i:i + k] in b for i in range(len(a) - k + 1))
            if not any(sim(x, t) or sim(x, lab) for x in titles):
                continue
            b = nk(first_str(r.get("schema:brand")))
            p = nk(first_str(r.get("schema:publisher")))
            if not ((b and b in brands) or (p and p in pubs)):
                continue
            seen.add(key)
            where = page_idx.get(ib)
            out.append({
                "stem": stem, "title": d.get("title"), "ei": ei, "etype": e.get("type"), "imprint": e.get("imprint") or e.get("label"),
                "missing": ",".join(map(str, sorted(miss))), "cand_vol": vn if vn is not None else "(無番号)",
                "isbn": ib or "(ISBNなし)", "cand_label": r.get("rdfs:label"), "cand_brand": first_str(r.get("schema:brand")),
                "cand_pub": first_str(r.get("schema:publisher")), "cand_date": r.get("schema:datePublished"),
                "brand_match": "o" if b and b in brands else "", "where": ",".join(where) if isinstance(where, list) else (where or ""),
                "in_db": db.get(ib, ""),
            })

cols = list(out[0].keys()) if out else []
with open("docs/production-diagnostics/volgap-madb-siblings.tsv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, delimiter="\t")
    w.writeheader()
    w.writerows(out)
pages = {(o["stem"]) for o in out}
print(f"候補 {len(out)} 件 / {len(pages)} 頁")
by_kind = defaultdict(int)
for o in out:
    k = "ISBNなし" if o["isbn"] == "(ISBNなし)" else ("本番の別頁" if o["where"] and o["stem"] not in o["where"] else ("同じ頁" if o["where"] else ("種2のみ" if o["in_db"] else "どこにも無い")))
    by_kind[k] += 1
print(dict(by_kind))
