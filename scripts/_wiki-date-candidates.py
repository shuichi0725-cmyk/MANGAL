# -*- coding: utf-8 -*-
"""Wikipedia発売日 掃引 STEP0 = 掃引候補(jawikiに記事がある本番頁)を確定する。

★盲目的に本番69,223頁へ記事取得をかけない。Wikidata(QLever)への1クエリで
  「jawikiに記事がある漫画作品」14,443件の記事名を取り、本番の題と突合して候補を絞る。

出力:
  .cache/jawiki-manga-titles.json  [{qid, name}]           (再取得を避けるキャッシュ)
  .cache/jawiki-title-hits.json    [[stem, 本番title, 巻数, jawiki記事名]]

usage: python scripts/_wiki-date-candidates.py [--refresh]
"""
import argparse, collections, glob, io, json, os, re, sys, unicodedata
import urllib.request, urllib.parse

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TITLES = os.path.join(ROOT, ".cache", "jawiki-manga-titles.json")
HITS = os.path.join(ROOT, ".cache", "jawiki-title-hits.json")
ENDPOINT = "https://qlever.dev/api/wikidata"   # ★WDQSは障害が多く1req/分に絞られる
UA = "MANGAL-bot/1.0 (manga database)"

QUERY = """
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX schema: <http://schema.org/>
SELECT ?item ?name WHERE {
  VALUES ?cls { wd:Q8274 wd:Q21198342 }
  ?item wdt:P31 ?cls .
  ?a schema:about ?item ; schema:isPartOf <https://ja.wikipedia.org/> ; schema:name ?name .
}
"""


def norm(t):
    t = unicodedata.normalize("NFKC", str(t or ""))
    t = re.sub(r"\s*[（(][^）)]*[）)]\s*$", "", t)          # 曖昧さ回避の括弧を落とす
    return re.sub(r"[\s　・!！?？:：〜~\-＆&。、．.『』「」♥❤☆★]", "", t).lower()


def band(n):
    return ("1巻以下" if n <= 1 else "2巻" if n <= 2 else "3-4巻" if n <= 4 else
            "5-9巻" if n <= 9 else "10-19巻" if n <= 19 else "20巻以上")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="Wikidataを引き直す")
    a = ap.parse_args()

    if a.refresh or not os.path.exists(TITLES):
        req = urllib.request.Request(
            ENDPOINT + "?" + urllib.parse.urlencode({"query": QUERY}),
            headers={"User-Agent": UA, "Accept": "application/sparql-results+json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            d = json.loads(r.read().decode("utf-8"))
        titles = [{"qid": b["item"]["value"].rsplit("/", 1)[-1], "name": b["name"]["value"]}
                  for b in d["results"]["bindings"]]
        json.dump(titles, io.open(TITLES, "w", encoding="utf-8"), ensure_ascii=False)
    else:
        titles = json.load(io.open(TITLES, encoding="utf-8"))
    print("jawiki 漫画記事:", len(titles))

    widx = collections.defaultdict(list)
    for t in titles:
        widx[norm(t["name"])].append(t["name"])

    files = glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml"))
    rows = []
    bt, bh = collections.Counter(), collections.Counter()
    for p in files:
        s = io.open(p, encoding="utf-8", errors="replace").read()
        n = len(re.findall(r"^\s*-\s*number:", s, re.M))
        bt[band(n)] += 1
        m = re.search(r"^title:\s*(.+)$", s, re.M)
        if not m:
            continue
        ti = m.group(1).strip().strip("'\"")
        k = norm(ti)
        if k and k in widx:
            bh[band(n)] += 1
            rows.append([os.path.basename(p)[:-4], ti, n, widx[k][0]])

    json.dump(rows, io.open(HITS, "w", encoding="utf-8"), ensure_ascii=False)
    print("本番頁 %d / 題一致 = 掃引候補 %d" % (len(files), len(rows)))
    print("\n帯          本番頁数   候補   率")
    for b in ["1巻以下", "2巻", "3-4巻", "5-9巻", "10-19巻", "20巻以上"]:
        print("%-9s %8d %6d  %4.1f%%" % (b, bt[b], bh[b], 100.0 * bh[b] / bt[b] if bt[b] else 0))
    print("\n->", os.path.relpath(HITS, ROOT))


main()
