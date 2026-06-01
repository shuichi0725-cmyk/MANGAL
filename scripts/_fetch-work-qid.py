"""作品(work)の Wikidata QID を AniList漫画ID(P8731)経由で一意取得。

★慎重設計:
- 結合キー = anilist_id(既照合済)→ 作品名ファジーマッチ不要 = 誤join ゼロ
- Wikidata SPARQL に VALUES で一括問い合わせ(300/batch)
- 礼儀: User-Agent明示・batch間 sleep・429/5xx は指数backoffで retry
- 中断再開可: .cache/work-qid-map.json に anilist_id→qid を逐次保存
- 純粋追加レイヤー: 種1/種2/種3 不変。 promote が enrich として作品QIDを付与

出力: .cache/work-qid-map.json = {anilist_id(str): {"qid": "Q...", "label": "..."}}
"""
import json, sys, time, urllib.parse, urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ENRICH = Path(".cache/anilist-enrich-map.json")
OUT = Path(".cache/work-qid-map.json")
# ★WDQS(query.wikidata.org)は障害中で1req/分。 QLever(独立・高速)を使う。
ENDPOINT = "https://qlever.dev/api/wikidata"
UA = "MANGAL-research/1.0 (https://mangal.shuichi0725.workers.dev; shuichi0725@gmail.com)"
BATCH = 400
SLEEP = 0.5
PREFIX = "PREFIX wdt: <http://www.wikidata.org/prop/direct/> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "


def run(q):
    data = urllib.parse.urlencode({"query": q}).encode()
    req = urllib.request.Request(ENDPOINT, data=data,
                                 headers={"User-Agent": UA,
                                          "Accept": "application/sparql-results+json",
                                          "Content-Type": "application/x-www-form-urlencoded"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))["results"]["bindings"]
        except Exception as e:
            wait = SLEEP * (2 ** attempt) + 1
            print(f"    retry {attempt+1}/5 ({e}) wait {wait:.0f}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError("SPARQL failed after retries")


def sparql(ids):
    vals = " ".join(f'"{i}"' for i in ids)
    return run(PREFIX + "SELECT ?id ?w WHERE { VALUES ?id { " + vals + " } ?w wdt:P8731 ?id . }")


def main():
    m = json.load(ENRICH.open(encoding="utf-8"))
    ids = sorted({str(v["anilist_id"]) for v in m.values()
                  if isinstance(v, dict) and v.get("anilist_id")})
    out = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    # 既取得(該当なしも空dictで記録)は skip → 再開可
    todo = [i for i in ids if i not in out]
    print(f"全 anilist_id: {len(ids):,} / 既取得: {len(out):,} / 残: {len(todo):,}")
    hit = sum(1 for v in out.values() if v)
    for bi in range(0, len(todo), BATCH):
        chunk = todo[bi:bi + BATCH]
        rows = sparql(chunk)
        found = {}
        for b in rows:
            aid = b["id"]["value"]
            qid = b["w"]["value"].rsplit("/", 1)[-1]
            found[aid] = {"qid": qid}
        for i in chunk:
            out[i] = found.get(i, {})  # 該当なしは {} で記録
        hit += len(found)
        OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        done = min(bi + BATCH, len(todo))
        print(f"  batch {done:,}/{len(todo):,}  この回 {len(found)}件ヒット  累計ヒット {hit:,}")
        time.sleep(SLEEP)
    final_hit = sum(1 for v in out.values() if v)
    print(f"\n★QID取得完了: {len(out):,} 問い合わせ済 / 作品QID {final_hit:,}件")

    # ラベル付与(QA用): 取得済QIDに ja(無ければen)ラベルを引く
    qids = sorted({v["qid"] for v in out.values() if v and not v.get("label")})
    print(f"ラベル未取得 QID: {len(qids):,}")
    for bi in range(0, len(qids), BATCH):
        chunk = qids[bi:bi + BATCH]
        vals = " ".join(f"wd:{q}" for q in chunk)
        q = (PREFIX + "PREFIX wd: <http://www.wikidata.org/entity/> "
             "SELECT ?w ?l WHERE { VALUES ?w { " + vals + " } ?w rdfs:label ?l . "
             'FILTER(LANG(?l)="ja" || LANG(?l)="en") }')
        rows = run(q)
        lab = {}
        for b in rows:
            qid = b["w"]["value"].rsplit("/", 1)[-1]
            l = b["l"]["value"]
            # ja 優先(後勝ち回避: ja が来たら上書き、enは未設定時のみ)
            if qid not in lab or _is_ja(l):
                lab[qid] = l
        for aid, v in out.items():
            if v and v["qid"] in lab and not v.get("label"):
                v["label"] = lab[v["qid"]]
        OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        print(f"  label batch {min(bi+BATCH,len(qids)):,}/{len(qids):,}")
        time.sleep(SLEEP)
    print("★ラベル付与完了")


def _is_ja(s):
    return any("぀" <= c <= "ヿ" or "一" <= c <= "鿿" for c in s)


if __name__ == "__main__":
    main()
