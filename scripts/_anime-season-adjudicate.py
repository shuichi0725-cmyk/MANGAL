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

# --deep 用: format(NOVEL判定)と relations(LN→コミカライズの2ホップ) も取る
QUERY_DEEP = """
query ($ids: [Int]) {
  Page(perPage: 50) {
    media(id_in: $ids, type: MANGA) {
      id
      format
      title { native romaji }
      synonyms
      staff { edges { role node { name { full native } } } }
      relations { edges { relationType node { id type format title { native } } } }
    }
  }
}
"""


def norm(t):
    t = unicodedata.normalize("NFKC", str(t or "")).lower()
    return re.sub(r"[\s　・!！?？:：〜~ー\-‐‑。、．.「」『』()（）【】〈〉《》<>☆★♥&＆]", "", t)


def gql(ids, query=None):
    body = json.dumps({"query": query or QUERY, "variables": {"ids": ids}}).encode()
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
    ap.add_argument("--deep", action="store_true",
                    help="LN原作型の2ホップ裁定: relationノードの実体がNOVEL(AniListはLNもtype=MANGA)の時、"
                         "そのLNのrelationsからコミカライズ(format MANGA/ONE_SHOT)を辿って結線(薬屋/塩対応型)")
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
    q = QUERY_DEEP if a.deep else QUERY
    print(f"AniList取得: {len(need_ids)}ノード ({(len(need_ids) + 49) // 50}req)", flush=True)
    details = {}
    for i in range(0, len(need_ids), 50):
        chunk = need_ids[i:i + 50]
        r = gql(chunk, q)
        for m in r["data"]["Page"]["media"]:
            details[m["id"]] = m
        time.sleep(2.6)

    # --deep: NOVELノードのrelationsからコミカライズ(2ホップ先)を集め、詳細を追加取得
    hop2 = {}  # ln_aid -> [comicalize node dict]
    if a.deep:
        hop2_ids = set()
        for aid, d in details.items():
            if d.get("format") != "NOVEL":
                continue
            for e in (d.get("relations") or {}).get("edges") or []:
                nd = e.get("node") or {}
                if nd.get("type") == "MANGA" and nd.get("format") in ("MANGA", "ONE_SHOT") \
                        and e.get("relationType") in ("ADAPTATION", "ALTERNATIVE"):
                    hop2.setdefault(aid, []).append(nd["id"])
                    hop2_ids.add(nd["id"])
        hop2_ids -= set(details)
        print(f"--deep: LNノード{len(hop2)}件 → コミカライズ候補{len(hop2_ids)}ノード追加取得", flush=True)
        for i in range(0, len(sorted(hop2_ids)), 50):
            chunk = sorted(hop2_ids)[i:i + 50]
            r = gql(chunk, QUERY_DEEP)
            for m in r["data"]["Page"]["media"]:
                details[m["id"]] = m
            time.sleep(2.6)

    # a2s: 頁のanilist_id逆引き(joinと同じmap。2ホップ先aidの直結線判定に使う)
    a2s = {}
    if os.path.exists(MAP):
        a2s = (json.load(open(MAP, encoding="utf-8")) or {}).get("anilist") or {}

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
    stays = []  # (season, anime_title, 型, 詳細)
    for r, nodes in holds:
        verdict = None
        stay_info = []
        # --deep: NOVELノードはコミカライズ(2ホップ先)に差し替えて判定
        cand_aids = []
        for c in nodes:
            aid = c["anilist_id"]
            if a.deep and (details.get(aid) or {}).get("format") == "NOVEL":
                cand_aids.extend(hop2.get(aid, []))
            else:
                cand_aids.append(aid)
        for aid in dict.fromkeys(cand_aids):
            # 2ホップ先aidが既に頁へ結線済(a2s)なら最強証拠で即accept
            if a.deep and str(aid) in a2s:
                verdict = {"anime_anilist_id": r["anime_anilist_id"], "slug": a2s[str(aid)],
                           "via": "adjudicate:ln-deep-aid",
                           "evidence": f"{r.get('anime_title')} ← LN relations経由 comicalize {aid}(頁aid直結線)",
                           "at": time.strftime("%Y-%m-%d")}
                break
            d = details.get(aid)
            if not d:
                continue
            c = {"anilist_id": aid}
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
                # ★包含フォールバック(2026-09-01): 完全一致ゼロの時だけ、正規化題の包含
                #   (ジョジョの奇妙な冒険ファントムブラッド ⊃ 頁題ジョジョの奇妙な冒険 /
                #    頁題まどか☆マギカ魔獣編 ⊃ 題まどか☆マギカ)を候補化。短題の誤爆は
                #    len≥6ガード+著者ゲートで防ぐ。ACCEPTは常に著者一致必須。
                for t in expand:
                    nt = norm(t)
                    if len(nt) < 6:
                        continue
                    for pk, slugs2 in t2s.items():
                        if len(pk) >= 6 and (nt in pk or pk in nt):
                            cand_slugs.update(slugs2)
            if not cand_slugs:
                stay_info.append(("NO_PAGE", f"{aid} {d.get('title', {}).get('native')}"))
                continue
            surs = surname_candidates((d.get("staff") or {}).get("edges"))
            ok = []
            for s in cand_slugs:
                au = authors.get(s) or set()
                if any(sur and any(sur in a for a in au) for sur in surs):
                    ok.append(s)
            if not ok:
                stay_info.append(("GATE_FAIL", f"{aid} {d.get('title', {}).get('native')} 候補={sorted(cand_slugs)[:3]}"))
            elif len(ok) > 1:
                stay_info.append(("AMBIG", f"{aid} ok={sorted(ok)[:4]}"))
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
            kind = stay_info[0][0] if stay_info else "NO_CAND"
            stays.append((r["season_key"], r.get("anime_title") or "", kind,
                          " / ".join(f"{k}:{v}" for k, v in stay_info[:2])))
    print(f"自動裁定 ACCEPT {n_acc} / 保留のまま {n_stay}")
    stays_p = os.path.join(ROOT, "docs", "production-diagnostics", "anime-season-stays.tsv")
    with open(stays_p, "w", encoding="utf-8", newline="") as fo:
        fo.write("season\tanime_title\tkind\tdetail\n")
        for row in sorted(stays, reverse=True):
            fo.write("\t".join(str(x) for x in row) + "\n")
    from collections import Counter
    print("保留の型内訳:", dict(Counter(s[2] for s in stays)))
    print(f"→ {os.path.relpath(stays_p, ROOT)}")
    if not a.dry and out_rows:
        with open(ACCEPTS, "a", encoding="utf-8") as fo:
            for row in out_rows:
                fo.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"→ {os.path.relpath(ACCEPTS, ROOT)} に追記。 join再実行で反映")


if __name__ == "__main__":
    main()
