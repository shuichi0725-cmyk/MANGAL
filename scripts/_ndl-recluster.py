"""NDL DCNDL RDF で巻を作画別に再クラスタ(option2の正しい分割)。★候補のみ・適用なし。

NDLは著者典拠ID + 読み(transcription)を持つ。 これで作画版を確実に分離する。

usage:
  1) python _ndl-recluster.py <rdf> <base>            # creator頻度表を表示(版を見極める)
  2) python _ndl-recluster.py <rdf> <base> ID:姓 ...  # 作画版IDを指定して再クラスタ+DB照合
     例: ... 00065332:saito 00707303:takemura
ISBNに作画版IDが含まれればその版、 どれも無ければ第1引数の版(主版)既定。
出力: data/seeds/slug-recluster-candidates.tsv へ追記。
"""
import sys, re, csv, sqlite3
from collections import defaultdict, Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent


def parse(rdf):
    xml = open(rdf, encoding="utf-8").read()
    recs = re.split(r"<dcndl:BibResource", xml)[1:]
    vols, id_name, id_read = [], {}, {}
    for r in recs:
        mi = re.search(r"97[0-9]{11}", r)
        if not mi:
            continue
        my = re.search(r"<dcterms:date>(\d{4})", r)
        ids = re.findall(r"entity/(\w+)", r)
        for a in re.findall(r"<dcterms:creator>.*?</dcterms:creator>", r, re.S):
            cid = re.search(r"entity/(\w+)", a); nm = re.search(r"<foaf:name>([^<]+)", a); tr = re.search(r"<dcndl:transcription>([^<]+)", a)
            if cid and nm:
                id_name[cid.group(1)] = nm.group(1); id_read[cid.group(1)] = tr.group(1) if tr else ""
        vols.append({"isbn": mi.group(0), "year": my.group(1) if my else "", "ids": set(ids)})
    return vols, id_name, id_read


def main():
    rdf, base = sys.argv[1], sys.argv[2]
    specs = [s.split(":") for s in sys.argv[3:]]  # [(id, surname), ...]
    vols, id_name, id_read = parse(rdf)
    if not specs:
        freq = Counter(i for v in vols for i in v["ids"])
        print("=== %s : ISBN有 %d巻 / 著者典拠頻度 ===" % (base, len(vols)))
        for cid, c in freq.most_common(12):
            print("  id%-12s %-16s 読%-16s %d巻" % (cid, id_name.get(cid, "")[:16], id_read.get(cid, "")[:16], c))
        print("\n→ 作画版を見極めて再実行: python _ndl-recluster.py <rdf> %s ID:姓 ID:姓" % base)
        return
    sak_ids = [s[0] for s in specs]
    sur = {s[0]: s[1] for s in specs}
    main_id = sak_ids[0]  # 主版(IDが付かない巻の既定)

    def ver_of(ids):
        hit = [s for s in sak_ids if s in ids]
        # 複数作画IDがあれば「最も少数=specific」を採るためspecs後方優先
        return hit[-1] if hit else main_id

    # 我々DBの該当巻ISBN
    con = sqlite3.connect(str(ROOT / ".cache" / "db-v2.sqlite")); con.text_factory = lambda b: b.decode("utf-8", "replace")
    isbn2ver = {v["isbn"]: ver_of(v["ids"]) for v in vols}
    isbn2year = {v["isbn"]: v["year"] for v in vols}
    seen = set(); db_isbn = []
    for r in csv.DictReader((ROOT / ".cache" / "slug-final.tsv").open(encoding="utf-8"), delimiter="\t"):
        if r["base_slug"] == base and r["rep"] not in seen:
            seen.add(r["rep"])
            for (i,) in con.execute("SELECT v.isbn13 FROM series s JOIN editions e ON e.series_id=s.id JOIN volumes v ON v.edition_id=e.id WHERE s.series_key=? AND v.isbn13 IS NOT NULL", (r["rep"],)):
                db_isbn.append(str(i).replace("-", ""))
    grp = defaultdict(list)
    for ib in db_isbn:
        grp[isbn2ver.get(ib, main_id)].append(ib)

    out = ROOT / "data" / "seeds" / "slug-recluster-candidates.tsv"
    new = not out.exists()
    print("=== %s 再クラスタ(DB %d巻) ===" % (base, len(db_isbn)))
    with out.open("a", encoding="utf-8") as f:
        if new:
            f.write("base\tversion_id\tsakuga\tslug\tyear\tn_vols\tisbns\n")
        for sid in sak_ids:
            ibs = grp.get(sid, [])
            ys = [int(isbn2year[i]) for i in ibs if isbn2year.get(i)]
            y0 = min(ys) if ys else ""
            slug = "-".join([base, sur[sid]] + ([str(y0)] if y0 else []))
            print("  %s(%s): %d巻 年%s → %s" % (sur[sid], id_name.get(sid, "")[:14], len(ibs), y0, slug))
            f.write("%s\t%s\t%s\t%s\t%s\t%d\t%s\n" % (base, sid, sur[sid], slug, y0, len(ibs), ",".join(ibs)))
    print("→ %s に追記" % out.name)


if __name__ == "__main__":
    main()
