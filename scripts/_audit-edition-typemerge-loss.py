# -*- coding: utf-8 -*-
"""同type版の合流で「別の出版社の版」が1タブに畳まれ、巻番号の衝突で巻が消える型 (2026-08-30 新設)。

きっかけ: コンビニ掃引(bucket B)で 隻眼の竜 が「Akita top comics wide が6巻で主版5巻より多い」
  として挙がったが、中身は**リイド社SPコミックスのISBN**(978-4-8458)で、秋田書店のレーベル名を
  名乗っていた。調べると コンビニ案件ではなく**版の取り違え**だった。

★真因 = promote は既定で **同typeの版を1タブに畳む**(`group_key = effective_type`)。
  種2が持つ4版(SPコミックス6/Akita top comics wide2/リイド文庫5/秋田文庫4)が
  standard 2版・bunkobon 2版にそれぞれ合流し、**巻番号の衝突で
  秋田文庫4巻と秋田版2巻が丸ごと不可視**になっていた(頁からは「巻抜け」にすら見えない)。

  - `separate_editions`(series-merge.yml)は **sid単位**の分離なので、
    1つのsidが4版を持つこの形には効かない。
  - `group_key` を (type × imprint) に変えると **X の「あすかコミックス / ASUKA COMICS」**の
    ような ARMS型の表記ゆれを誤って割る([[imprint_split_arms_type]])。
  → よって共有ロジックは触らず、**per-caseで canonical seed を起こして版を組み直す**のが是正。

■ 判定 (= 表記ゆれと切り分けるため、名前ではなく**出版社の実体**で見る)
  ① 本番の1つの版タブが、種2では**2つ以上の edition** に由来する
  ② それらの **ISBNから引いた出版社(種1 metadata101 schema:publisher)が実際に違う**
     ★ここが肝。imprintの文字列比較だと「あすかコミックス/ASUKA COMICS」を別物と誤判定する
  ③ 消えた巻 = その種2 editionのISBNのうち、**本番のどの頁にも出ていない**もの
     (promoteが意図的に落とすもの= KEEP外type / drop対象imprint / volume-exclude は除く)

  ★LOST>0 が実害。LOST=0 は「畳まれてはいるがレーベル名が混ざっただけ」で優先度は低い。

出力: docs/production-diagnostics/edition-typemerge-loss.tsv
是正: canonical seed(`data/seeds/edition-canonical/<SRC slug>.yml`)で版を明示的に組み直す。
      ★出版社は 楽天books と ISBN出版者記号 の**両方**で確認してから書くこと。

  python scripts/_audit-edition-typemerge-loss.py
"""
import collections, io, json, os, re, sqlite3, sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAT = os.path.join(ROOT, ".cache", "volume-flat.tsv")
DB = os.path.join(ROOT, ".cache", "db-v2.sqlite")
IDX = os.path.join(ROOT, ".cache", "isbn-page-index.json")
META = os.path.join(ROOT, ".cache", "madb", "metadata101-clean.json")
PUBCACHE = os.path.join(ROOT, ".cache", "isbn-publisher.tsv")
CANON = os.path.join(ROOT, "data", "seeds", "edition-canonical")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "edition-typemerge-loss.tsv")

KEEP_TYPES = {"standard", "bunkobon", "wideban", "kanzenban", "shinsoban", "aizoban", "deluxe"}
DROP_IMP = ["My first big", "コンビニ", "増刊", "同人", "ジャンプremix", "フィルムコミック",
            "カッパ・ノベル", "カッパノベル", "カッパ・ホーム", "カッパホーム",
            "KPC", "プラチナコミックス", "リミックス", "SJR"]
DROP_IMP_L = ["bilingual", "english", "novel", "novels", "remix", "collection box"]


def _to13(s):
    s = re.sub(r"[^0-9Xx]", "", str(s or ""))
    if len(s) == 13:
        return s
    if len(s) == 10:
        c = "978" + s[:9]
        d = sum((1 if i % 2 == 0 else 3) * int(x) for i, x in enumerate(c))
        return c + str((10 - d % 10) % 10)
    return ""


def dropped_imprint(imp):
    i = str(imp or "")
    return any(p in i for p in DROP_IMP) or any(p in i.lower() for p in DROP_IMP_L)


def load_pub():
    """isbn13 → 出版社。metadata101 は重いので TSV に焼いて再利用する。"""
    if os.path.exists(PUBCACHE):
        d = {}
        with io.open(PUBCACHE, encoding="utf-8") as f:
            for l in f:
                a, _, b = l.rstrip("\n").partition("\t")
                d[a] = b
        return d
    print("metadata101 から isbn→出版社 を構築中(初回のみ)…", flush=True)
    g = json.load(io.open(META, encoding="utf-8"))
    rows = g.get("@graph", g) if isinstance(g, dict) else g
    d = {}
    for r in rows:
        p = r.get("schema:publisher") or r.get("publisher")
        if isinstance(p, list):
            p = p[0] if p else None
        if isinstance(p, dict):
            p = p.get("@value") or p.get("name")
        i = r.get("schema:isbn") or r.get("isbn")
        if isinstance(i, list):
            i = i[0] if i else None
        k = _to13(i)
        if k and p:
            d[k] = str(p).strip()
    with io.open(PUBCACHE, "w", encoding="utf-8", newline="\n") as f:
        for k, v in d.items():
            f.write("%s\t%s\n" % (k, v))
    print("  %d件 → %s" % (len(d), os.path.relpath(PUBCACHE, ROOT)))
    return d


def main():
    pub = load_pub()
    idx = json.load(io.open(IDX, encoding="utf-8"))
    canon = {f[:-4] for f in os.listdir(CANON) if f.endswith(".yml")}

    con = sqlite3.connect(DB)
    e_of, e_meta = {}, {}
    for eid, ty, imp, isbn in con.execute(
            "SELECT e.id,e.type,e.imprint,v.isbn13 FROM editions e JOIN volumes v ON v.edition_id=e.id"):
        if isbn:
            e_of[isbn] = eid
        e_meta.setdefault(eid, {"type": ty, "imprint": imp, "isbns": []})["isbns"].append(isbn)

    tabs = collections.defaultdict(list)
    meta = {}
    with io.open(FLAT, encoding="utf-8") as f:
        h = next(f).rstrip("\n").split("\t")
        I = {k: h.index(k) for k in h}
        for l in f:
            c = l.rstrip("\n").split("\t")
            if c[I["is_version"]] == "1":
                continue
            k = (c[I["slug"]], c[I["ed_idx"]])
            tabs[k].append(c[I["isbn13"]])
            meta[k] = (c[I["title"]], c[I["ed_label"]], c[I["ed_imprint"]], c[I["ed_type"]])

    rows = []
    for (slug, ei), isbns in sorted(tabs.items()):
        eids = {e_of[i] for i in isbns if i in e_of}
        if len(eids) < 2:
            continue
        pubs = collections.defaultdict(set)
        for eid in eids:
            for i in e_meta[eid]["isbns"]:
                if i in pub:
                    pubs[eid].add(pub[i])
        # ② 出版社の実体が違う edition が2つ以上あるか(表記ゆれ除外の肝)
        allp = set()
        for s in pubs.values():
            allp |= s
        if len(allp) < 2:
            continue
        have = set(isbns)
        lost = []
        for eid in sorted(eids):
            m = e_meta[eid]
            if m["type"] not in KEEP_TYPES or dropped_imprint(m["imprint"]):
                continue
            for i in m["isbns"]:
                if i and i not in have and not idx.get(i):
                    lost.append((m["imprint"], i))
        if not lost and len(allp) < 2:
            continue
        ti, lb, im, ty = meta[(slug, ei)]
        rows.append((len(lost), slug, ti, ty, lb, im, len(isbns),
                     " / ".join(sorted("%s[%s]" % (e_meta[e]["imprint"], ",".join(sorted(pubs[e]))[:24])
                                       for e in eids))[:180],
                     "canonical有" if slug in canon else "",
                     ";".join(i for _, i in lost[:6])))
    rows.sort(key=lambda r: (-r[0], r[1]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("消えた巻数\tslug\ttitle\ttype\t表示label\t表示imprint\t表示巻数\t畳まれた種2版[出版社]\tcanonical\t消えたISBN\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")
    lostrows = [r for r in rows if r[0] > 0]
    print("同type合流タブ(出版社が実際に違う): %d 件 / うち★巻が消えているもの %d 件 (計 %d 巻)"
          % (len(rows), len(lostrows), sum(r[0] for r in rows)))
    print("→ %s" % os.path.relpath(OUT, ROOT))
    print("\n--- 消えた巻が多い順 上位25 ---")
    for r in lostrows[:25]:
        print("  %3d巻消失 %-34s %-9s 表示=%-20s | %s" % (r[0], r[1][:32], r[3], (r[5] or "")[:18], r[7][:96]))


if __name__ == "__main__":
    main()
