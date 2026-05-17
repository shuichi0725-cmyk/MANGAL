"""step G: db-v2.sqlite + series-supplement-v2.yml から MANGAL yml を 生成。

v1 scope: 既存 56 yml に 対応する series のみ regenerate
  - data/manga/*.yml の slug を 起点に db-v2 で 検索
  - 新 schema (= subtitle, subtitle_kana, volume_label 等) で 出力
  - data/manga.v2/<slug>.yml に書き出し (= 旧 data/manga は 不変)
  - 後で diff で 比較

filter (= step A/B、 「本編以外は極力表示しない」):
  - step A: 同 qid series で 「親 / 子」 関係 検出
            親 = title が prefix で 親 has MORE volumes → 子 is spinoff
  - step B: 本編 series 内の edition filter
            keep: standard / bunkobon / wideban / kanzenban / shinsoban / aizoban
            drop: anime / other / renewal
            drop imprint: 'My first big%' / '%コンビニ%' / '%増刊%'
            spinoff series は max(release_date) >= CUTOFF_YEAR なら keep
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

CUTOFF_YEAR = 2015  # spinoff で この年 以降なら keep
KEEP_EDITION_TYPES = {"standard", "bunkobon", "wideban", "kanzenban", "shinsoban", "aizoban"}
DROP_IMPRINT_PATTERNS = ["My first big", "コンビニ", "増刊", "同人"]
# bilingual / 英訳版 imprint は drop (= 翻訳版 は 別 product)
DROP_IMPRINT_LOWER_PATTERNS = ["bilingual"]


def load_seed3() -> dict:
    """series_key → seed3 entry の dict"""
    with SEED3.open("r", encoding="utf-8") as f:
        d = yaml.safe_load(f)
    return {e["key"]: e for e in d["series"]}


def normalize_title_for_prefix(t: str) -> str:
    """『〜』 strip、 「英訳・」「劇場版」「テレビアニメ版」 等 接頭辞 strip。"""
    s = t.strip()
    # 『...』 → ...
    s = re.sub(r"[『「【〔]", "", s)
    s = re.sub(r"[』」】〕]", "", s)
    # 接頭辞 strip
    for prefix in ["英訳・", "劇場版", "劇場用アニメ", "テレビアニメ版",
                   "映画 ", "映画"]:
        if s.startswith(prefix):
            s = s[len(prefix):].lstrip()
    return s


def build_parent_map(con: sqlite3.Connection) -> dict[int, int]:
    """series_id → parent_series_id (= 親検出済 only)。 公開対象 (= score<3) のみ。

    親判定:
      - 同 qid または 同 creator_name
      - 親 title が 子 title の prefix (= normalize 後)
      - 親 has MORE total ISBN volumes than 子
      - 親 自身 が 副題なし
    """
    cur = con.cursor()
    cur.row_factory = sqlite3.Row
    cur.execute("""
        SELECT s.id, s.qid, s.title, s.subtitle,
               (SELECT COUNT(*) FROM volumes v JOIN editions e ON e.id=v.edition_id
                WHERE e.series_id=s.id AND v.isbn13 IS NOT NULL) AS n_isbn
        FROM series s
        WHERE s.adult_score < 3
    """)
    all_series = [dict(r) for r in cur.fetchall()]
    by_qid = defaultdict(list)
    for s in all_series:
        if s["qid"]:
            by_qid[s["qid"]].append(s)
    parent_map: dict[int, int] = {}
    for qid, sib in by_qid.items():
        # 候補 parent (= 副題なし、 n_isbn 多い順)
        parents = [s for s in sib if not s["subtitle"]]
        parents.sort(key=lambda s: -s["n_isbn"])
        for child in sib:
            child_norm = normalize_title_for_prefix(child["title"])
            for parent in parents:
                if parent["id"] == child["id"]:
                    continue
                parent_norm = normalize_title_for_prefix(parent["title"])
                if not parent_norm:
                    continue
                # parent_norm が child_norm の prefix
                if child_norm.startswith(parent_norm) and child_norm != parent_norm:
                    # 親 has more vol
                    if parent["n_isbn"] > child["n_isbn"]:
                        parent_map[child["id"]] = parent["id"]
                        break
                # 副題ある child は parent と base title が一致 (= no prefix relation)
                # ケースも spinoff 扱い
                elif child.get("subtitle") and parent_norm == child_norm:
                    if parent["n_isbn"] > child["n_isbn"]:
                        parent_map[child["id"]] = parent["id"]
                        break
    return parent_map


def get_max_release_year(con: sqlite3.Connection, series_id: int) -> int | None:
    cur = con.cursor()
    cur.row_factory = sqlite3.Row
    r = cur.execute("""
        SELECT MAX(SUBSTR(v.release_date, 1, 4)) AS y
        FROM volumes v JOIN editions e ON e.id=v.edition_id
        WHERE e.series_id=? AND v.release_date IS NOT NULL
    """, (series_id,)).fetchone()
    if r and r["y"]:
        try:
            return int(r["y"])
        except ValueError:
            return None
    return None


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


def edition_passes_filter(ed_row: dict) -> bool:
    """edition の type / imprint で 本編判定。 step B filter。"""
    if ed_row["type"] not in KEEP_EDITION_TYPES:
        return False
    imp = ed_row["imprint"] or ""
    for pat in DROP_IMPRINT_PATTERNS:
        if pat in imp:
            return False
    imp_l = imp.lower()
    for pat in DROP_IMPRINT_LOWER_PATTERNS:
        if pat in imp_l:
            return False
    return True


def get_editions_with_volumes(con: sqlite3.Connection, series_id: int) -> list[dict]:
    """editions + volumes を まとめて取得し、 同 type editions を 1 つに merge。

    merge logic (= 同 series 内の 同 type editions = 限定版/DVD付き 等 packaging variant が
                  imprint 違いで 分裂しているため):
      - imprint 違いの 同 type editions を 1 つに統合
      - volume number で dedup、 同 number は 最古 release_date の entry を採用
      - 統合後 edition の imprint = 最多 volumes を持つ imprint
      - label は 最多 volumes を持つ edition から
    """
    cur = con.cursor()
    cur.row_factory = sqlite3.Row
    eds = cur.execute(
        "SELECT * FROM editions WHERE series_id=?", (series_id,)
    ).fetchall()
    # type → [edition+volumes] list
    by_type: dict[str, list[dict]] = defaultdict(list)
    for ed in eds:
        if not edition_passes_filter(dict(ed)):
            continue
        vols = cur.execute(
            """SELECT * FROM volumes WHERE edition_id=?
               ORDER BY number, release_date""",
            (ed["id"],),
        ).fetchall()
        if not vols:
            continue
        # 同 number 内で 一番古い 1 件のみ採用 (= 初版 representative、 同 edition 内 dedup)
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
        by_type[ed["type"]].append(
            {
                "type": ed["type"],
                "label": ed["label"],
                "imprint": ed["imprint"],
                "year_started": ed["year_started"],
                "year_ended": ed["year_ended"],
                "volumes": primary_vols,
            }
        )
    out = []
    for type_key, ed_group in by_type.items():
        if len(ed_group) == 1:
            out.append(ed_group[0])
            continue
        # 同 type で 複数 edition → merge
        # 全 volumes を集めて number で dedup、 同 number は release_date 最古 entry 優先
        by_num: dict[int, dict] = {}
        for ed in ed_group:
            for v in ed["volumes"]:
                n = v["number"]
                cur_v = by_num.get(n)
                if cur_v is None:
                    by_num[n] = v
                    continue
                # release_date 比較 (= None は 最後扱い)
                cur_d = cur_v.get("release_date") or "9999-99"
                new_d = v.get("release_date") or "9999-99"
                if new_d < cur_d:
                    by_num[n] = v
        merged_vols = [by_num[n] for n in sorted(by_num.keys())]
        # 代表 imprint / label = 最多 volumes を持つ edition から (= main 印象維持)
        primary_ed = max(ed_group, key=lambda e: len(e["volumes"]))
        out.append(
            {
                "type": type_key,
                "label": primary_ed["label"],
                "imprint": primary_ed["imprint"],
                "year_started": primary_ed["year_started"],
                "year_ended": primary_ed["year_ended"],
                "volumes": merged_vols,
            }
        )
    # editions を 第1巻 (= 最古 volume) の release_date 昇順 で sort
    def first_vol_date(ed_dict):
        dates = [v["release_date"] for v in ed_dict["volumes"] if v["release_date"]]
        return min(dates) if dates else "9999-99"
    out.sort(key=first_vol_date)
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

    # 年代: editions の volumes.release_date から 計算
    # year_started = 最も古い edition の 最初の volume year
    # year_ended = 「最初の edition (= 本編初版)」 の 最後の volume year
    #              (= リニューアル版を 含めずに 原作連載終了年を出す)
    def year_of(d: str | None) -> int | None:
        if not d or len(d) < 4:
            return None
        try:
            return int(d[:4])
        except ValueError:
            return None

    all_years = []
    for ed in editions:
        for v in ed["volumes"]:
            y = year_of(v.get("release_date"))
            if y:
                all_years.append(y)
    o["year_started"] = min(all_years) if all_years else src_yml.get("year_started", 2000)

    # year_ended: 最初の edition (= sorted by first vol date) の max year
    # ただし outlier 1 件 (= 単一巻だけ 重版年が混入) は drop
    if editions:
        first_ed_years = [year_of(v.get("release_date")) for v in editions[0]["volumes"]]
        first_ed_years = sorted([y for y in first_ed_years if y])
        # outlier 除外: 末尾の年が 直前と 5 年以上空くなら drop
        while len(first_ed_years) > 5:
            if first_ed_years[-1] - first_ed_years[-2] > 5:
                first_ed_years.pop()
            else:
                break
        if first_ed_years:
            o["year_ended"] = max(first_ed_years)
        else:
            o["year_ended"] = src_yml.get("year_ended")
    else:
        o["year_ended"] = src_yml.get("year_ended")
    # status は 種3 から
    o["status"] = (seed3 or {}).get("status") or src_yml.get("status", "completed")
    # status=ongoing なら year_ended は null
    if o["status"] == "ongoing":
        o["year_ended"] = None

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

    # step A: 親 series 検出 map
    print("[step A] 親 series 検出 中 ...", file=sys.stderr)
    parent_map = build_parent_map(con)
    print(f"  検出 spinoff series 数: {len(parent_map)}", file=sys.stderr)

    stats = {"total": 0, "regenerated": 0, "not_found_in_db": 0,
             "no_editions": 0, "dropped_spinoff_old": 0}
    not_found = []
    dropped = []

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
        # step A: spinoff 判定 (= 親があれば 子 = spinoff)
        is_spinoff = series["id"] in parent_map
        if is_spinoff:
            max_y = get_max_release_year(con, series["id"])
            if max_y is None or max_y < CUTOFF_YEAR:
                stats["dropped_spinoff_old"] += 1
                dropped.append(f"{ypath.name}  title={title}  max_year={max_y}")
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
    if dropped:
        print(f"\n=== dropped (= spinoff & old) ===", file=sys.stderr)
        for d in dropped:
            print(f"  🗑️  {d}", file=sys.stderr)

    print(f"\nwrote {stats['regenerated']} yml to {OUT_DIR}", file=sys.stderr)


if __name__ == "__main__":
    main()
