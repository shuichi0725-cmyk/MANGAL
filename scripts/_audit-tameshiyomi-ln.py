# -*- coding: utf-8 -*-
"""試し読みアンカーのラノベ/小説混入検査 (2026-08-20 領民0人型=ユーザ発見)。

型: ラノベ原作コミカライズ頁で、BookLive検索が**小説版**のtitle_idを拾い、試し読みが
ラノベになる(領民0人スタートの辺境領主様=556239(ラノベ)→正=621456(コミカライズ))。

検査 = 危険集合(アンカー済み∩原作クレジット持ち頁)の各title_idについて、BookLive商品頁の
JSON-LD category/genre を読み、ライトノベル/文芸/小説ならflag。
- 台帳 = .cache/tameshiyomi/ln-audit.jsonl (title_id単位・再開可能・campaign後の再実行は差分だけ)
- 出力 = docs/production-diagnostics/tameshiyomi-ln-anchors.tsv
- レート 1.3秒/req。是正はflagを見て別途(検索し直し=作画者クエリ+category=マンガ検証)。
"""
import glob
import io
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, ".cache", "tameshiyomi", "ln-audit.jsonl")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "tameshiyomi-ln-anchors.tsv")
NOVEL_CAT = re.compile(r"ライトノベル|ラノベ|文芸|小説|BLノベル|TLノベル")


def category_of(tid: str):
    url = f"https://booklive.jp/product/index/title_id/{tid}/vol_no/001"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    cat = re.search(r'"category":\s*"([^"]+)"', html)
    gen = re.search(r'"genre":\s*"([^"]+)"', html)
    t = re.search(r'property="og:title" content="([^"|]+)', html)
    return ((cat.group(1) if cat else "") + "/" + (gen.group(1) if gen else ""),
            t.group(1).strip() if t else "")


def main() -> None:
    anchors = {}
    for line in io.open(os.path.join(ROOT, "data", "seeds", "tameshiyomi-booklive.jsonl"), encoding="utf-8"):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("title_id"):
            anchors[r["slug"]] = r["title_id"]
    pat = re.compile(r"(?m)^original_authors:\n- name")
    risk = []
    for f in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
        t = io.open(f, encoding="utf-8").read()
        m = re.search(r"(?m)^slug: (.+)", t)
        slug = m.group(1).strip() if m else ""
        if slug in anchors and pat.search(t):
            risk.append((slug, anchors[slug]))
    checked = {}
    if os.path.exists(LEDGER):
        for line in io.open(LEDGER, encoding="utf-8"):
            try:
                r = json.loads(line)
                checked[r["tid"]] = r
            except Exception:
                pass
    todo = [(s, t) for s, t in risk if t not in checked]
    print(f"危険集合 {len(risk)} / 検査済 {len(risk) - len(todo)} / 残 {len(todo)}", flush=True)
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    # ★8並列(2026-08-20 ユーザ「長くない？」): expandの8並列HEADと同じ相手(BookLive CDN)の
    #   軽いGETなので並列可。90分→10分台。失敗はfailカウントのみ(台帳未記載=次回再試行)。
    from concurrent.futures import ThreadPoolExecutor

    def probe(item):
        slug, tid = item
        try:
            catgen, ptitle = category_of(tid)
            return slug, tid, catgen, ptitle
        except Exception as e:
            return slug, tid, None, type(e).__name__

    fails = 0
    with io.open(LEDGER, "a", encoding="utf-8", newline="\n") as w, \
            ThreadPoolExecutor(max_workers=8) as pool:
        for i, (slug, tid, catgen, ptitle) in enumerate(pool.map(probe, todo)):
            if catgen is None:
                fails += 1
                print(f"  ERR {slug} {ptitle}", flush=True)
                continue
            w.write(json.dumps({"tid": tid, "slug": slug, "cat": catgen, "ptitle": ptitle,
                                "at": time.strftime("%Y-%m-%d")}, ensure_ascii=False) + "\n")
            w.flush()
            if (i + 1) % 500 == 0:
                print(f"  {i + 1}/{len(todo)}", flush=True)
    if fails:
        print(f"取得失敗 {fails}(台帳未記載=再実行で再試行)", flush=True)
    # 集計(全台帳から)
    flagged = []
    for line in io.open(LEDGER, encoding="utf-8"):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if NOVEL_CAT.search(r.get("cat") or ""):
            flagged.append(r)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as w:
        w.write("slug\ttitle_id\tカテゴリ\t商品題\n")
        for r in sorted(flagged, key=lambda r: r["slug"]):
            w.write(f"{r['slug']}\t{r['tid']}\t{r['cat']}\t{r['ptitle']}\n")
    print(f"flag(ラノベ/小説アンカー): {len(flagged)} → {OUT}")


if __name__ == "__main__":
    main()
