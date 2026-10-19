"""作品(work)の Wikidata QID を AniList漫画ID(P8731)経由で一意取得。

★慎重設計:
- 結合キー = anilist_id(既照合済)→ 作品名ファジーマッチ不要 = 誤join ゼロ
- Wikidata SPARQL に VALUES で一括問い合わせ(400/batch)
- 礼儀: User-Agent明示・batch間 sleep・429/5xx は指数backoffで retry
- 中断再開可: .cache/work-qid-map.json に anilist_id→qid を逐次保存
- 純粋追加レイヤー: 種1/種2/種3 不変。 promote が enrich として作品QIDを付与

★月次蒸留の intake 段 workqid(2026-10-19〜)= `--refresh --soft` で毎月全件取り直す。
  既定の再開モードは「該当なし {}」を二度と聞かないので、 後から Wikidata に項目ができた作品
  (新作の多く)が永久に拾えない。 --refresh は全 anilist_id を聞き直し、 最後に一括で差し替える
  (途中で落ちても前回の map は無傷・激減なら書かない)。
- --soft = QLever 不通・激減でも exit 0(前回の map のまま。 intake を止めない)。
  取り直せなかった月は _monthly-postflight.py が「他言語名の出所が古い」で FAIL にする。

出力: .cache/work-qid-map.json = {anilist_id(str): {"qid": "Q...", "label": "..."}}

  python scripts/_fetch-work-qid.py                    # 未取得の anilist_id だけ(再開)
  python scripts/_fetch-work-qid.py --refresh [--soft]  # 全件取り直し(月次)
"""
import datetime, json, os, shutil, sys, time, urllib.parse, urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
ENRICH = ROOT / ".cache" / "anilist-enrich-map.json"
OUT = ROOT / ".cache" / "work-qid-map.json"
# ★WDQS(query.wikidata.org)は障害中で1req/分。 QLever(独立・高速)を使う。
ENDPOINT = "https://qlever.dev/api/wikidata"
UA = "MANGAL-research/1.0 (https://mangal.shuichi0725.workers.dev; shuichi0725@gmail.com)"
BATCH = 400
SLEEP = 0.5
SHRINK_GUARD = 0.95   # 取り直しで作品QIDがこれ未満に減ったら書かない(QLever 側の不調を疑う)
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


def _save(out):
    tmp = OUT.with_name(OUT.name + ".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, OUT)


def fetch(refresh: bool):
    m = json.load(ENRICH.open(encoding="utf-8"))
    ids = sorted({str(v["anilist_id"]) for v in m.values()
                  if isinstance(v, dict) and v.get("anilist_id")})
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if refresh:
        # 全件聞き直す。 enrich map から外れた anilist_id の既存行は残す(照合ゲート等が引くため)
        idset = set(ids)
        out = {k: v for k, v in old.items() if k not in idset}
        todo = ids
    else:
        out = old
        todo = [i for i in ids if i not in out]   # 既取得(該当なしも空dictで記録)は skip → 再開可
    print(f"全 anilist_id: {len(ids):,} / 既取得: {len(old):,} / 問い合わせ: {len(todo):,}"
          + ("(★全件取り直し)" if refresh else ""))
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
            v = found.get(i, {})  # 該当なしは {} で記録
            prev = old.get(i) or {}
            if v and prev.get("qid") == v["qid"] and prev.get("label"):
                v["label"] = prev["label"]           # 同じQIDならラベルを引き継ぐ(聞き直さない)
            out[i] = v
        hit += len(found)
        if not refresh:
            _save(out)
        done = min(bi + BATCH, len(todo))
        if not refresh or done == len(todo) or (bi // BATCH) % 20 == 0:
            print(f"  batch {done:,}/{len(todo):,}  この回 {len(found)}件ヒット  累計ヒット {hit:,}")
        time.sleep(SLEEP)
    final_hit = sum(1 for v in out.values() if v)
    print(f"\n★QID取得完了: {len(out):,} 問い合わせ済 / 作品QID {final_hit:,}件")

    if refresh:
        old_hit = sum(1 for v in old.values() if v)
        if final_hit < old_hit * SHRINK_GUARD:
            raise RuntimeError(f"作品QIDが激減 {old_hit:,} → {final_hit:,}(QLever 側の不調を疑う)= 書かない")
        gained = sum(1 for k, v in out.items() if v and not (old.get(k) or {}))
        lost = sum(1 for k, v in old.items() if v and not (out.get(k) or {}))
        changed = sum(1 for k, v in out.items() if v and (old.get(k) or {}).get("qid") not in (None, v["qid"]))
        print(f"  前回比: 新たにQID +{gained:,} / 外れた -{lost:,} / QIDが変わった {changed:,}")

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
        if not refresh:
            _save(out)
        print(f"  label batch {min(bi+BATCH,len(qids)):,}/{len(qids):,}")
        time.sleep(SLEEP)
    print("★ラベル付与完了")

    if refresh:
        bak = OUT.with_name(OUT.name + f".bak-{datetime.date.today():%Y%m%d}")
        if OUT.exists() and not bak.exists():
            shutil.copy2(OUT, bak)
            print(f"  退避: {bak.name}")
        _save(out)
        print(f"  書込: {OUT.relative_to(ROOT)}")


def _is_ja(s):
    return any("぀" <= c <= "ヿ" or "一" <= c <= "鿿" for c in s)


def main():
    refresh = "--refresh" in sys.argv
    try:
        fetch(refresh)
    except Exception as e:
        if "--soft" not in sys.argv:
            raise
        print(f"\n★作品QIDを取り直せなかった(前回の {OUT.name} のまま続行): {e}")
        print("  直ったら: python scripts/intake.py --run --stages workqid,worklabels(頁へは次の promote で入る)")


if __name__ == "__main__":
    main()
