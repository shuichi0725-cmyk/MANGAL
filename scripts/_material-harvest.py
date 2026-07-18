#!/usr/bin/env python3
"""素材ハーベスト (= skill material-harvest の実行体。2026-07-17 新設)

アイドル運転の柱: 本番に書かず「素材」だけを収集する。生成/反映は各既存protocol
(enrich-catch-synopsis / completion-judge / 反映ゲート) が別途担う。

サブコマンド(全て再開可能・逐次追記・429/枠切れ即中断):
  triage       ローカルだけで worklist 構築(日付粗い巻 / catch,synopsis欠落頁 / QID有無)
  dates-local  楽天cache(delta+isbn)から発売日を精密化候補として収集(★prefix一致のみ/矛盾はhold)
  wiki-link    作品QID→jawiki記事名 (QLever一括)
  wiki-fetch   記事wikitextを取得+infobox抽出(掲載誌/連載期間/休載/巻数/受賞/アニメ化) [--limit N]
  awards       作者QID+作品QIDのP166(受賞)をQLever一括収集
  fish-residue wiki無し×caption無しの残差を魚(TinyFish)で収集(サイト台帳つき) [--limit N]

出力:
  .cache/enrich-material/           素材庫(worklist/wiki/awards/fish/簿記)
  data/seeds/release-date-fill.jsonl 発売日精密化候補(★promote結線はGO待ち=貯めるだけ)
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAT = os.path.join(ROOT, ".cache", "enrich-material")
V2 = os.path.join(ROOT, "data", "manga.v2")
QLEVER = "https://qlever.dev/api/wikidata"
UA = "MANGAL-material-harvest/1.0 (contact: shuichi0725@gmail.com)"
WIKI_API = "https://ja.wikipedia.org/w/api.php"
DATE_SEED = os.path.join(ROOT, "data", "seeds", "release-date-fill.jsonl")

os.makedirs(MAT, exist_ok=True)


def _jsonl_append(path, rows):
    with io.open(path, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _jsonl_load(path):
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in io.open(path, encoding="utf-8") if l.strip()]


def _yload(path):
    import yaml
    with io.open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------- triage ----------------

def cmd_triage(a):
    """manga.v2 を1パスして worklist 3本を作る(毎回作り直し=冪等)。"""
    import glob
    _wq = os.path.join(ROOT, ".cache", "work-qid-map.json")
    global _WORK_QID
    _WORK_QID = json.load(io.open(_wq, encoding="utf-8")) if os.path.exists(_wq) else {}
    if not _WORK_QID:
        print("★warn: work-qid-map.json 無し = wiki worklist は空になる", file=sys.stderr)
    dates, enrich, wiki = [], [], []
    tot = 0
    for p in sorted(glob.glob(os.path.join(V2, "*.yml"))):
        tot += 1
        d = _yload(p)
        slug = d.get("slug") or os.path.basename(p)[:-4]
        # 日付が粗い巻 (= null or YYYY or YYYY-MM)
        coarse = []
        for e in d.get("editions") or []:
            pools = [e.get("volumes") or []] + [v.get("volumes") or [] for v in (e.get("versions") or [])]
            for pool in pools:
                for v in pool:
                    rd = v.get("release_date")
                    if v.get("isbn13") and (not rd or len(str(rd)) < 10):
                        coarse.append({"isbn": str(v["isbn13"]), "cur": rd})
        if coarse:
            dates.append({"slug": slug, "vols": coarse})
        # enrich 欠落
        missing = [k for k in ("catch", "synopsis") if not d.get(k)]
        if missing:
            enrich.append({"slug": slug, "title": d.get("title"),
                           "authors": [x.get("name") for x in d.get("authors") or []],
                           "publisher": d.get("publisher"),
                           "isbns": [str(v.get("isbn13")) for e in d.get("editions") or []
                                     for v in e.get("volumes") or [] if v.get("isbn13")][:3],
                           "missing": missing})
        # wiki 結線候補 (★頁の wikidata_qid は作者QID名前空間=使わない[2026-07-17実測で44k頁全て作者QID]。
        #   作品QIDは .cache/work-qid-map.json(anilist_id キー・P8731由来) から引く)
        aid = d.get("anilist_id")
        wq = (_WORK_QID.get(str(aid)) or {}).get("qid") if aid is not None else None
        if wq:
            wiki.append({"slug": slug, "anilist_id": aid, "qid": wq})
    for name, rows in (("dates", dates), ("enrich", enrich), ("wiki", wiki)):
        path = os.path.join(MAT, f"worklist-{name}.jsonl")
        with io.open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_isbn = sum(len(x["vols"]) for x in dates)
    print(f"triage: 全{tot}頁 → 日付粗い頁{len(dates)}(対象ISBN {n_isbn:,}) / enrich欠落{len(enrich)} / QID有{len(wiki)}")


# ---------------- dates-local ----------------

_DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(?:(\d{1,2})日)?")


def _parse_sales(s):
    m = _DATE_RE.search(str(s or ""))
    if not m:
        return None
    y, mo, dy = m.group(1), m.group(2), m.group(3)
    if not dy:
        return f"{y}-{int(mo):02d}"
    return f"{y}-{int(mo):02d}-{int(dy):02d}"


def cmd_dates_local(a):
    """楽天cache 2本を1パスし、対象ISBNの salesDate を精密化候補に。
    ★ゲート: 新値が年月日フルで、既存が空 or 新値のprefix の時だけ候補化。矛盾は hold。"""
    targets = {}
    for row in _jsonl_load(os.path.join(MAT, "worklist-dates.jsonl")):
        for v in row["vols"]:
            targets[v["isbn"]] = {"slug": row["slug"], "cur": v["cur"]}
    print(f"対象ISBN: {len(targets):,}")
    done = {json.loads(l)["isbn"] for l in io.open(DATE_SEED, encoding="utf-8")} if os.path.exists(DATE_SEED) else set()
    holds_path = os.path.join(MAT, "dates-conflict-holds.tsv")
    cand, holds, seen = [], [], set()
    for path, key in ((os.path.join(ROOT, ".cache", "rakuten-isbn-delta.jsonl"), "item"),
                      (os.path.join(ROOT, ".cache", "rakuten-isbn.jsonl"), "item")):
        if not os.path.exists(path):
            continue
        with io.open(path, encoding="utf-8") as f:
            for l in f:
                try:
                    d = json.loads(l)
                except Exception:
                    continue
                isbn = str(d.get("isbn") or "")
                if isbn not in targets or isbn in done or isbn in seen:
                    continue
                it = d.get(key) or d
                new = _parse_sales(it.get("salesDate"))
                if not new or len(new) < 10:
                    continue  # 年月日フルで取れた時だけ
                cur = targets[isbn]["cur"]
                seen.add(isbn)
                if not cur or new.startswith(str(cur)):
                    cand.append({"isbn": isbn, "slug": targets[isbn]["slug"], "before": cur,
                                 "date": new, "source": os.path.basename(path),
                                 "collected_at": time.strftime("%Y-%m-%d")})
                else:
                    holds.append(f"{targets[isbn]['slug']}\t{isbn}\t{cur}\t{new}\t{os.path.basename(path)}")
    _jsonl_append(DATE_SEED, cand)
    if holds:
        with io.open(holds_path, "a", encoding="utf-8") as f:
            f.write("\n".join(holds) + "\n")
    print(f"dates-local: 候補+{len(cand):,}(累計{len(done)+len(cand):,}) / 矛盾hold {len(holds)} → {os.path.basename(holds_path)}")
    print(f"  ★seedは収集のみ(promote結線=GO待ち): {DATE_SEED}")


# ---------------- QLever 共通 ----------------

def _qlever(q):
    data = urllib.parse.urlencode({"query": q}).encode()
    req = urllib.request.Request(QLEVER, data=data, headers={
        "User-Agent": UA, "Accept": "application/sparql-results+json",
        "Content-Type": "application/x-www-form-urlencoded"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))["results"]["bindings"]
        except Exception as e:
            wait = 2 ** attempt + 1
            print(f"  qlever retry {attempt+1}/5 ({str(e)[:60]}) wait {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise SystemExit("QLever 5連続失敗 = 中断(再実行で再開)")


def _batches(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


# ---------------- wiki-link ----------------

def cmd_wiki_link(a):
    out = os.path.join(MAT, "wiki-links.jsonl")
    have = {r["qid"] for r in _jsonl_load(out)}
    rows = [r for r in _jsonl_load(os.path.join(MAT, "worklist-wiki.jsonl")) if r["qid"] not in have]
    qid2slug = {}
    for r in rows:
        qid2slug.setdefault(r["qid"], r["slug"])
    qids = sorted(qid2slug)
    print(f"wiki-link: 未解決QID {len(qids):,}")
    n_link = 0
    for i, b in enumerate(_batches(qids, 500)):
        vals = " ".join(f"wd:{q}" for q in b)
        q = f"""PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX schema: <http://schema.org/>
SELECT ?item ?article WHERE {{ VALUES ?item {{ {vals} }}
  ?article schema:about ?item ; schema:isPartOf <https://ja.wikipedia.org/> . }}"""
        got = {}
        for r in _qlever(q):
            qid = r["item"]["value"].rsplit("/", 1)[-1]
            got[qid] = urllib.parse.unquote(r["article"]["value"].rsplit("/wiki/", 1)[-1]).replace("_", " ")
        batch_rows = [{"qid": qq, "slug": qid2slug[qq], "article": got.get(qq)} for qq in b]
        _jsonl_append(out, batch_rows)
        n_link += sum(1 for x in batch_rows if x["article"])
        print(f"  batch {i+1}: 解決{sum(1 for x in batch_rows if x['article'])}/{len(b)}")
        time.sleep(1.0)
    print(f"wiki-link 完了: 今回リンク{n_link:,} → {out}")


# ---------------- wiki-fetch ----------------

_INFO_PATTERNS = {
    "magazine": re.compile(r"\|\s*掲載誌\s*=\s*(.+)"),
    "period": re.compile(r"\|\s*(?:連載期間|発表期間)\s*=\s*(.+)"),
    "volumes_total": re.compile(r"\|\s*巻数\s*=\s*(.+)"),
    "award": re.compile(r"\|\s*受賞\s*=\s*(.+)"),
}


def cmd_wiki_fetch(a):
    links = [r for r in _jsonl_load(os.path.join(MAT, "wiki-links.jsonl")) if r.get("article")]
    rawdir = os.path.join(MAT, "wiki")
    os.makedirs(rawdir, exist_ok=True)
    ext_path = os.path.join(MAT, "wiki-extract.jsonl")
    done = {r["slug"] for r in _jsonl_load(ext_path)}
    todo = [r for r in links if r["slug"] not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f"wiki-fetch: 残{len([r for r in links if r['slug'] not in done]):,} / 今回{len(todo):,} (0.8s/req)")
    # ★エラー方針(2026-07-18 改訂): 429/503=レート制限はバックオフ(60s→120s→240s)して続行、
    #   3連続バックオフ後も429なら「冷却待ち」を明示して中断。その他エラーは連続5(成功でリセット)で中断。
    #   旧実装の「累積5で即死」はアイドル運転が数分で止まる実害(2026-07-18朝=24件で停止)。
    n_err = 0
    n_backoff = 0
    for i, r in enumerate(todo):
        p = {"action": "parse", "page": r["article"], "prop": "wikitext", "format": "json",
             "formatversion": "2", "redirects": "1"}
        req = urllib.request.Request(WIKI_API + "?" + urllib.parse.urlencode(p), headers={"User-Agent": UA})
        try:
            d = json.load(urllib.request.urlopen(req, timeout=60))
            wt = (d.get("parse") or {}).get("wikitext") or ""
            n_err = 0
            n_backoff = 0
        except Exception as e:
            code = getattr(e, "code", None)
            if code in (429, 503):
                n_backoff += 1
                if n_backoff > 3:
                    print(f"★429/503が継続({r['article']}) = Wikipedia冷却待ち。1時間ほど空けて再実行(done集合で続きから)"); return
                wait = 60 * (2 ** (n_backoff - 1))
                print(f"  429/503 → {wait}s バックオフ({n_backoff}/3)"); time.sleep(wait); continue
            n_err += 1
            print(f"  err({n_err}/5) {r['article']}: {str(e)[:80]}")
            if n_err >= 5:
                print("★連続エラー5 = 中断(再実行で再開)"); return
            time.sleep(3); continue
        io.open(os.path.join(rawdir, r["slug"] + ".wiki.txt"), "w", encoding="utf-8").write(wt)
        ex = {"slug": r["slug"], "article": r["article"]}
        for k, pat in _INFO_PATTERNS.items():
            m = pat.search(wt)
            if m:
                ex[k] = m.group(1).strip()[:300]
        ex["hiatus_mention"] = bool(re.search(r"休載", wt[:20000]))
        _jsonl_append(ext_path, [ex])
        if (i + 1) % 100 == 0:
            print(f"  ...{i+1}/{len(todo)}")
        time.sleep(0.8)
    print(f"wiki-fetch: 今回{len(todo)}件(err {n_err}) → {ext_path}")


# ---------------- awards ----------------

def _p166(qids, tag, out):
    have = {r["qid"] for r in _jsonl_load(out)}
    qids = [q for q in qids if q not in have]
    print(f"awards[{tag}]: 未収集QID {len(qids):,}")
    for i, b in enumerate(_batches(qids, 500)):
        vals = " ".join(f"wd:{q}" for q in b)
        q = f"""PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?item ?award ?ja ?en ?time WHERE {{ VALUES ?item {{ {vals} }}
  ?item p:P166 ?st . ?st ps:P166 ?award .
  OPTIONAL {{ ?st pq:P585 ?time }}
  OPTIONAL {{ ?award rdfs:label ?ja FILTER(LANG(?ja)="ja") }}
  OPTIONAL {{ ?award rdfs:label ?en FILTER(LANG(?en)="en") }} }}"""
        got = {}
        for r in _qlever(q):
            qid = r["item"]["value"].rsplit("/", 1)[-1]
            got.setdefault(qid, []).append({
                "award_qid": r["award"]["value"].rsplit("/", 1)[-1],
                "ja": (r.get("ja") or {}).get("value"), "en": (r.get("en") or {}).get("value"),
                "time": ((r.get("time") or {}).get("value") or "")[:10] or None})
        _jsonl_append(out, [{"qid": qq, "awards": got.get(qq, [])} for qq in b])
        print(f"  batch {i+1}: 受賞持ち {len(got)}/{len(b)}")
        time.sleep(1.0)


def cmd_awards(a):
    author_qids = sorted({r["qid"] for r in csv.DictReader(io.open(os.path.join(ROOT, "data", "seed", "mangaka.csv"), encoding="utf-8")) if r.get("qid", "").startswith("Q")})
    _p166(author_qids, "作者", os.path.join(MAT, "awards-authors.jsonl"))
    work_qids = sorted({r["qid"] for r in _jsonl_load(os.path.join(MAT, "worklist-wiki.jsonl"))})
    _p166(work_qids, "作品", os.path.join(MAT, "awards-works.jsonl"))
    for tag, f in (("作者", "awards-authors.jsonl"), ("作品", "awards-works.jsonl")):
        rows = _jsonl_load(os.path.join(MAT, f))
        n = sum(1 for r in rows if r["awards"])
        print(f"awards[{tag}]: 受賞持ち {n:,}/{len(rows):,}")


# ---------------- fish-residue ----------------

def cmd_fish_residue(a):
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from _tinyfish import search as tf_search, fetch as tf_fetch
    ledger_p = os.path.join(MAT, "fish-site-ledger.json")
    ledger = json.load(io.open(ledger_p, encoding="utf-8")) if os.path.exists(ledger_p) else {}
    # ★fetchしないドメイン: Amazon=PA-APIのみ合法(既裁定) / 楽天=照会は_lookup.py経由(skill external-data-access)
    DENY = ("amazon.co.jp", "amazon.com", "rakuten.co.jp")
    linked = {r["slug"] for r in _jsonl_load(os.path.join(MAT, "wiki-links.jsonl")) if r.get("article")}
    # caption有無: delta cacheを引かず、素材庫に無い×wiki無しをそのまま残差扱い(v1)
    out = os.path.join(MAT, "fish-material.jsonl")
    done = {r["slug"] for r in _jsonl_load(out)}
    todo = [r for r in _jsonl_load(os.path.join(MAT, "worklist-enrich.jsonl"))
            if r["slug"] not in linked and r["slug"] not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f"fish-residue: 対象{len(todo)} (wiki無しenrich欠落。--limitで刻む)")
    for r in todo:
        qy = f"{r['title']} {' '.join(r['authors'][:2])} 漫画"
        try:
            sr = tf_search(qy)
        except SystemExit:
            raise
        except Exception as e:
            print(f"★search失敗({str(e)[:60]}) = 中断"); return
        results = (sr or {}).get("results") or []
        pick = []
        for x in results[:5]:
            u = x.get("url", "")
            parsed = urllib.parse.urlparse(u)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                continue  # 検索結果に混じる不正URL(相対パス等)はfetch対象から除外
            dom = parsed.netloc
            if ledger.get(dom) == "blocked" or any(dom.endswith(d) for d in DENY):
                continue
            pick.append(u)
            if len(pick) >= 2:
                break
        texts = []
        if pick:
            try:
                fr = tf_fetch(pick)
            except SystemExit as e:
                fr = {"results": [], "errors": [{"url": u, "error": str(e)[:80]} for u in pick]}
            except Exception as e:
                fr = {"results": [], "errors": [{"url": u, "error": str(e)[:80]} for u in pick]}
            for ok in (fr or {}).get("results") or []:
                dom = urllib.parse.urlparse(ok.get("url", "")).netloc
                body = (ok.get("text") or ok.get("markdown") or "")[:4000]
                # 空文=取れていない(JS重等)。okにせずempty印(=blockedとは区別・再挑戦余地を残す)
                ledger[dom] = "ok" if body.strip() else ledger.get(dom, "empty")
                if body.strip():
                    texts.append({"url": ok.get("url"), "text": body})
            for er in (fr or {}).get("errors") or []:
                dom = urllib.parse.urlparse(er.get("url", "")).netloc
                ledger.setdefault(dom, "blocked")
        _jsonl_append(out, [{"slug": r["slug"], "title": r["title"], "query": qy,
                             "snippets": [{"url": x.get("url"), "snippet": x.get("snippet")} for x in results[:5]],
                             "pages": texts, "at": time.strftime("%Y-%m-%d")}])
        json.dump(ledger, io.open(ledger_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        time.sleep(1.0)
    print(f"fish-residue: +{len(todo)} → {out} / サイト台帳 {len(ledger)}ドメイン")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["triage", "dates-local", "wiki-link", "wiki-fetch", "awards", "fish-residue"])
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    {"triage": cmd_triage, "dates-local": cmd_dates_local, "wiki-link": cmd_wiki_link,
     "wiki-fetch": cmd_wiki_fetch, "awards": cmd_awards, "fish-residue": cmd_fish_residue}[a.cmd](a)


if __name__ == "__main__":
    main()
