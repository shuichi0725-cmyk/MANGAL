"""主要 完結 漫画 2000 タイトル を db-v2 から 抽出 + yml 生成。

選定 criteria:
  - adult_score < 3 (= non-adult)
  - 通常版相当 (= standard/bunkobon/wideban/kanzenban/shinsoban/aizoban) edition あり
  - 最新巻 release_date <= 2020 (= 完結 推定)
  - 5巻以上 (= 主要作品)
  - title が 関連書 / 非漫画 prefix で 始まらない
  - score 順: qid あり ボーナス 100 + vol_count、 desc で top N

slug 自動生成:
  - title_kana を pykakasi で ローマ字化、 hyphen 区切り
  - 重複 slug は suffix '-2', '-3' 等

出力:
  - data/manga.draft-2000/*.yml (= 主 dir 不干渉)
"""

import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import yaml
import pykakasi

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
SEED3 = ROOT / "data" / "seeds" / "series-supplement-v2.yml"
OUT_DIR = ROOT / "data" / "manga.draft-2000"

TARGET_COUNT = 2000

# 関連書 / 非漫画 prefix で title 始まったら drop
DROP_TITLE_PATTERNS = [
    "テレビアニメ版", "TVアニメ版", "TVアニメ", "アニメコミック",
    "劇場版", "映画", "OVA",
    "ノベライズ", "ノベル", "小説",
    "公式ガイド", "公式ファンブック", "公式図録", "公式読本",
    "ガイドブック", "ファンブック", "アンソロジー",
    "設定資料集", "キャラクター名鑑",
]
# title 内に 含まれたら drop
DROP_TITLE_CONTAINS = [
    "の秘密", "の謎", "完全解析", "心理分析", "攻略本", "コミック大全",
    "コミックスペシャル", "ナビゲーション",
]

KEEP_EDITION_TYPES = {"standard", "bunkobon", "wideban", "kanzenban", "shinsoban", "aizoban"}

# ISBN-13 prefix → publisher key (= data/publishers.yml master と一致)
# 大半 メジャー 出版社 を カバー。 推定 不能 cases は skip。
ISBN_PUBLISHER_PREFIXES = [
    # 長い prefix を 先 (= 4-08 集英社 と 4-08-XX の sub-prefix は 先頭一致 順)
    ("978487731", "core-magazine"),
    ("978487572", "kubo-shoten"),
    ("978486554", "overlap"),
    ("978486442", "byakuya-shobo"),
    ("978486127", "mag-garden"),
    ("978484585", "leed"),
    ("978484584", "leed"),
    ("978484583", "leed"),
    ("978484582", "leed"),
    ("978484581", "leed"),
    ("978484580", "leed"),
    ("978484519", "leed"),
    ("978478598", "shonen-gahosha"),
    ("978478594", "shonen-gahosha"),
    ("978479861", "hobby-japan"),
    ("978479860", "hobby-japan"),
    ("978477323", "kaiohsha"),
    ("978477081", "line-digital-frontier"),
    ("978477080", "line-digital-frontier"),
    ("978477077", "line-digital-frontier"),
    ("978479262", "seirinkogeisha"),
    ("978478754", "square-enix"),
    ("978478753", "square-enix"),
    ("978478752", "square-enix"),
    ("978478751", "square-enix"),
    ("978478750", "square-enix"),
    ("978483874", "magazine-house"),
    ("978483873", "magazine-house"),
    ("978483872", "magazine-house"),
    ("978483871", "magazine-house"),
    ("978480197", "tatsumi"),
    ("978480198", "tatsumi"),
    ("978480199", "takeshobo"),
    ("978480192", "takeshobo"),
    ("978480193", "takeshobo"),
    ("978480194", "takeshobo"),
    ("978480195", "takeshobo"),
    ("978482116", "bunkasha"),
    ("978482113", "bunkasha"),
    ("978482111", "bunkasha"),
    ("978483224", "houbunsha"),
    ("978483222", "houbunsha"),
    ("978483223", "houbunsha"),
    ("978483444", "gentosha-comics"),
    ("978483447", "gentosha-comics"),
    ("978483449", "gentosha-comics"),
    ("9784592", "hakusensha"),
    ("9784253", "akita"),
    ("9784408", "jitsugyo-no-nihon"),
    ("9784403", "shinshokan"),
    ("9784480", "chikuma-shobo"),
    ("9784537", "nihon-bungeisha"),
    ("9784575", "futabasha"),
    ("9784396", "shodensha"),
    ("9784596", "harpercollins-japan"),
    ("9784344", "gentosha"),
    ("978404", "kadokawa"),
    ("9784091", "shogakukan"),
    ("9784093", "shogakukan"),
    ("9784092", "shogakukan"),
    ("9784094", "shogakukan"),
    ("9784099", "shogakukan"),
    ("9784065", "kodansha"),
    ("9784063", "kodansha"),
    ("9784061", "kodansha"),
    ("9784062", "kodansha"),
    ("9784064", "kodansha"),
    ("9784066", "kodansha"),
    ("9784068", "kodansha"),
    ("9784069", "kodansha"),
    ("9784088", "shueisha"),
    ("9784087", "shueisha"),
    ("9784086", "shueisha"),
    ("9784085", "shueisha"),
    ("9784084", "shueisha"),
    ("9784083", "shueisha"),
    ("9784082", "shueisha"),
    ("9784081", "shueisha"),
    ("9784080", "shueisha"),
]


def infer_publisher_from_isbn(isbn: str | None) -> str | None:
    """ISBN-13 prefix から publisher を 推定。"""
    if not isbn:
        return None
    s = re.sub(r"[^0-9]", "", isbn)
    if len(s) != 13:
        return None
    for prefix, pub in ISBN_PUBLISHER_PREFIXES:
        if s.startswith(prefix):
            return pub
    return None

# pykakasi kakasi 初期化 (= グローバル に 1 回)
_KKS = pykakasi.kakasi()


def kana_to_slug(kana: str | None) -> str:
    """カタカナ / ひらがな → slug 形式 ローマ字 (= 小文字 + hyphen 区切り)。

    space で 分割し、 各 part を pykakasi で hepburn ローマ字化。
    非 [a-z0-9] は strip、 part 内 で 連結。 part 同士は hyphen で 結合。

    e.g. 'シンゲキ ノ キョジン' → 'shingeki-no-kyojin'
    e.g. 'ランマニブンノイチ' → 'ranmanibunnoichi' (= space なしで 連結)
    """
    if not kana:
        return ""
    parts = [p for p in re.split(r"[\s　・]+", kana) if p]
    romaji_parts: list[str] = []
    for p in parts:
        result = _KKS.convert(p)
        rom = "".join(r["hepburn"] for r in result).lower()
        rom = re.sub(r"[^a-z0-9]", "", rom)
        if rom:
            romaji_parts.append(rom)
    return "-".join(romaji_parts)


def title_to_romaji(kana: str | None) -> str:
    """title_romaji 生成 (= 全小文字 + space 区切り)。"""
    if not kana:
        return ""
    parts = [p for p in re.split(r"[\s　・]+", kana) if p]
    romaji_parts: list[str] = []
    for p in parts:
        result = _KKS.convert(p)
        rom = "".join(r["hepburn"] for r in result).lower()
        rom = re.sub(r"[^a-z0-9]", "", rom)
        if rom:
            romaji_parts.append(rom)
    return " ".join(romaji_parts)


def title_passes_filter(title: str) -> bool:
    if not title:
        return False
    for pat in DROP_TITLE_PATTERNS:
        if title.startswith(pat):
            return False
    for pat in DROP_TITLE_CONTAINS:
        if pat in title:
            return False
    return True


def select_candidates(con: sqlite3.Connection, limit: int) -> list[dict]:
    """完結 推定 series を 抽出。 ranking 順 で limit 件 返す。"""
    cur = con.cursor()
    cur.row_factory = sqlite3.Row
    types_in = ",".join("?" for _ in KEEP_EDITION_TYPES)
    rows = cur.execute(
        f"""
        SELECT s.id, s.title, s.subtitle, s.title_kana, s.subtitle_kana, s.qid,
               s.adult_score, s.source, s.series_key,
               MAX(v.release_date) AS last_date,
               MIN(v.release_date) AS first_date,
               COUNT(DISTINCT v.id) AS vol_count
        FROM series s
        JOIN editions e ON e.series_id = s.id
        JOIN volumes v ON v.edition_id = e.id
        WHERE s.adult_score < 3
          AND e.type IN ({types_in})
          AND v.release_date IS NOT NULL
          AND v.number > 0
        GROUP BY s.id
        HAVING vol_count >= 5
           AND SUBSTR(last_date, 1, 4) <= '2020'
        ORDER BY (CASE WHEN s.qid IS NOT NULL THEN 100 ELSE 0 END) + vol_count DESC
        LIMIT ?
        """,
        list(KEEP_EDITION_TYPES) + [limit * 5],  # 5x で 取得 後 filter
    ).fetchall()
    out = []
    seen_titles = set()
    for r in rows:
        if not title_passes_filter(r["title"]):
            continue
        if not r["title_kana"]:
            continue  # kana 必須
        # 同一作品 (= main + orphan + kana 表記揺れ) は 1 件 のみ
        # 簡易 dedup key: (title_kana_normalized, vol_count) で 似た series を merge
        kana_norm = re.sub(r"[\s　]", "", r["title_kana"] or "")
        key = (kana_norm, r["title"])
        if key in seen_titles:
            continue
        seen_titles.add(key)
        out.append(dict(r))
        if len(out) >= limit:
            break
    return out


def build_yml_for_candidate(
    con: sqlite3.Connection,
    cand: dict,
    seed3: dict,
    valid_pubs: set,
    valid_mags: set,
    valid_gens: set,
    related_finder,
    editions_loader,
    authors_loader,
) -> dict | None:
    """1 candidate を yml dict に。"""
    series_row = cand  # cand already has all needed fields
    related_ids = related_finder(con, series_row)
    editions = editions_loader(con, related_ids)
    if not editions:
        return None
    authors = authors_loader(con, series_row["id"])
    seed_entry = seed3.get(series_row["series_key"])

    # title_kana strip space (= 必須 field、 空なら skip)
    raw_kana = series_row.get("title_kana") or ""
    title_kana = re.sub(r"[\s　]+", "", raw_kana)
    if not title_kana:
        return None  # title_kana 不明 → skip
    title_romaji = title_to_romaji(raw_kana)
    if not title_romaji:
        return None  # title_romaji 推定不能 → skip

    # subtitle 空 でも edition 名 strip 不要 (= 種3 直接出力)
    sub = series_row.get("subtitle")
    EDITION_NAME_SUBTITLES = {"新装再編版", "新装版", "完全版", "愛蔵版", "文庫版",
                              "ワイド版", "デラックス", "新装新版", "リニューアル版",
                              "廉価版", "新装版コミックス", "復刻版"}
    if sub and sub in EDITION_NAME_SUBTITLES:
        sub = None

    # year
    all_years = []
    for ed in editions:
        for v in ed["volumes"]:
            d = v.get("release_date")
            if d and len(d) >= 4:
                try:
                    all_years.append(int(d[:4]))
                except ValueError:
                    pass
    year_started = min(all_years) if all_years else 2000
    year_ended = None
    if editions:
        first_ed_years = []
        for v in editions[0]["volumes"]:
            d = v.get("release_date")
            if d and len(d) >= 4:
                try:
                    first_ed_years.append(int(d[:4]))
                except ValueError:
                    pass
        first_ed_years.sort()
        while len(first_ed_years) > 5:
            if first_ed_years[-1] - first_ed_years[-2] > 5:
                first_ed_years.pop()
            else:
                break
        if first_ed_years:
            year_ended = max(first_ed_years)

    status = (seed_entry or {}).get("status") or "completed"  # 抽出時点で 完結扱い
    if status == "ongoing":
        year_ended = None

    writers, originals = [], []
    for a in authors:
        if a["role"] == "original_author":
            originals.append({"name": a["name"], "role": "writer"})
        else:
            writers.append({"name": a["name"], "role": a["role"]})
    if not writers:
        writers = [{"name": "(unknown)", "role": "writer_artist"}]

    pub_cand = (seed_entry or {}).get("publisher")
    if pub_cand and valid_pubs and pub_cand not in valid_pubs:
        pub_cand = None
    # ISBN prefix から publisher 推定 (= 種3 fill 漏れ 補完)
    if not pub_cand:
        for ed in editions:
            for v in ed["volumes"]:
                p = infer_publisher_from_isbn(v.get("isbn13"))
                if p and (not valid_pubs or p in valid_pubs):
                    pub_cand = p
                    break
            if pub_cand:
                break

    mag_cand = (seed_entry or {}).get("magazine")
    if mag_cand and valid_mags and mag_cand not in valid_mags:
        mag_cand = None

    demographic = (seed_entry or {}).get("demographic") or "shounen"

    genres_cand = (seed_entry or {}).get("genres") or ["drama"]
    if valid_gens:
        filtered = [g for g in genres_cand if g in valid_gens]
        genres_cand = filtered or ["drama"]

    o: dict = {
        "slug": cand["__slug__"],
        "title": series_row["title"],
        "title_kana": title_kana,
        "title_romaji": title_romaji,
    }
    if sub:
        o["subtitle"] = sub
        if series_row.get("subtitle_kana"):
            o["subtitle_kana"] = re.sub(r"[\s　]+", "", series_row["subtitle_kana"])
    o["year_started"] = year_started
    o["year_ended"] = year_ended
    o["status"] = status
    o["authors"] = writers
    o["original_authors"] = originals
    if not pub_cand:
        return None  # publisher 推定不能 → skip
    o["publisher"] = pub_cand
    o["magazine"] = mag_cand
    o["demographic"] = demographic
    o["genres"] = genres_cand
    o["synopsis"] = (seed_entry or {}).get("synopsis") or ""
    anime_adapted = (seed_entry or {}).get("anime_adapted")
    if anime_adapted is not None:
        o["anime_adapted"] = anime_adapted
    if series_row.get("qid"):
        o["wikidata_qid"] = series_row["qid"]

    # editions 出力 (= type/label/imprint/volumes 構造)
    cleaned_eds = []
    for ed in editions:
        vols_out = []
        for v in ed["volumes"]:
            vo = {"number": v["number"]}
            if v.get("volume_label"):
                vo["volume_label"] = v["volume_label"]
            vo["asin"] = v.get("asin")
            vo["isbn13"] = str(v["isbn13"]) if v.get("isbn13") else None
            vo["cover_url"] = v.get("cover_url")
            vo["release_date"] = v.get("release_date") or None
            vols_out.append(vo)
        ce = {"type": ed["type"], "label": ed.get("label")}
        if ed.get("imprint"):
            ce["imprint"] = ed["imprint"]
        ce["volumes"] = vols_out
        cleaned_eds.append(ce)
    o["editions"] = cleaned_eds
    return o


def main():
    import importlib.util
    # 既存 promote logic を import (= find_related_series_ids, get_editions_with_volumes, get_authors)
    spec = importlib.util.spec_from_file_location("p", ROOT / "scripts" / "_promote-bulk-v2.py")
    pm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pm)

    print(f"loading {SEED3} ...", file=sys.stderr)
    with SEED3.open("r", encoding="utf-8") as f:
        d = yaml.safe_load(f)
    seed3 = {e["key"]: e for e in d["series"]}
    print(f"  entries: {len(seed3)}", file=sys.stderr)

    valid_pubs, valid_mags, valid_gens = pm.load_master_keys()
    print(
        f"  master: pubs={len(valid_pubs)} mags={len(valid_mags)} gens={len(valid_gens)}",
        file=sys.stderr,
    )

    con = sqlite3.connect(DB)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for p in OUT_DIR.glob("*.yml"):
        p.unlink()

    print(f"[step 1] parent_map 構築...", file=sys.stderr)
    parent_map = pm.build_parent_map(con)
    print(f"  spinoff: {len(parent_map)}", file=sys.stderr)

    print(f"[step 2] 候補抽出...", file=sys.stderr)
    cands = select_candidates(con, TARGET_COUNT)
    print(f"  候補: {len(cands)}", file=sys.stderr)

    # spinoff drop
    cands = [c for c in cands if c["id"] not in parent_map or c["vol_count"] >= 10]
    print(f"  spinoff 除外後: {len(cands)}", file=sys.stderr)

    # slug 自動生成 + 重複 handling
    print(f"[step 3] slug 生成...", file=sys.stderr)
    slug_count: dict[str, int] = defaultdict(int)
    for c in cands:
        base_slug = kana_to_slug(c["title_kana"])
        if not base_slug:
            # title から ASCII 部分 抽出 fallback
            base_slug = re.sub(r"[^a-z0-9]+", "-", (c["title"] or "").lower()).strip("-")
        if not base_slug:
            base_slug = f"series-{c['id']}"
        slug_count[base_slug] += 1
        if slug_count[base_slug] == 1:
            c["__slug__"] = base_slug
        else:
            c["__slug__"] = f"{base_slug}-{slug_count[base_slug]}"

    print(f"[step 4] yml 生成...", file=sys.stderr)
    stats = {"written": 0, "no_editions": 0}
    for i, c in enumerate(cands):
        if i % 200 == 0:
            print(f"  progress: {i}/{len(cands)}", file=sys.stderr)
        try:
            yml_dict = build_yml_for_candidate(
                con, c, seed3, valid_pubs, valid_mags, valid_gens,
                pm.find_related_series_ids,
                pm.get_editions_with_volumes,
                pm.get_authors,
            )
        except Exception as e:
            print(f"  ❌ {c['title']!r}: {e}", file=sys.stderr)
            continue
        if not yml_dict:
            stats["no_editions"] += 1
            continue
        out_path = OUT_DIR / f"{c['__slug__']}.yml"
        with out_path.open("w", encoding="utf-8") as f:
            f.write("# Auto-generated by scripts/_extract-top-completed.py\n")
            yaml.dump(yml_dict, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        stats["written"] += 1

    print(f"\n=== stats ===", file=sys.stderr)
    for k, v in stats.items():
        print(f"  {k}: {v}", file=sys.stderr)
    print(f"\nwrote {stats['written']} yml to {OUT_DIR}", file=sys.stderr)


if __name__ == "__main__":
    main()
