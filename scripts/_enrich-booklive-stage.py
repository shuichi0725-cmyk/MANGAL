# -*- coding: utf-8 -*-
"""BookLive紹介文(+楽天caption)を enrich バッチへステージング (= 2026-08-27 新設)。

背景: 楽天caption鉱脈が枯れた層に対し BookLive商品頁の1巻紹介文が第2材料源になった
  ([[enrich-catch-synopsis]] skill Step1)。ハーベスト出力 .cache/booklive-desc.jsonl を
  applier(_apply-enrich-batch.py)が読める材料バッチ形式へ落とす。
  ★丸写し8gram検査は材料バッチのcaptionsを見るので、BookLive desc も caption として入れる。

出力: .cache/enrich-batches/batch-<START+i>.json  = {"kind":"full","items":[...]}
      .cache/enrich-batches/digest-<N>.txt        = 生成用の人間可読ダイジェスト

  python scripts/_enrich-booklive-stage.py --start 9301 --size 50 [--limit N]
"""
import argparse, io, json, os, sys
import yaml
try: from yaml import CSafeLoader as L
except Exception: from yaml import SafeLoader as L

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BATCHDIR = os.path.join(ROOT, ".cache", "enrich-batches")


def n_vols(d):
    n = 0
    for e in (d.get("editions") or []):
        n = max(n, len(e.get("volumes") or []))
    return n


def load_page(slug):
    p = os.path.join(ROOT, "data", "manga.v2", slug + ".yml")
    if not os.path.exists(p):
        return None
    try:
        return yaml.load(io.open(p, encoding="utf-8"), Loader=L) or {}
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=9301)
    ap.add_argument("--size", type=int, default=50)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--minlen", type=int, default=60)
    ap.add_argument("--rakuten", default=os.path.join(ROOT, ".cache", "enrich", "materials.jsonl"),
                    help="楽天材料(_enrich-captions.py 出力)も併合する")
    a = ap.parse_args()

    items, seen = [], set()

    # 1) 楽天材料(1〜2巻に minlen 以上のcaptionがある頁のみ=skillの「1-2巻の範囲」規律)
    if a.rakuten and os.path.exists(a.rakuten):
        for ln in io.open(a.rakuten, encoding="utf-8"):
            r = json.loads(ln)
            caps = [c for c in (r.get("captions") or []) if len(c.get("caption") or "") >= a.minlen]
            if not any(int(c.get("vol") or 99) <= 2 for c in caps):
                continue
            s = r["slug"]
            if s in seen: continue
            d = load_page(s)
            if d is None: continue
            if (d.get("catch") or "").strip() and (d.get("synopsis") or "").strip(): continue
            seen.add(s)
            items.append({"slug": s, "title": d.get("title"), "authors": d.get("authors") or [],
                          "genres_now": list(d.get("genres") or []), "demographic": d.get("demographic"),
                          "n_vols": n_vols(d), "src": "rakuten",
                          "captions": [{"vol": c.get("vol"), "caption": c.get("caption")} for c in caps]})

    # 2) BookLive紹介文(1巻基点・出版社公式)
    blp = os.path.join(ROOT, ".cache", "booklive-desc.jsonl")
    for ln in io.open(blp, encoding="utf-8"):
        r = json.loads(ln)
        s, desc = r["slug"], (r.get("desc") or "").strip()
        if s in seen or len(desc) < a.minlen: continue
        d = load_page(s)
        if d is None: continue
        if (d.get("catch") or "").strip() and (d.get("synopsis") or "").strip(): continue
        seen.add(s)
        items.append({"slug": s, "title": d.get("title"), "authors": d.get("authors") or [],
                      "genres_now": list(d.get("genres") or []), "demographic": d.get("demographic"),
                      "n_vols": n_vols(d), "src": "booklive",
                      "captions": [{"vol": 1, "caption": desc}]})

    if a.limit: items = items[:a.limit]
    os.makedirs(BATCHDIR, exist_ok=True)
    n = 0
    for i in range(0, len(items), a.size):
        num = a.start + n
        chunk = items[i:i + a.size]
        json.dump({"kind": "full", "items": chunk},
                  io.open(os.path.join(BATCHDIR, f"batch-{num}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        n += 1
    print(f"staged {len(items)} items -> batch-{a.start}..{a.start + n - 1} ({n} batches, size={a.size})")
    from collections import Counter
    print("  src:", dict(Counter(x["src"] for x in items)))


if __name__ == "__main__":
    main()
