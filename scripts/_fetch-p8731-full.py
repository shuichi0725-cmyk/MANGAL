"""Wikidata P8731(AniList manga ID)全量マップの取得 (= 計画③ recall の正解チャネル)。

_fetch-work-qid.py(既結線aidの逆引き)と違い、 ★P8731を持つ全項目を取る:
  aid → {qid, label(ja優先), aliases(ja)}
これで「うちの未マッチ頁題 == Wikidata公式ラベル/別名」→ P8731 で AniList ID 直結線が引ける。
QLever(WDQSは1req/分制限のため不使用)・LIMIT/OFFSET ページング・中断再開は上書きで単純化。

出力: .cache/p8731-full-map.json = {aid(str): {"qid","label","aliases":[...]}}
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".cache/p8731-full-map.json"
ENDPOINT = "https://qlever.dev/api/wikidata"
UA = "MANGAL-research/1.0 (https://mangal.shuichi0725.workers.dev; shuichi0725@gmail.com)"
PREFIX = ("PREFIX wdt: <http://www.wikidata.org/prop/direct/> "
          "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
          "PREFIX skos: <http://www.w3.org/2004/02/skos/core#> ")
PAGE = 100000


def run(q):
    data = urllib.parse.urlencode({"query": q}).encode()
    req = urllib.request.Request(ENDPOINT, data=data,
                                 headers={"User-Agent": UA,
                                          "Accept": "application/sparql-results+json",
                                          "Content-Type": "application/x-www-form-urlencoded"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode("utf-8"))["results"]["bindings"]
        except Exception as e:
            wait = 2 ** attempt + 1
            print(f"  retry {attempt+1}/5 ({e}) wait {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError("SPARQL failed after retries")


def paged(core, tag):
    rows = []
    off = 0
    while True:
        chunk = run(PREFIX + core + f" LIMIT {PAGE} OFFSET {off}")
        rows.extend(chunk)
        print(f"  {tag}: +{len(chunk):,} (累計 {len(rows):,})")
        if len(chunk) < PAGE:
            return rows
        off += PAGE
        time.sleep(0.5)


def main():
    out = {}
    # 1) aid + qid + jaラベル(無ければ後で en fallback)
    for b in paged("SELECT ?w ?id ?l WHERE { ?w wdt:P8731 ?id . "
                   'OPTIONAL { ?w rdfs:label ?l . FILTER(LANG(?l)="ja") } }', "label-ja"):
        aid = b["id"]["value"]
        qid = b["w"]["value"].rsplit("/", 1)[-1]
        ent = out.setdefault(aid, {"qid": qid, "label": "", "aliases": []})
        if b.get("l"):
            ent["label"] = b["l"]["value"]
    print(f"P8731項目: {len(out):,} (jaラベル {sum(1 for v in out.values() if v['label']):,})")
    # 2) ja別名
    for b in paged("SELECT ?id ?a WHERE { ?w wdt:P8731 ?id . ?w skos:altLabel ?a . "
                   'FILTER(LANG(?a)="ja") }', "alias-ja"):
        aid = b["id"]["value"]
        if aid in out:
            out[aid]["aliases"].append(b["a"]["value"])
    # 3) enラベル fallback(ja無し分のみ)
    for b in paged("SELECT ?id ?l WHERE { ?w wdt:P8731 ?id . ?w rdfs:label ?l . "
                   'FILTER(LANG(?l)="en") }', "label-en"):
        aid = b["id"]["value"]
        if aid in out and not out[aid]["label"]:
            out[aid]["label"] = b["l"]["value"]
    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    n_alias = sum(len(v["aliases"]) for v in out.values())
    print(f"★wrote {OUT}: {len(out):,} aid / 別名 {n_alias:,}")


if __name__ == "__main__":
    main()
