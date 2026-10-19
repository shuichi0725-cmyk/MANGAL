"""作品(work)QID の 言語別ラベル(rdfs:label)を Wikidata から一括取得 = 他言語名の一次ソース。

★2026-10-19 らんま1/2「他言語がハングルしかない」報告で新設。
  AniList synonyms は言語タグが無く(韓/中/タイ/英別名/ローマ字/日本語別名が混在)、
  英題(title.english)も synonyms に入らない。 Wikidata は 1言語1ラベルで言語コード付き。

- 入力 = .cache/work-qid-map.json(_fetch-work-qid.py = AniList ID P8731 経由の一意join)
- ★rdfs:label のみ(skos:altLabel は人物名・旧題・誤記が混じるので使わない)
- QLever(独立・高速・VALUES一括)。 400 QID/batch・batch間 sleep・retry
- 中断再開可: 既取得 QID は skip(--refresh で全件取り直し)
- 純粋追加レイヤー: 種1/種2/種3 不変。 promote が work_wikidata_qid 経由で join

出力: .cache/work-labels.json = {qid: {lang: label}}
"""
import json, sys, time, urllib.parse, urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
QMAP = Path(".cache/work-qid-map.json")
OUT = Path(".cache/work-labels.json")
ENDPOINT = "https://qlever.dev/api/wikidata"
UA = "MANGAL-research/1.0 (https://mangal.shuichi0725.workers.dev; shuichi0725@gmail.com)"
BATCH = 400
SLEEP = 0.5
PREFIX = ("PREFIX wd: <http://www.wikidata.org/entity/> "
          "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> ")


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
            wait = SLEEP * (2 ** attempt) + 1
            print(f"    retry {attempt+1}/5 ({e}) wait {wait:.0f}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError("SPARQL failed after retries")


def main():
    qmap = json.loads(QMAP.read_text(encoding="utf-8"))
    qids = sorted({v["qid"] for v in qmap.values() if v and v.get("qid")})
    out = {} if "--refresh" in sys.argv or not OUT.exists() else json.loads(OUT.read_text(encoding="utf-8"))
    todo = [q for q in qids if q not in out]
    print(f"作品QID: {len(qids):,} / 既取得: {len(out):,} / 残: {len(todo):,}")
    for bi in range(0, len(todo), BATCH):
        chunk = todo[bi:bi + BATCH]
        vals = " ".join(f"wd:{q}" for q in chunk)
        rows = run(PREFIX + "SELECT ?w ?l WHERE { VALUES ?w { " + vals + " } ?w rdfs:label ?l . }")
        got = {q: {} for q in chunk}  # ラベル無しも {} で記録(再開時 skip)
        for b in rows:
            qid = b["w"]["value"].rsplit("/", 1)[-1]
            lang = b["l"].get("xml:lang")
            if lang:
                got.setdefault(qid, {})[lang] = b["l"]["value"]
        out.update(got)
        OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        print(f"  batch {min(bi + BATCH, len(todo)):,}/{len(todo):,}  ラベル {len(rows):,}行")
        time.sleep(SLEEP)
    n_lab = sum(len(v) for v in out.values())
    print(f"★完了: QID {len(out):,} / ラベル {n_lab:,}(平均 {n_lab / max(1, len(out)):.1f}言語)")


if __name__ == "__main__":
    main()
