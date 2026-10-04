#!/usr/bin/env python3
"""著者名のリスト → 読み(カタカナ)を根拠付きで引く。 seed には書かない(表に出すだけ)。

2026-10-04(巻書誌の役割で原作者を足した時に、読みの無い人が出たため新設)。 引く順:
  ① MADB 作者台帳 metadata504 の schema:name の ja-hrkt(公式ヨミ)
  ② NDL 典拠(ndla 直リンク: metadata504 の ma:ndla / DB mangaka.qid の "ndl:…")→ ndl:transcription ja-Kana
     ★NDL は 1.2秒/req([[ndl_access_rate_method]])。 取得結果は .cache/author-yomi-ndl-cache.json に貯める(再開可)。
  どちらも無い人 = 空(捏造しない)。
使い方: python scripts/_resolve-author-yomi.py names.json out.tsv
  out.tsv = name / kana / source / ndla。 確かめてから data/seeds/author-yomi.yml へ純粋追加する。
"""
import html, json, os, re, sqlite3, sys, time, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".cache", "author-yomi-ndl-cache.json")


def clean_yomi(raw: str) -> str:
    # "タカハシ, ルミコ, 1957-" → "タカハシルミコ"(日付/数字/latin部は捨て、かな部のみ連結)。 _fetch-author-yomi-ndl.py と同じ規則
    keep = []
    for p in (x.strip() for x in raw.split(",")):
        if re.search(r"\d", p):
            continue
        if re.search(r"[ァ-ヶーぁ-ん]", p):
            keep.append(re.sub(r"[\s　]", "", p))
    return "".join(keep)


def fetch_ndl(eid: str) -> str:
    url = "https://id.ndl.go.jp/auth/ndlna/%s.rdf" % eid
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (MANGAL author-yomi)"})
    x = html.unescape(urllib.request.urlopen(req, timeout=25).read().decode("utf-8"))
    m = re.search(r'<ndl:transcription xml:lang="ja-Kana">(.*?)</ndl:transcription>', x, re.S)
    return clean_yomi(m.group(1)) if m else ""


def main():
    names = json.load(open(sys.argv[1], encoding="utf-8"))
    out_path = sys.argv[2]
    g = json.load(open(os.path.join(ROOT, ".cache", "madb", "metadata504.json"), encoding="utf-8"))
    rows = g.get("@graph", g) if isinstance(g, dict) else g
    by_name = {}
    for r in rows:
        nm = r.get("schema:name")
        lst = nm if isinstance(nm, list) else [nm]
        plain = [x for x in lst if isinstance(x, str)]
        hr = [x.get("@value") for x in lst if isinstance(x, dict) and x.get("@language") == "ja-hrkt"]
        for p in set(plain + [r.get("rdfs:label")] if r.get("rdfs:label") else plain):
            if p:
                by_name.setdefault(p, []).append({"kana": hr[0] if hr else "", "ndla": r.get("ma:ndla") or ""})
    con = sqlite3.connect(os.path.join(ROOT, ".cache", "db-v2.sqlite"))
    db_ndl = {}
    for nm, q in con.execute("SELECT name, qid FROM mangaka WHERE qid LIKE 'ndl:%'"):
        db_ndl.setdefault(nm, q.split(":", 1)[1])
    cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
    res = []
    n_ndl = 0
    for nm in names:
        cands = by_name.get(nm, [])
        kanas = {re.sub(r"[\s　]", "", c["kana"]) for c in cands if c["kana"]}
        if len(kanas) == 1:
            res.append((nm, kanas.pop(), "madb504", ""))
            continue
        if len(kanas) > 1:
            res.append((nm, "", "madb504-ambiguous:" + "/".join(sorted(kanas)), ""))
            continue
        ndlas = {c["ndla"].rstrip("/").split("/")[-1] for c in cands if c["ndla"]}
        if nm in db_ndl:
            ndlas.add(db_ndl[nm])
        if len(ndlas) != 1:
            res.append((nm, "", "none" if not ndlas else "ndla-ambiguous", "|".join(sorted(ndlas))))
            continue
        eid = ndlas.pop()
        if eid not in cache:
            try:
                time.sleep(1.2)
                cache[eid] = fetch_ndl(eid)
            except Exception as e:  # 取れない時は空のまま(次回再試行)
                print(f"  NDL失敗 {nm} {eid}: {e}", flush=True)
                res.append((nm, "", "ndl-error", eid))
                continue
            n_ndl += 1
            if n_ndl % 25 == 0:
                json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
                print(f"  NDL {n_ndl}件…", flush=True)
        res.append((nm, cache[eid], "ndl" if cache[eid] else "ndl-noyomi", eid))
    json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("name\tkana\tsource\tndla\n")
        for r in res:
            f.write("\t".join(r) + "\n")
    from collections import Counter
    c = Counter(r[2].split(":")[0] for r in res)
    print(f"読み: {sum(1 for r in res if r[1])}/{len(res)} 取得  内訳 {dict(c)}  NDL問い合わせ {n_ndl}")


if __name__ == "__main__":
    main()
