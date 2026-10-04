#!/usr/bin/env python3
"""手で巻を固定した頁(edition-overrides の editions / edition-canonical)に、後から出た紙の続巻が載っていないかを楽天で引く。

2026-10-05 発見(SHIORI EXPERIENCE): 8/7 の頁統合で edition-overrides が22巻で固定 → 23〜26巻(新刊)が永久に出ない。
月次の検出器 #27 第2部は「種2 に来た続巻」しか見ず、種2 にも楽天キャッシュにも無い新刊(=この型の本命)は拾えない。
→ 楽天を live で「題 + 次の巻番号」と引き、見つかれば次の番号も続けて引く(_lookup の作法=rakuten_live_retry)。
照合 = 題(正規化)一致 + 巻番号 + 著者のどれかが楽天の著者欄に在る + MANGAL のどの頁にも無い ISBN。 特装/限定/セット/BOX は外す。
報告のみ(seed は書かない)。 出力 = docs/production-diagnostics/frozen-page-new-volumes.tsv
使い方: python scripts/_audit-frozen-page-new-volumes.py [--limit N]
"""
import argparse, importlib.util, json, os, re, sys, unicodedata

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "frozen-page-new-volumes.tsv")
_argv, sys.argv = sys.argv, [sys.argv[0]]
_s = importlib.util.spec_from_file_location("lk", os.path.join(ROOT, "scripts", "_lookup.py"))
lk = importlib.util.module_from_spec(_s)
_s.loader.exec_module(lk)
sys.argv = _argv
ENV = lk._env()
NOISE = re.compile(r"特装|限定|セット|BOX|ボックス|ガイド|ファンブック|画集|小説|ノベル|アンソロジー|カレンダー")


def norm(s):
    s = unicodedata.normalize("NFKC", str(s or ""))
    return re.sub(r"[\s　〜~ー\-–—・･。、．，,.:：;；!！?？'’\"”「」『』【】\[\]（）()/／＋+＆&☆★♪]", "", s).lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    eo = json.load(open(os.path.join(ROOT, "data", "seeds", "edition-overrides.json"), encoding="utf-8"))
    pub2stem = {v: k for k, v in json.load(open(os.path.join(ROOT, ".cache", "prod-page-slugs.json"), encoding="utf-8")).items()}
    stems = {pub2stem.get(k, k): "overrides" for k, v in eo.items() if isinstance(v, dict) and v.get("editions")}
    for f in os.listdir(os.path.join(ROOT, "data", "seeds", "edition-canonical")):
        if f.endswith(".yml"):
            stems.setdefault(f[:-4], "canonical")
    isbn_idx = json.load(open(os.path.join(ROOT, ".cache", "isbn-page-index.json"), encoding="utf-8"))
    rows, n = [], 0
    items = sorted(stems.items())
    if a.limit:
        items = items[: a.limit]
    for stem, kind in items:
        fp = os.path.join(ROOT, "data", "manga.v2", stem + ".yml")
        if not os.path.exists(fp):
            continue
        d = yaml.safe_load(open(fp, encoding="utf-8")) or {}
        title = d.get("title") or ""
        nums = [v["number"] for e in d.get("editions") or [] for v in e.get("volumes") or [] if isinstance(v.get("number"), int)]
        if not nums or not title:
            continue
        authors = [norm(x.get("name")) for x in (d.get("authors") or []) + (d.get("original_authors") or []) if x.get("name")]
        nxt = max(nums) + 1
        n += 1
        while True:
            try:
                its = lk.rakuten_live_retry(ENV, title=f"{title} {nxt}", hits=30) or []
            except SystemExit:
                print("★楽天429で中断", flush=True)
                its, nxt = [], None
            hit = None
            for it in its:
                t = unicodedata.normalize("NFKC", it.get("title") or "")
                if NOISE.search(t) or not t:
                    continue
                # ★題の照合 = 巻番号を除いた題が頁題と一致(旧=「含む」で ルパン三世Y/物語日本の歴史/〜傑作選 を拾った 2026-10-05)
                mm = re.search(rf"^(.*?)[\s　]*(?:第)?[（(]?\s*{nxt}\s*[)）]?\s*(?:巻)?(?:[（(][^)）]*[)）])?\s*$", t)
                if not mm or norm(mm.group(1)) != norm(title):
                    continue
                if authors and not any(x and x in norm(it.get("author")) for x in authors):
                    continue
                isbn = str(it.get("isbn") or "")
                if not isbn or isbn in isbn_idx:
                    continue
                hit = (isbn, it.get("salesDate"), it.get("title"), it.get("seriesName"), it.get("publisherName"))
                break
            if not hit:
                break
            rows.append((kind, stem, title, max(nums), nxt, *hit))
            print(f"  [{kind}] {title} 頁最大{max(nums)} → {nxt}巻 {hit[0]} {hit[1]} {hit[2]}", flush=True)
            nxt += 1
        if nxt is None:
            break
        if n % 100 == 0:
            print(f"  …{n}/{len(items)} 頁(見つかった巻 {len(rows)})", flush=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("kind\tstem\ttitle\tpage_max\tvol\tisbn\tsalesDate\trakuten_title\tseries\tpublisher\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")
    print(f"完了: {n}頁を照会 / 載っていない紙の続巻 {len(rows)}巻・{len({r[1] for r in rows})}頁 → {OUT}", flush=True)


if __name__ == "__main__":
    main()
