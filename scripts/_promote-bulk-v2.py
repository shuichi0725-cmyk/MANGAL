"""step G: db-v2.sqlite + series-supplement-v2.yml から MANGAL yml を 生成。

v1 scope: 既存 56 yml に 対応する series のみ regenerate
  - data/manga/*.yml の slug を 起点に db-v2 で 検索
  - 新 schema (= subtitle, subtitle_kana, volume_label 等) で 出力
  - data/manga.v2/<slug>.yml に書き出し (= 旧 data/manga は 不変)
  - 後で diff で 比較

(完全な promote-bulk v2 = 全 152k series 対象は 別途実装)
"""

import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
SEED3 = ROOT / "data" / "seeds" / "series-supplement-v2.yml"
SRC_DIR = ROOT / "data" / "manga"
OUT_DIR = ROOT / "data" / "manga.v2"


def load_seed3() -> dict:
    """series_key → seed3 entry の dict"""
    with SEED3.open("r", encoding="utf-8") as f:
        d = yaml.safe_load(f)
    return {e["key"]: e for e in d["series"]}


def find_series(con: sqlite3.Connection, slug: str, title: str, qid: str | None) -> dict | None:
    """旧 yml の (slug, title, qid) から db-v2 で series 探す。

    優先順:
      1. qid + title 完全一致
      2. title 完全一致 (= qid なし時)
      3. title 部分一致
    """
    cur = con.cursor()
    cur.row_factory = sqlite3.Row
    if qid:
        rows = cur.execute(
            "SELECT * FROM series WHERE qid=? AND title=? ORDER BY adult_score LIMIT 1",
            (qid, title),
        ).fetchall()
        if rows:
            return dict(rows[0])
    rows = cur.execute(
        "SELECT * FROM series WHERE title=? ORDER BY adult_score LIMIT 1", (title,)
    ).fetchall()
    if rows:
        return dict(rows[0])
    return None


def get_authors(con: sqlite3.Connection, series_id: int) -> list[dict]:
    cur = con.cursor()
    cur.row_factory = sqlite3.Row
    rows = cur.execute(
        """
        SELECT m.name, sa.role
        FROM series_authors sa
        JOIN mangaka m ON m.id = sa.mangaka_id
        WHERE sa.series_id = ?
        """,
        (series_id,),
    ).fetchall()
    return [{"name": r["name"], "role": r["role"]} for r in rows]


def get_editions_with_volumes(con: sqlite3.Connection, series_id: int) -> list[dict]:
    """editions + volumes を まとめて取得。 volumes は number 昇順、 同 number で release_date 古順。"""
    cur = con.cursor()
    cur.row_factory = sqlite3.Row
    eds = cur.execute(
        "SELECT * FROM editions WHERE series_id=? ORDER BY type, imprint", (series_id,)
    ).fetchall()
    out = []
    for ed in eds:
        vols = cur.execute(
            """SELECT * FROM volumes WHERE edition_id=?
               ORDER BY number, release_date""",
            (ed["id"],),
        ).fetchall()
        # 同 number 内で 一番古い 1 件のみ採用 (= 初版 representative)
        seen = set()
        primary_vols = []
        for v in vols:
            if v["number"] in seen:
                continue
            seen.add(v["number"])
            primary_vols.append(
                {
                    "number": v["number"] if v["number"] else 1,
                    "volume_label": v["volume_label"],
                    "isbn13": v["isbn13"],
                    "release_date": v["release_date"],
                    "cover_url": v["cover_url"],
                    "asin": v["asin"],
                }
            )
        if not primary_vols:
            continue
        out.append(
            {
                "type": ed["type"],
                "label": ed["label"],
                "imprint": ed["imprint"],
                "year_started": ed["year_started"],
                "year_ended": ed["year_ended"],
                "volumes": primary_vols,
            }
        )
    return out


def clean_vol(v: dict) -> dict:
    """yml に出力する volume dict を 作る (= null を 適切に省略)"""
    o = {"number": v["number"]}
    if v["volume_label"]:
        o["volume_label"] = v["volume_label"]
    o["asin"] = v.get("asin")
    if v["isbn13"]:
        o["isbn13"] = str(v["isbn13"])
    else:
        o["isbn13"] = None
    o["cover_url"] = v.get("cover_url")
    if v["release_date"]:
        o["release_date"] = v["release_date"]
    else:
        o["release_date"] = None
    return o


def clean_edition(ed: dict) -> dict:
    out = {
        "type": ed["type"],
        "label": ed["label"],
    }
    if ed["imprint"]:
        out["imprint"] = ed["imprint"]
    if ed["year_started"]:
        out["year_started"] = ed["year_started"]
    if ed["year_ended"]:
        out["year_ended"] = ed["year_ended"]
    out["volumes"] = [clean_vol(v) for v in ed["volumes"]]
    return out


def build_yml(
    src_yml: dict,
    series_row: dict,
    authors: list[dict],
    editions: list[dict],
    seed3: dict | None,
    valid_pubs: set,
    valid_mags: set,
    valid_gens: set,
) -> dict:
    """db-v2 + 種3 + 旧 yml の slug / 一部 metadata から 新 yml dict を build。

    旧 yml から流用:
      - slug
      - title_romaji (= ローマ字化は ロジック移植せず 既存値 再利用)
      - anime_first_year / awards / wikipedia_url 等 既存補強
    """
    o: dict = {}
    o["slug"] = src_yml["slug"]
    o["title"] = series_row["title"]
    o["title_kana"] = series_row["title_kana"] or src_yml.get("title_kana", "")
    o["title_romaji"] = src_yml.get("title_romaji", "")
    if series_row["subtitle"]:
        o["subtitle"] = series_row["subtitle"]
    if series_row["subtitle_kana"]:
        o["subtitle_kana"] = series_row["subtitle_kana"]

    # 年代 (= editions.year_started/ended を 集約)
    years = [ed["year_started"] for ed in editions if ed["year_started"]]
    o["year_started"] = min(years) if years else src_yml.get("year_started", 2000)
    y_end = [ed["year_ended"] for ed in editions if ed["year_ended"]]
    o["year_ended"] = max(y_end) if y_end else src_yml.get("year_ended")
    # status は 種3 から
    o["status"] = (seed3 or {}).get("status") or src_yml.get("status", "completed")

    # authors / original_authors
    writers, originals = [], []
    for a in authors:
        if a["role"] == "original_author":
            originals.append({"name": a["name"], "role": "writer"})  # 旧 schema 互換
        else:
            writers.append({"name": a["name"], "role": a["role"]})
    if not writers:
        writers = src_yml.get("authors") or [{"name": "(unknown)", "role": "writer_artist"}]
    o["authors"] = writers
    o["original_authors"] = originals

    # publisher: 種3 → 旧 yml の 優先で 取得、 master 未定義なら 旧 yml に fallback
    pub_cand = (seed3 or {}).get("publisher") or src_yml.get("publisher")
    if pub_cand and valid_pubs and pub_cand not in valid_pubs:
        pub_cand = src_yml.get("publisher", pub_cand)
    o["publisher"] = pub_cand or "(unknown)"

    # magazine: 種3 由来は AI fill で 旧 master key と 揃ってない 可能性
    # master 未定義時は 旧 yml に fallback、 それでも未定義なら null
    mag_cand = (seed3 or {}).get("magazine") or src_yml.get("magazine")
    if mag_cand and valid_mags and mag_cand not in valid_mags:
        # 旧 yml の magazine を 優先で 使う
        old_mag = src_yml.get("magazine")
        mag_cand = old_mag if old_mag and old_mag in valid_mags else None
    o["magazine"] = mag_cand

    o["demographic"] = (seed3 or {}).get("demographic") or src_yml.get("demographic", "shounen")

    # genres: 種3 由来 keys を validate
    genres_cand = (seed3 or {}).get("genres") or src_yml.get("genres", ["other"])
    if valid_gens:
        filtered = [g for g in genres_cand if g in valid_gens]
        if not filtered:
            filtered = src_yml.get("genres", ["other"])
        genres_cand = filtered
    o["genres"] = genres_cand

    o["synopsis"] = (seed3 or {}).get("synopsis") or src_yml.get("synopsis", "")

    # anime / alternative_titles
    anime_adapted = (seed3 or {}).get("anime_adapted")
    if anime_adapted is None:
        anime_adapted = src_yml.get("anime_adapted")
    if anime_adapted is not None:
        o["anime_adapted"] = anime_adapted
    if "anime_first_year" in src_yml:
        o["anime_first_year"] = src_yml["anime_first_year"]

    alt_en = series_row["title_official_en"]
    src_alt = src_yml.get("alternative_titles") or {}
    if alt_en or src_alt:
        merged_alt = dict(src_alt)
        if alt_en and "en" not in merged_alt:
            merged_alt["en"] = alt_en
        if merged_alt:
            o["alternative_titles"] = merged_alt

    if "awards" in src_yml:
        o["awards"] = src_yml["awards"]
    if series_row["qid"]:
        o["wikidata_qid"] = series_row["qid"]
    if "wikipedia_url" in src_yml:
        o["wikipedia_url"] = src_yml["wikipedia_url"]

    o["editions"] = [clean_edition(ed) for ed in editions]
    return o


def load_master_keys() -> tuple[set, set, set]:
    """data/magazines.yml + publishers.yml + genres.yml の 有効 key set を返す。"""
    pub_yml = ROOT / "data" / "publishers.yml"
    mag_yml = ROOT / "data" / "magazines.yml"
    gen_yml = ROOT / "data" / "genres.yml"
    pubs, mags, gens = set(), set(), set()
    if pub_yml.exists():
        with pub_yml.open("r", encoding="utf-8") as f:
            d = yaml.safe_load(f) or {}
        pubs = set(d.keys())
    if mag_yml.exists():
        with mag_yml.open("r", encoding="utf-8") as f:
            d = yaml.safe_load(f) or {}
        mags = set(d.keys())
    if gen_yml.exists():
        with gen_yml.open("r", encoding="utf-8") as f:
            d = yaml.safe_load(f) or {}
        gens = set(d.keys())
    return pubs, mags, gens


def main():
    print(f"loading {SEED3} ...", file=sys.stderr)
    seed3 = load_seed3()
    print(f"  entries: {len(seed3)}", file=sys.stderr)

    valid_pubs, valid_mags, valid_gens = load_master_keys()
    print(
        f"  master keys: pubs={len(valid_pubs)} mags={len(valid_mags)} gens={len(valid_gens)}",
        file=sys.stderr,
    )

    con = sqlite3.connect(DB)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # 既存 v2 dir clean
    for p in OUT_DIR.glob("*.yml"):
        p.unlink()

    stats = {"total": 0, "regenerated": 0, "not_found_in_db": 0, "no_editions": 0}
    not_found = []

    for ypath in sorted(SRC_DIR.glob("*.yml")):
        stats["total"] += 1
        with ypath.open("r", encoding="utf-8") as f:
            src = yaml.safe_load(f)
        slug = src["slug"]
        title = src["title"]
        qid = src.get("wikidata_qid")
        series = find_series(con, slug, title, qid)
        if not series:
            stats["not_found_in_db"] += 1
            not_found.append(f"{ypath.name}  title={title}")
            continue
        editions = get_editions_with_volumes(con, series["id"])
        if not editions:
            stats["no_editions"] += 1
            continue
        authors = get_authors(con, series["id"])
        seed_entry = seed3.get(series["series_key"])
        new_yml = build_yml(src, series, authors, editions, seed_entry,
                            valid_pubs, valid_mags, valid_gens)
        out_path = OUT_DIR / f"{slug}.yml"
        with out_path.open("w", encoding="utf-8") as f:
            f.write("# Regenerated by scripts/_promote-bulk-v2.py (= path B' step G)\n")
            yaml.dump(new_yml, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        stats["regenerated"] += 1

    print(f"\n=== stats ===", file=sys.stderr)
    for k, v in stats.items():
        print(f"  {k}: {v}", file=sys.stderr)
    if not_found:
        print(f"\n=== not found in db-v2 ===", file=sys.stderr)
        for n in not_found:
            print(f"  ❌ {n}", file=sys.stderr)

    print(f"\nwrote {stats['regenerated']} yml to {OUT_DIR}", file=sys.stderr)


if __name__ == "__main__":
    main()
