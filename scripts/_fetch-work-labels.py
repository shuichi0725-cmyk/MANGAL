"""作品(work)QID の 言語別ラベル(rdfs:label)を Wikidata から一括取得 = 他言語名の一次ソース。

★2026-10-19 らんま1/2「他言語がハングルしかない」報告で新設。
  AniList synonyms は言語タグが無く(韓/中/タイ/英別名/ローマ字/日本語別名が混在)、
  英題(title.english)も synonyms に入らない。 Wikidata は 1言語1ラベルで言語コード付き。

- 入力 = .cache/work-qid-map.json(_fetch-work-qid.py = AniList ID P8731 経由の一意join)
- ★rdfs:label のみ(skos:altLabel は人物名・旧題・誤記が混じるので使わない)
- QLever(独立・高速・VALUES一括)。 400 QID/batch・batch間 sleep・retry
- 中断再開可: 既取得 QID は skip
- 純粋追加レイヤー: 種1/種2/種3 不変。 promote が work_wikidata_qid 経由で join

★月次蒸留の intake 段 worklabels(2026-10-19〜)= `--refresh --soft` で毎月全件取り直す
  (新作のQIDに加え、 既存作品に後から足された言語・直されたラベルも拾う)。
  --refresh は最後に一括で差し替える(途中で落ちても前回の labels は無傷・激減なら書かない)。
- --soft = QLever 不通・激減でも exit 0(前回の labels のまま。 intake を止めない)。
  取り直せなかった月は _monthly-postflight.py が「他言語名の出所が古い」で FAIL にする。

出力: .cache/work-labels.json = {qid: {lang: label}}

  python scripts/_fetch-work-labels.py                    # 未取得の QID だけ(再開)
  python scripts/_fetch-work-labels.py --refresh [--soft]  # 全件取り直し(月次)
"""
import datetime, json, os, shutil, sys, time, urllib.parse, urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
QMAP = ROOT / ".cache" / "work-qid-map.json"
OUT = ROOT / ".cache" / "work-labels.json"
ENDPOINT = "https://qlever.dev/api/wikidata"
UA = "MANGAL-research/1.0 (https://mangal.shuichi0725.workers.dev; shuichi0725@gmail.com)"
BATCH = 400
SLEEP = 0.5
SHRINK_GUARD = 0.95   # 取り直しでラベル総数がこれ未満に減ったら書かない(QLever 側の不調を疑う)
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


def _save(out):
    tmp = OUT.with_name(OUT.name + ".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, OUT)


def fetch(refresh: bool):
    qmap = json.loads(QMAP.read_text(encoding="utf-8"))
    qids = sorted({v["qid"] for v in qmap.values() if v and v.get("qid")})
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    out = {} if refresh else old
    todo = qids if refresh else [q for q in qids if q not in out]
    print(f"作品QID: {len(qids):,} / 既取得: {len(old):,} / 問い合わせ: {len(todo):,}"
          + ("(★全件取り直し)" if refresh else ""))
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
        if not refresh:
            _save(out)
        print(f"  batch {min(bi + BATCH, len(todo)):,}/{len(todo):,}  ラベル {len(rows):,}行")
        time.sleep(SLEEP)
    n_lab = sum(len(v) for v in out.values())
    print(f"★完了: QID {len(out):,} / ラベル {n_lab:,}(平均 {n_lab / max(1, len(out)):.1f}言語)")

    if refresh:
        n_old = sum(len(v) for v in old.values())
        if n_lab < n_old * SHRINK_GUARD:
            raise RuntimeError(f"ラベルが激減 {n_old:,} → {n_lab:,}(QLever 側の不調を疑う)= 書かない")
        new_q = sum(1 for q in out if q not in old)
        added = sum(1 for q, v in out.items() for lg in v if lg not in (old.get(q) or {}))
        changed = sum(1 for q, v in out.items() for lg, l in v.items() if (old.get(q) or {}).get(lg) not in (None, l))
        removed = sum(1 for q, v in old.items() if q in out for lg in v if lg not in out[q])
        print(f"  前回比: 新しい作品QID {new_q:,} / ラベル +{added:,} 足された・{changed:,} 直された・-{removed:,} 消えた")
        bak = OUT.with_name(OUT.name + f".bak-{datetime.date.today():%Y%m%d}")
        if OUT.exists() and not bak.exists():
            shutil.copy2(OUT, bak)
            print(f"  退避: {bak.name}")
        _save(out)
        print(f"  書込: {OUT.relative_to(ROOT)}")


def main():
    refresh = "--refresh" in sys.argv
    try:
        fetch(refresh)
    except Exception as e:
        if "--soft" not in sys.argv:
            raise
        print(f"\n★言語別ラベルを取り直せなかった(前回の {OUT.name} のまま続行): {e}")
        print("  直ったら: python scripts/intake.py --run --stages workqid,worklabels(頁へは次の promote で入る)")


if __name__ == "__main__":
    main()
