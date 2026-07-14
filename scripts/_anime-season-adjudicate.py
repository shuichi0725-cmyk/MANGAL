#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""アニメ季節・保留の自動裁定 (= 題名/別名一致 × 著者姓一致 の二重ゲート)。

保留(join失敗)のうち原作漫画relationを持つものについて、AniListから原作ノードの
title/synonyms/staff を一括取得(id_in 50件/req)し、うちのDBと突合:
  - 題名 or synonym の正規化一致で頁候補を出す
  - 候補頁の著者姓に AniList staff の姓(名 姓の最後の語)が含まれる時だけ ACCEPT
  - 候補複数/著者不一致/候補0 = 保留のまま(無理しない)
結果は data/seeds/anime-season-accepts.jsonl に純粋追加(join が最優先で読む)。

使い方:
  python scripts/_anime-season-adjudicate.py          # 裁定実行(API ~15req)
  python scripts/_anime-season-adjudicate.py --dry    # 書き込まず判定だけ表示
"""
import argparse, json, os, re, sys, time, unicodedata, urllib.request
from _idx_authors import au_name  # ★索引v2 authorsパック対応(2026-07-14)

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEASONS = os.path.join(ROOT, "data", "seeds", "anime-seasons.jsonl")
LINKS = os.path.join(ROOT, "data", "seeds", "anime-season-links.jsonl")
ACCEPTS = os.path.join(ROOT, "data", "seeds", "anime-season-accepts.jsonl")
MAP = os.path.join(ROOT, ".cache", "anilist-to-slug.json")
INDEX = os.path.join(ROOT, "data", "manga-list-index.json")

QUERY = """
query ($ids: [Int]) {
  Page(perPage: 50) {
    media(id_in: $ids, type: MANGA) {
      id
      title { native romaji }
      synonyms
      staff { edges { role node { name { full native } } } }
    }
  }
}
"""


def norm(t):
    t = unicodedata.normalize("NFKC", str(t or "")).lower()
    return re.sub(r"[\s　・!！?？:：〜~ー\-。、．.「」『』()（）☆★♥&＆]", "", t)


def gql(ids):
    body = json.dumps({"query": QUERY, "variables": {"ids": ids}}).encode()
    for attempt in range(4):
        req = urllib.request.Request("https://graphql.anilist.co", data=body,
                                     headers={"Content-Type": "application/json",
                                              "User-Agent": "Mozilla/5.0 (MANGAL adjudicate)"})
        try:
            return json.loads(urllib.request.urlopen(req, timeout=30).read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                wait = int(e.headers.get("Retry-After") or 65)
                print(f"  429: {wait}s待機", flush=True)
                time.sleep(wait)
                continue
            raise


def surname_candidates(staff_edges):
    """AniList staff から姓候補集合(native優先。'名 姓'順のfullは最後の語)"""
    out = set()
    for e in staff_edges or []:
        nm = (e.get("node") or {}).get("name") or {}
        nat = nm.get("native")
        if nat:
            # 日本語表記は「姓 名」or 連結。空白があれば先頭語=姓、無ければ先頭2文字も候補に
            parts = str(nat).replace("　", " ").split(" ")
            out.add(norm(parts[0]))
            if len(parts) == 1 and len(nat) >= 2:
                out.add(norm(nat[:2]))
        full = nm.get("full")
        if full:
            out.add(norm(str(full).split(" ")[-1]))  # ローマ字 名 姓
    return {s for s in out if s}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    # 保留対象 = seasons - links - 既accepts のうち漫画relationあり
    linked = {json.loads(l)["anime_anilist_id"] for l in open(LINKS, encoding="utf-8")}
    done = set()
    if os.path.exists(ACCEPTS):
        done = {json.loads(l)["anime_anilist_id"] for l in open(ACCEPTS, encoding="utf-8")}
    holds = []
    for l in open(SEASONS, encoding="utf-8"):
        r = json.loads(l)
        if r["anime_anilist_id"] in linked or r["anime_anilist_id"] in done:
            continue
        nodes = [c for c in (r.get("source_manga") or []) if c.get("anilist_id")]
        if nodes:
            holds.append((r, nodes))
    print(f"裁定対象(漫画relationあり保留): {len(holds)}アニメ", flush=True)

    # 原作ノードid → AniList詳細
    need_ids = sorted({c["anilist_id"] for _, nodes in holds for c in nodes})
    print(f"AniList取得: {len(need_ids)}ノード ({(len(need_ids) + 49) // 50}req)", flush=True)
    details = {}
    for i in range(0, len(need_ids), 50):
        chunk = need_ids[i:i + 50]
        r = gql(chunk)
        for m in r["data"]["Page"]["media"]:
            details[m["id"]] = m
        time.sleep(2.6)

    # DB側: 題名index + slug→著者
    li = json.load(open(INDEX, encoding="utf-8"))
    f = li["f"]
    isl, it, ia, io = f.index("slug"), f.index("title"), f.index("authors"), f.index("original_authors")
    t2s = {}
    authors = {}
    for row in li["d"]:
        t2s.setdefault(norm(row[it]), []).append(row[isl])
        # ★original_authors も含める (= LN原作アニメのrelationノードはラノベ本体のことがあり、
        #   その著者は頁のoriginal側に居る。ヘルモード=ハム男 型。2026-07-12)
        authors[row[isl]] = {norm(au_name(x)) for x in (row[ia] or [])} | \
                            {norm(au_name(x)) for x in (row[io] or [])}

    n_acc = n_stay = 0
    out_rows = []
    for r, nodes in holds:
        verdict = None
        for c in nodes:
            d = details.get(c["anilist_id"])
            if not d:
                continue
            titles = [d.get("title", {}).get("native"), d.get("title", {}).get("romaji")] + (d.get("synonyms") or [])
            # 副題切り落とし形も試す(無職転生~サブタイトル~型)
            expand = list(titles)
            for t in titles:
                if t:
                    head = re.split(r"[~〜～:：]", str(t))[0].strip()
                    if head and head != t:
                        expand.append(head)
            cand_slugs = set()
            for t in expand:
                if not t:
                    continue
                hit = t2s.get(norm(t))
                if hit:
                    cand_slugs.update(hit)
            if not cand_slugs:
                continue
            surs = surname_candidates((d.get("staff") or {}).get("edges"))
            ok = []
            for s in cand_slugs:
                au = authors.get(s) or set()
                if any(sur and any(sur in a for a in au) for sur in surs):
                    ok.append(s)
            if len(ok) == 1:
                verdict = {"anime_anilist_id": r["anime_anilist_id"], "slug": ok[0],
                           "via": "adjudicate:title+author",
                           "evidence": f"{r.get('anime_title')} ← node {c['anilist_id']} {d.get('title', {}).get('native')}",
                           "at": time.strftime("%Y-%m-%d")}
                break
            # 候補1つでも著者不一致、または複数 = 保留のまま
        if verdict:
            n_acc += 1
            out_rows.append(verdict)
            print(f"  ACCEPT {verdict['evidence']} → {verdict['slug']}")
        else:
            n_stay += 1
    print(f"自動裁定 ACCEPT {n_acc} / 保留のまま {n_stay}")
    if not a.dry and out_rows:
        with open(ACCEPTS, "a", encoding="utf-8") as fo:
            for row in out_rows:
                fo.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"→ {os.path.relpath(ACCEPTS, ROOT)} に追記。 join再実行で反映")


if __name__ == "__main__":
    main()
