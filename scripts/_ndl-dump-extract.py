"""NDL サーチ 全件ファイル(OAI-PMH dcndl・月1更新)から MANGAL に要る書誌だけ抜き出す。

★2026-11-23 新設(ユーザ「一つ落として作ってみて」): 照会API(opensearch)は NDL 429 が長引くため、
  全件ファイル https://ndlsearch.ndl.go.jp/files/oaipmhAllData/xmlList.txt (約26,400本・各5,000件・圧縮約4MB)を
  1本ずつ 落とす → 抜き出す → 元ファイルを D:/NDL へコピー → 手元を消す(2026-11-23 ユーザ指示で保管)。
  中身は NDL 蔵書以外(論文・雑誌記事・デジコレ…)も混ざる = setSpec が iss-ndl-opac* の書誌だけ見る。

残す条件(どれか): ①ISBN が MANGAL の ISBN 索引(.cache/isbn-page-index.json)に在る
                  ②NDC が 726.1(漫画)/ NDLC が Y84 (= 掲載外の漫画も拾う=取りこぼし発見用)
出力: .cache/ndl-dump/extract/<連番>.jsonl.gz(1行1書誌)+ 済み台帳 .cache/ndl-dump/done.txt(再開可)

使い方:
  python scripts/_ndl-dump-extract.py file <path.gz>          # 手元の1本だけ抜き出して要約
  python scripts/_ndl-dump-extract.py run [--limit N] [--pace 秒]   # 一覧の未済を順に 落とす→抜く→消す
  python scripts/_ndl-dump-extract.py status
利用条件: NDLサーチAPIの利用条件に従う(営利=申請/継続利用=届出)。 同時に1本だけ・間を空ける。
"""
import gzip
import json
import os
import re
import shutil
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache", "ndl-dump")
RAW = os.path.join(CACHE, "raw")
OUT = os.path.join(CACHE, "extract")
DONE = os.path.join(CACHE, "done.txt")
LIST_URL = "https://ndlsearch.ndl.go.jp/files/oaipmhAllData/xmlList.txt"
LIST = os.path.join(CACHE, "xmlList.txt")
STOP = os.path.join(CACHE, "STOP")
STORE = os.environ.get("NDL_DUMP_STORE", "D:/NDL")  # 元ファイルの保管先(2026-11-23 ユーザ指示)。空=保管しない
UA = "MANGAL-ndl-dump/1.0"

NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "dcndl": "http://ndl.go.jp/dcndl/terms/",
    "foaf": "http://xmlns.com/foaf/0.1/",
}
RDF_ABOUT = "{%s}about" % NS["rdf"]
RDF_RES = "{%s}resource" % NS["rdf"]
RDF_DT = "{%s}datatype" % NS["rdf"]


def q(tag):
    p, t = tag.split(":")
    return "{%s}%s" % (NS[p], t)


def isbn13(s):
    d = re.sub(r"[^0-9Xx]", "", s or "").upper()
    if len(d) == 13 and d.isdigit():
        return d
    if len(d) == 10 and d[:9].isdigit():
        core = "978" + d[:9]
        tot = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(core))
        return core + str((10 - tot % 10) % 10)
    return None


def _txt(e):
    return (e.text or "").strip() if e is not None else ""


def _desc(parent, tag):
    """dc:title / dcndl:seriesTitle 等の rdf:Description(value+transcription)を列挙。"""
    out = []
    for el in parent.findall(q(tag)):
        d = el.find(q("rdf:Description"))
        if d is not None:
            out.append({"value": _txt(d.find(q("rdf:value"))),
                        "kana": _txt(d.find(q("dcndl:transcription")))})
        elif _txt(el):
            out.append({"value": _txt(el), "kana": ""})
    return out


def parse_record(rec):
    hdr = rec.find(q("oai:header"))
    if hdr is None or hdr.get("status") == "deleted":
        return None
    sets = [_txt(s) for s in hdr.findall(q("oai:setSpec"))]
    if not any(s.startswith("iss-ndl-opac") for s in sets):
        return None
    rdf = rec.find(".//" + q("rdf:RDF"))
    if rdf is None:
        return None
    bib = None
    for b in rdf.findall(q("dcndl:BibResource")):
        if b.find(q("dcterms:title")) is not None or b.find(q("dc:title")) is not None:
            bib = b
            break
    if bib is None:
        return None
    ids = {}
    for i in bib.findall(q("dcterms:identifier")):
        dt = (i.get(RDF_DT) or "").rsplit("/", 1)[-1]
        ids.setdefault(dt, []).append(_txt(i))
    isbns = sorted({x for x in (isbn13(v) for v in ids.get("ISBN", [])) if x})
    subj = {}
    for s in bib.findall(q("dc:subject")):
        dt = (s.get(RDF_DT) or "").rsplit("/", 1)[-1]
        subj.setdefault(dt, []).append(_txt(s))
    classes = [ (s.get(RDF_RES) or "").replace("http://id.ndl.go.jp/class/", "")
               for s in bib.findall(q("dcterms:subject")) if s.get(RDF_RES)]
    headings = [_txt(d.find(q("rdf:value"))) for s in bib.findall(q("dcterms:subject"))
                for d in s.findall(q("rdf:Description"))]
    creators = []
    for c in bib.findall(q("dcterms:creator")):
        a = c.find(q("foaf:Agent"))
        if a is None:
            continue
        creators.append({"name": _txt(a.find(q("foaf:name"))),
                         "kana": _txt(a.find(q("dcndl:transcription"))),
                         "auth": (a.get(RDF_ABOUT) or "").rsplit("/", 1)[-1]})
    pubs = []
    for p in bib.findall(q("dcterms:publisher")):
        a = p.find(q("foaf:Agent"))
        if a is not None:
            pubs.append(_txt(a.find(q("foaf:name"))))
    ndc = [v for k, vs in subj.items() if k.startswith("NDC") for v in vs]
    return {
        "id": _txt(hdr.find(q("oai:identifier"))).rsplit(":", 1)[-1],
        "datestamp": _txt(hdr.find(q("oai:datestamp"))),
        "sets": sets,
        "isbn": isbns,
        "jpno": ids.get("JPNO", []),
        "bibid": ids.get("NDLBibID", []),
        "title": _desc(bib, "dc:title"),
        "volume": _desc(bib, "dcndl:volume"),
        "volume_title": _desc(bib, "dcndl:volumeTitle"),
        "series": _desc(bib, "dcndl:seriesTitle"),
        "alternative": _desc(bib, "dcndl:alternative"),
        "creators": creators,
        "dc_creator": [_txt(x) for x in bib.findall(q("dc:creator"))],
        "creator_alt": [_txt(x) for x in bib.findall(q("dcndl:creatorAlternative"))],
        "publisher": pubs,
        "issued": _txt(bib.find(q("dcterms:issued"))),
        "date": _txt(bib.find(q("dcterms:date"))),
        "edition": _txt(bib.find(q("dcndl:edition"))),
        "extent": _txt(bib.find(q("dcterms:extent"))),
        "price": _txt(bib.find(q("dcndl:price"))),
        "ndc": ndc,
        "class": classes,
        "subject": headings,
        "genre": [_txt(x) for x in bib.findall(q("dcndl:genre"))],
        "audience": [_txt(x) for x in bib.findall(q("dcterms:audience"))],
        "description": [_txt(x) for x in bib.findall(q("dcterms:description"))],
        "part": [_txt(x) for x in bib.findall(q("dcndl:partInformation"))],
    }


def _keep(r, idx):
    if any(i in idx for i in r["isbn"]):
        return "isbn"
    if any(n.startswith("726.1") for n in r["ndc"]) or any(c.endswith("/Y84") for c in r["class"]):
        return "manga"
    return None


_IDX = None


def load_index():
    global _IDX
    if _IDX is None:
        p = os.path.join(ROOT, ".cache", "isbn-page-index.json")
        _IDX = set(json.load(open(p, encoding="utf-8")))
    return _IDX


def extract_file(path, out_path):
    idx = load_index()
    n_all = n_opac = 0
    kept = {"isbn": 0, "manga": 0}
    tmp = out_path + ".tmp"
    with gzip.open(path, "rb") as src, gzip.open(tmp, "wt", encoding="utf-8") as dst:
        for ev, el in ET.iterparse(src, events=("end",)):
            if el.tag != q("oai:record"):
                continue
            n_all += 1
            r = parse_record(el)
            el.clear()
            if r is None:
                continue
            n_opac += 1
            why = _keep(r, idx)
            if why:
                r["why"] = why
                kept[why] += 1
                dst.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, out_path)
    return n_all, n_opac, kept


def _urls():
    if not os.path.exists(LIST) or time.time() - os.path.getmtime(LIST) > 20 * 86400:
        os.makedirs(CACHE, exist_ok=True)
        req = urllib.request.Request(LIST_URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            open(LIST, "wb").write(r.read())
    return [u.strip() for u in open(LIST, encoding="utf-8") if u.strip()]


def _done():
    return set(open(DONE, encoding="utf-8").read().split()) if os.path.exists(DONE) else set()


def cmd_run(limit, pace):
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    if STORE:
        os.makedirs(STORE, exist_ok=True)
    urls = _urls()
    done = _done()
    todo = [u for u in urls if u.rsplit("/", 1)[-1] not in done]
    print(f"全{len(urls)}本 / 済{len(urls) - len(todo)} / 残{len(todo)}", flush=True)
    for k, u in enumerate(todo[:limit] if limit else todo, 1):
        if os.path.exists(STOP):
            raise SystemExit("STOP 札を見て停止")
        name = u.rsplit("/", 1)[-1]
        raw = os.path.join(RAW, name)
        t0 = time.time()
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=300) as r, open(raw, "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
        except urllib.error.HTTPError as e:
            if os.path.exists(raw):
                os.remove(raw)
            raise SystemExit(f"HTTP {e.code} {name} → 即停止(再開可)")
        n_all, n_opac, kept = extract_file(raw, os.path.join(OUT, name.replace(".gz", ".jsonl.gz")))
        if STORE:  # ★ユーザ指示(2026-11-23): 落とした元ファイルは D:/NDL に保管(コピー→大きさ照合→手元を消す)
            dst = os.path.join(STORE, name)
            shutil.copy2(raw, dst)
            if os.path.getsize(dst) != os.path.getsize(raw):
                raise SystemExit(f"D: へのコピーの大きさが合わない {name} → 停止")
        os.remove(raw)
        with open(DONE, "a", encoding="utf-8") as f:
            f.write(name + "\n")
        print(f"[{time.strftime('%H:%M:%S')}] {k} {name[:40]} 全{n_all} 蔵書{n_opac} 残す isbn{kept['isbn']} 漫画{kept['manga']} "
              f"{time.time() - t0:.1f}秒", flush=True)
        time.sleep(pace)


def cmd_status():
    urls = _urls() if os.path.exists(LIST) else []
    done = _done()
    tot = {"isbn": 0, "manga": 0}
    for fn in os.listdir(OUT) if os.path.isdir(OUT) else []:
        for ln in gzip.open(os.path.join(OUT, fn), "rt", encoding="utf-8"):
            tot[json.loads(ln)["why"]] += 1
    print(f"済 {len(done)} / 全 {len(urls)} 本 ・ 抜いた書誌 isbn一致 {tot['isbn']} / 漫画(NDC726.1・Y84) {tot['manga']}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__)
    elif a[0] == "file":
        out = os.path.join(CACHE, "sample.jsonl.gz")
        n_all, n_opac, kept = extract_file(a[1], out)
        print(f"全{n_all} 蔵書{n_opac} 残す {kept} → {out}")
    elif a[0] == "run":
        lim = int(a[a.index("--limit") + 1]) if "--limit" in a else 0
        pace = float(a[a.index("--pace") + 1]) if "--pace" in a else 5.0
        cmd_run(lim, pace)
    elif a[0] == "status":
        cmd_status()
