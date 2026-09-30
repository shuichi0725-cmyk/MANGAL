# -*- coding: utf-8 -*-
"""1巻作品のキャッチ+ジャンル/要素見直し用バッチをステージング (= 2026-09-30 ユーザ裁定で新設)。

背景: 2026-07-14 裁定「1巻=ジャンルのみ」で、材料(楽天caption/巻説明/BookLive紹介文)が手元に
  在るのにキャッチが書かれていない1巻作品が 4,019 作あった。羅針盤は「書影+キャッチ」の作品しか
  載せない(app/lab/magic-shelf/compass.ts isEligible)ため、これらは一度も羅針盤に出ない。
  2026-09-30 ユーザ裁定「①一巻でもかけそうな物はキャッチを書きジャンル、要素を見直す」。

対象: 本番索引で 書影あり × キャッチなし × total_volumes<=1 × 材料(60字以上)が手元に在る頁。
材料: 楽天キャッシュ(rakuten-isbn.jsonl + -delta)の itemCaption / volume-desc-ja.jsonl の1巻 /
      .cache/booklive-desc.jsonl。 live照会はしない。
出力: .cache/enrich-batches/batch-<N>.json = {"kind":"catch1","items":[...]}(applierの丸写し検査が読む)
      .cache/enrich-batches/digest-<N>.txt  = 生成用ダイジェスト(現ジャンル/要素つき)

  python scripts/_enrich-1vol-stage.py --start 9700 --size 50
"""
import argparse, collections, io, json, os, sys
import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BATCHDIR = os.path.join(ROOT, ".cache", "enrich-batches")
MINLEN = 60


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=9700)
    ap.add_argument("--size", type=int, default=50)
    a = ap.parse_args()

    idx = json.load(io.open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    rows = [dict(zip(idx["f"], r)) for r in idx["d"]]
    cat = json.load(io.open(os.path.join(ROOT, "data", "manga-catch-index.json"), encoding="utf-8"))
    targets = [m for m in rows if m.get("cover") and not cat.get(m["slug"]) and (m.get("total_volumes") or 0) <= 1]

    # 公開slug -> SRC slug(manga.v2 のファイル名。catch seed は SRC slug で引かれる)
    ov = (yaml.safe_load(io.open(os.path.join(ROOT, "data", "seeds", "slug-overrides.yml"), encoding="utf-8")) or {}).get("overrides", {})
    pub2src = {v.get("slug"): k for k, v in ov.items() if isinstance(v, dict) and v.get("slug")}

    def src_of(pub):
        for s in (pub, pub2src.get(pub)):
            if s and os.path.exists(os.path.join(ROOT, "data", "manga.v2", s + ".yml")):
                return s
        return None

    ipi = json.load(io.open(os.path.join(ROOT, ".cache", "isbn-page-index.json"), encoding="utf-8"))
    page_isbns = collections.defaultdict(set)
    for i, ss in ipi.items():
        for s in ss:
            page_isbns[s].add(i)

    tmap = {}
    for m in targets:
        s = src_of(m["slug"])
        if s:
            tmap[m["slug"]] = (s, m)
    want = {}
    for pub, (s, _) in tmap.items():
        for i in page_isbns.get(pub, set()) | page_isbns.get(s, set()):
            want[i] = pub

    caps = collections.defaultdict(dict)  # pub -> {caption: isbn}
    for fn in ("rakuten-isbn.jsonl", "rakuten-isbn-delta.jsonl"):
        with io.open(os.path.join(ROOT, ".cache", fn), encoding="utf-8") as f:
            for line in f:
                if '"itemCaption": ""' in line:
                    continue
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                i = o.get("isbn")
                if i not in want:
                    continue
                c = " ".join(((o.get("item") or {}).get("itemCaption") or "").split())
                if len(c) >= MINLEN:
                    caps[want[i]].setdefault(c, i)

    vd = collections.defaultdict(list)
    for ln in io.open(os.path.join(ROOT, "data", "seeds", "volume-desc-ja.jsonl"), encoding="utf-8"):
        o = json.loads(ln)
        if str(o.get("vol")) in ("1", "None") and len(o.get("desc") or "") >= MINLEN:
            vd[o["slug"]].append(o["desc"])
    bl = {}
    for ln in io.open(os.path.join(ROOT, ".cache", "booklive-desc.jsonl"), encoding="utf-8"):
        o = json.loads(ln)
        if len(o.get("desc") or "") >= MINLEN:
            bl[o["slug"]] = o["desc"]

    items = []
    for pub, (s, m) in sorted(tmap.items(), key=lambda x: (-(x[1][1].get("year_started") or 0), x[0])):
        cs = []
        for c in list(caps.get(pub, {}))[:2]:
            cs.append({"vol": 1, "src": "rakuten", "caption": c})
        for k in {pub, s}:
            for c in vd.get(k, [])[:1]:
                cs.append({"vol": 1, "src": "voldesc", "caption": c})
            if k in bl:
                cs.append({"vol": 1, "src": "booklive", "caption": bl[k]})
        if not cs:
            continue
        items.append({"slug": s, "pub": pub, "title": m.get("title"), "subtitle": m.get("subtitle"),
                      "authors": [x for x in (m.get("authors") or [])][:3], "year": m.get("year_started"),
                      "magazine": m.get("magazine"), "demographic": m.get("demographic"),
                      "genres_now": m.get("genres") or [], "themes_now": m.get("themes") or [],
                      "n_vols": m.get("total_volumes") or 1, "captions": cs})

    os.makedirs(BATCHDIR, exist_ok=True)
    n = 0
    for i in range(0, len(items), a.size):
        num = a.start + n
        chunk = items[i:i + a.size]
        json.dump({"kind": "catch1", "items": chunk},
                  io.open(os.path.join(BATCHDIR, f"batch-{num}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        with io.open(os.path.join(BATCHDIR, f"digest-{num}.txt"), "w", encoding="utf-8") as out:
            for j, e in enumerate(chunk, 1):
                au = "・".join(str(x).split("\t")[0] for x in e["authors"])
                out.write(f"[{j}] {e['slug']} | {e['title']}{(' ' + e['subtitle']) if e['subtitle'] else ''} | {au} | "
                          f"{e['year']} | {e['magazine'] or '-'} | {e['demographic'] or '-'} | g={','.join(e['genres_now'])} | t={','.join(e['themes_now'])}\n")
                for c in e["captions"]:
                    out.write(f"    {c['src']}: {c['caption'][:420]}\n")
        n += 1
    print(f"targets {len(targets)} / src解決 {len(tmap)} / 材料あり {len(items)} -> batch-{a.start}..{a.start + n - 1} ({n} batches)")
    print("  src:", dict(collections.Counter(c["src"] for e in items for c in e["captions"])))


if __name__ == "__main__":
    main()
