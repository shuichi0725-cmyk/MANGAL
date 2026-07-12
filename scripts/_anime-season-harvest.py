#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""アニメ季節ハーベスト (= AniList季節クエリ→原作漫画リンク付きでseed化)。

「アニメの原作漫画」コーナー(季刊入替+全歴史)の収穫エンジン。2026-07-12 設計。
  - season×year の全TVアニメを取得(1963〜)。各作の source(MANGA/LIGHT_NOVEL/...) と
    relations から SOURCE/ADAPTATION の MANGA ノード(=原作漫画のanilist_id)を抜く
  - 出力: data/seeds/anime-seasons.jsonl (純粋追加・再実行で季単位skip・再開可能)
  - MANGAL頁へのjoinは別工程(_anime-season-join.py)

使い方:
  python scripts/_anime-season-harvest.py --from 1963 --to 2026     # 全歴史(初回・~20分)
  python scripts/_anime-season-harvest.py --season 2026-SUMMER      # 1季だけ(季刊更新)
  python scripts/_anime-season-harvest.py --stats
レート: 1.7s/req(AniList 90req/分の半分以下に抑える)。429=即中断(再実行で再開)。
"""
import argparse, json, os, sys, time, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(ROOT, "data", "seeds", "anime-seasons.jsonl")
SEASONS = ["WINTER", "SPRING", "SUMMER", "FALL"]

QUERY = """
query ($y: Int, $s: MediaSeason, $p: Int) {
  Page(page: $p, perPage: 50) {
    pageInfo { hasNextPage }
    media(season: $s, seasonYear: $y, type: ANIME, format_in: [TV, TV_SHORT]) {
      id
      idMal
      title { native romaji }
      source
      popularity
      startDate { year month day }
      relations {
        edges {
          relationType
          node { id type format title { native } }
        }
      }
    }
  }
}
"""


def gql(y, s, p):
    body = json.dumps({"query": QUERY, "variables": {"y": y, "s": s, "p": p}}).encode()
    req = urllib.request.Request("https://graphql.anilist.co", data=body,
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "Mozilla/5.0 (MANGAL harvest)"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def load_done():
    done = set()
    if os.path.exists(SEED):
        for line in open(SEED, encoding="utf-8"):
            try:
                done.add(json.loads(line)["season_key"])
            except Exception:
                pass
    return done


def harvest_season(y, s, out):
    """1季を全ページ取得して書き出す。戻り値=作品数(429等の例外は上へ)"""
    rows = []
    p = 1
    while True:
        r = gql(y, s, p)
        page = r["data"]["Page"]
        for m in page["media"]:
            src_manga = []
            for e in (m.get("relations") or {}).get("edges") or []:
                node = e.get("node") or {}
                # アニメ側から見た原作 = SOURCE (念のためADAPTATIONのMANGAも拾い、joinで判定)
                if node.get("type") == "MANGA" and e.get("relationType") in ("SOURCE", "ADAPTATION"):
                    src_manga.append({"anilist_id": node["id"], "rel": e["relationType"],
                                      "title": (node.get("title") or {}).get("native")})
            rows.append({
                "season_key": f"{y}-{s}",
                "anime_anilist_id": m["id"],
                "anime_title": (m.get("title") or {}).get("native") or (m.get("title") or {}).get("romaji"),
                "source": m.get("source"),
                "popularity": m.get("popularity"),
                "start": m.get("startDate"),
                "source_manga": src_manga,
            })
        if not page["pageInfo"]["hasNextPage"]:
            break
        p += 1
        time.sleep(1.7)
    for row in rows:
        out.write(json.dumps(row, ensure_ascii=False) + "\n")
    out.flush()
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="y_from", type=int)
    ap.add_argument("--to", dest="y_to", type=int)
    ap.add_argument("--season", help="YYYY-SEASON 形式で1季だけ")
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()

    if a.stats:
        done = load_done()
        n = sum(1 for _ in open(SEED, encoding="utf-8")) if os.path.exists(SEED) else 0
        print(f"収穫済み {len(done)}季 / {n}作品行")
        return

    targets = []
    if a.season:
        y, s = a.season.split("-")
        targets = [(int(y), s.upper())]
    elif a.y_from and a.y_to:
        for y in range(a.y_from, a.y_to + 1):
            for s in SEASONS:
                targets.append((y, s))
    else:
        ap.error("--from/--to か --season を指定")

    done = load_done()
    targets = [(y, s) for y, s in targets if f"{y}-{s}" not in done]
    print(f"対象 {len(targets)}季 (収穫済skip込み)", flush=True)
    out = open(SEED, "a", encoding="utf-8")
    for k, (y, s) in enumerate(targets):
        try:
            n = harvest_season(y, s, out)
        except Exception as e:
            print(f"★中断 {y}-{s}: {e} (再実行で再開)")
            break
        print(f"  {y}-{s}: {n}作品 [{k + 1}/{len(targets)}]", flush=True)
        time.sleep(1.7)
    print("done")


if __name__ == "__main__":
    main()
