#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""アニメ季節→MANGAL頁 join (= anime-seasons.jsonl の原作漫画をうちのslugに結線)。

結線順(強い順):
  1. relations の MANGA ノード(format=MANGA/ONE_SHOT, rel=SOURCE優先)の anilist_id → 頁yml の anilist_id 逆引き
  2. アニメ題の正規化完全一致 → 頁title/一覧索引
  3. 未結線 → docs/production-diagnostics/anime-season-holds.tsv (人/AI裁定用)
出力: data/seeds/anime-season-links.jsonl {season_key, anime_anilist_id, anime_title, source, slug, via}
  ※ source=ORIGINAL 等の非漫画はスキップ(joinの対象外)。
使い方:
  python scripts/_anime-season-join.py            # 全季join(逆引きmapは.cacheに自動構築)
  python scripts/_anime-season-join.py --rebuild-map  # 頁yml全走査でanilist→slug map再構築(~数分)
"""
import argparse, glob, json, os, re, sys, unicodedata

sys.stdout.reconfigure(encoding="utf-8")
import yaml

try:
    from yaml import CSafeLoader as L
except ImportError:
    from yaml import SafeLoader as L

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(ROOT, "data", "seeds", "anime-seasons.jsonl")
OUT = os.path.join(ROOT, "data", "seeds", "anime-season-links.jsonl")
HOLDS = os.path.join(ROOT, "docs", "production-diagnostics", "anime-season-holds.tsv")
MAP = os.path.join(ROOT, ".cache", "anilist-to-slug.json")
# 裁定済みaccepts (= _anime-season-adjudicate.py / 手動。 anime_anilist_id→slug or slug=null(結線不能確定))
ACCEPTS = os.path.join(ROOT, "data", "seeds", "anime-season-accepts.jsonl")


def norm(t):
    t = unicodedata.normalize("NFKC", str(t or "")).lower()
    return re.sub(r"[\s　・!！?？:：〜~ー\-。、．.「」『』()（）☆★♥&＆]", "", t)


def build_map():
    m = {}
    titles = {}
    for p in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
        try:
            d = yaml.load(open(p, encoding="utf-8"), Loader=L)
        except Exception:
            continue
        if not d:
            continue
        slug = os.path.basename(p)[:-4]
        aid = d.get("anilist_id")
        if aid:
            m[str(aid)] = slug
        titles.setdefault(norm(d.get("title")), []).append(slug)
    json.dump({"anilist": m, "titles": titles}, open(MAP, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"map構築: anilist_id {len(m)}件 / title {len(titles)}件 → {os.path.relpath(MAP, ROOT)}")
    return {"anilist": m, "titles": titles}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild-map", action="store_true")
    a = ap.parse_args()

    if a.rebuild_map or not os.path.exists(MAP):
        maps = build_map()
    else:
        maps = json.load(open(MAP, encoding="utf-8"))
    a2s, t2s = maps["anilist"], maps["titles"]

    accepts = {}
    if os.path.exists(ACCEPTS):
        for l in open(ACCEPTS, encoding="utf-8"):
            try:
                d = json.loads(l)
                accepts[d["anime_anilist_id"]] = d.get("slug")  # None=結線不能確定(holdsに出さない)
            except Exception:
                pass

    rows = [json.loads(l) for l in open(SEED, encoding="utf-8")]
    out = open(OUT, "w", encoding="utf-8")
    holds = open(HOLDS, "w", encoding="utf-8")
    n_join = n_hold = n_skip = n_acc = 0
    for r in rows:
        # 0) 裁定済み(最優先)
        if r["anime_anilist_id"] in accepts:
            slug0 = accepts[r["anime_anilist_id"]]
            if slug0:
                out.write(json.dumps({"season_key": r["season_key"], "anime_anilist_id": r["anime_anilist_id"],
                                      "anime_title": r.get("anime_title"), "source": r.get("source"),
                                      "popularity": r.get("popularity"), "slug": slug0, "via": "accept"},
                                     ensure_ascii=False) + "\n")
                n_join += 1
            n_acc += 1
            continue
        src = r.get("source")
        cands = r.get("source_manga") or []
        # 非漫画原作かつ漫画relationも無い = コーナー対象外(ORIGINAL/GAME等)
        manga_nodes = [c for c in cands if c.get("anilist_id")]
        if src not in ("MANGA", "ONE_SHOT", "LIGHT_NOVEL", "NOVEL", "WEB_NOVEL") and not manga_nodes:
            n_skip += 1
            continue
        slug = None
        via = None
        # 1) SOURCE優先で anilist_id 結線
        for rel in ("SOURCE", "ADAPTATION"):
            for c in manga_nodes:
                if c.get("rel") == rel and str(c["anilist_id"]) in a2s:
                    slug = a2s[str(c["anilist_id"])]
                    via = f"anilist:{rel}"
                    break
            if slug:
                break
        # 2) 原作漫画ノードの題名一致 (= コミカライズのanilist_idが頁側に未結線でも題で繋ぐ。
        #    骸骨騎士様Ⅱ型: アニメ題はⅡ付きだが漫画relationの題は無印=頁題と一致する)
        if not slug:
            for c in manga_nodes:
                hit = t2s.get(norm(c.get("title")))
                if hit and len(hit) == 1:
                    slug = hit[0]
                    via = "manga-title"
                    break
        # 3) アニメ題の正規化完全一致(続編サフィックスを剥がした形も試す)
        if not slug:
            at = norm(r.get("anime_title"))
            cands_t = [at, re.sub(r"(ⅱ|ⅲ|2ndseason|3rdseason|season\d|第\d期|\d)$", "", at)]
            for t in cands_t:
                hit = t2s.get(t)
                if hit and len(hit) == 1:
                    slug = hit[0]
                    via = "title"
                    break
        if slug:
            out.write(json.dumps({"season_key": r["season_key"], "anime_anilist_id": r["anime_anilist_id"],
                                  "anime_title": r.get("anime_title"), "source": src,
                                  "popularity": r.get("popularity"), "slug": slug, "via": via},
                                 ensure_ascii=False) + "\n")
            n_join += 1
        else:
            holds.write(f"{r['season_key']}\t{r.get('anime_title')}\t{src}\t{json.dumps(manga_nodes, ensure_ascii=False)[:150]}\n")
            n_hold += 1
    print(f"join {n_join} (うち裁定accept {n_acc}) / 保留 {n_hold} / 非漫画skip {n_skip} (全{len(rows)}アニメ)")
    print(f"→ {os.path.relpath(OUT, ROOT)} / holds={os.path.relpath(HOLDS, ROOT)}")


if __name__ == "__main__":
    main()
