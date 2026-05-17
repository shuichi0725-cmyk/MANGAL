"""新種2 build (= path B' option A hybrid)

Phase 1: metadata104 を 全件 load → cluster 化 (= series identity の source of truth)
Phase 2: metadata101 個別 book を 各 cluster に linkage
Phase 3: 紐づかない orphan books を baseTitle で 自前集約 → 補完 cluster
Phase 4: 合体 → .cache/series-v2.json

cluster 化 ロジック (= Phase 1):
  - 各 MADB series record (= C25xxxx) を 以下の key で 集約:
      (creator_id_or_name, base_title, subtitle)
  - 同じ key の records は 1 user-facing series (= edition variants として 統合)

linkage ルール (= Phase 2):
  - book を (base, subtitle, creator name) で cluster lookup
  - 副題 ignore でも 試す (= 補助)

orphan 集約 ルール (= Phase 3):
  - book の (parsed_label, subtitle, primary creator) で grouping
  - 副題分離は path B' のルール 適用 (= bare ` : ` で 別作品扱い)

抽出ロジック:
  - creator: schema:creator (= '[著]高橋留美子' 等) から 名前抽出
            → mangaka.csv で name + alt_names match → qid 解決
  - base_title + subtitle: rdfs:label / schema:name の ` : ` で split
  - title_kana: schema:name の ja-hrkt entry から
  - title_official_en: schema:alternateName から ASCII のみ entry を 選択
"""

import csv
import json
import re
import sys
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
META104 = ROOT / ".cache" / "madb" / "metadata104.json"
META101 = ROOT / ".cache" / "madb" / "metadata101-clean.json"
MANGAKA_CSV = ROOT / "data" / "seed" / "mangaka.csv"
OUT = ROOT / ".cache" / "series-v2.json"


def load_mangaka_map() -> dict[str, dict]:
    name_map: dict[str, dict] = {}
    with MANGAKA_CSV.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            info = {
                "qid": row["qid"],
                "name": row["name"],
                "has_adult": row.get("has_adult_credit", "false").lower() == "true",
            }
            name_map[row["name"]] = info
            for alt in (row.get("alt_names") or "").split("|"):
                alt = alt.strip()
                if alt and alt not in name_map:
                    name_map[alt] = info
    return name_map


def extract_creator_names(schema_creator) -> list[str]:
    if not schema_creator:
        return []
    if isinstance(schema_creator, list):
        s = schema_creator[0] if schema_creator else ""
    else:
        s = schema_creator
    if isinstance(s, dict):
        s = s.get("@value", "")
    if not isinstance(s, str):
        return []
    parts = re.split(r"\s*[/,]\s+", s)
    names = []
    for chunk in parts:
        chunk = re.sub(r"^\[[^\]]+\]\s*", "", chunk)
        if "∥" in chunk:
            chunk = chunk.split("∥", 1)[0]
        chunk = chunk.strip().rstrip(",").strip()
        chunk = re.sub(r"\s*\[[^\]]+\]\s*$", "", chunk).strip()
        if chunk:
            names.append(chunk)
    return names


def get_name_array(schema_name) -> list:
    if not schema_name:
        return []
    if isinstance(schema_name, list):
        return schema_name
    return [schema_name]


def get_primary_label(name_arr) -> str:
    if not name_arr:
        return ""
    first = name_arr[0]
    if isinstance(first, str):
        return first
    if isinstance(first, dict):
        return first.get("@value", "")
    return ""


def get_kana_from_name(name_arr) -> str:
    if not name_arr:
        return ""
    for item in name_arr[1:]:
        if not isinstance(item, dict):
            continue
        if item.get("@language") != "ja-hrkt":
            continue
        v = item.get("@value", "")
        if not v:
            continue
        if re.search(r"[ァ-ヿ]", v):
            return v
    return ""


def get_official_en(alt_name) -> str:
    if not alt_name:
        return ""
    if not isinstance(alt_name, list):
        alt_name = [alt_name]
    for item in alt_name:
        if isinstance(item, dict):
            v = item.get("@value", "")
        else:
            v = item
        if not isinstance(v, str) or not v:
            continue
        if re.match(r"^[A-Za-z0-9\s\-\!\?\.\,\:\;\/\&\(\)']+$", v):
            return v
    return ""


def parse_label(label: str) -> tuple[str, str]:
    """rdfs:label → (base, subtitle)。 ` = ` 以降 strip、 ` : ` で 副題分離。"""
    if not label:
        return "", ""
    t = label.strip()
    if " = " in t:
        t = t.split(" = ", 1)[0].strip()
    if " : " in t:
        b, y = t.split(" : ", 1)
        return b.strip(), y.strip()
    return t, ""


def get_brand_label(b) -> str:
    br = b.get("schema:brand", "")
    if isinstance(br, list) and br:
        first = br[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("@value", "")
        return ""
    return br if isinstance(br, str) else ""


def get_isbn(b) -> str:
    isbn = b.get("schema:isbn", "")
    if isinstance(isbn, list):
        isbn = isbn[0] if isbn else ""
    return str(isbn or "")


def get_vol(b) -> str:
    vol = b.get("schema:volumeNumber", "") or ""
    if isinstance(vol, list):
        vol = vol[0] if vol else ""
    return str(vol or "")


# =============================================================================
# Phase 1: metadata104 → clusters
# =============================================================================

def build_metadata104_clusters(mangaka: dict) -> tuple[list[dict], dict]:
    print(f"[phase 1] loading {META104} ...", file=sys.stderr)
    with META104.open("r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"  MADB series records: {len(data['@graph'])}", file=sys.stderr)

    clusters: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    stats = {
        "total_madb104": 0,
        "qid_resolved": 0,
        "qid_unresolved": 0,
        "no_creator": 0,
        "no_label": 0,
    }
    for b in data["@graph"]:
        stats["total_madb104"] += 1
        rdfs = b.get("rdfs:label", "")
        if not rdfs:
            stats["no_label"] += 1
            continue
        base, subtitle = parse_label(rdfs)
        if not base:
            stats["no_label"] += 1
            continue
        creator_names = extract_creator_names(b.get("schema:creator", ""))
        if not creator_names:
            stats["no_creator"] += 1
            continue
        qid = ""
        matched_name = ""
        for nm in creator_names:
            if nm in mangaka:
                qid = mangaka[nm]["qid"]
                matched_name = nm
                break
        if qid:
            stats["qid_resolved"] += 1
        else:
            stats["qid_unresolved"] += 1
            matched_name = creator_names[0]

        name_arr = get_name_array(b.get("schema:name"))
        record = {
            "madb_id": b.get("schema:identifier"),
            "rdfs_label": rdfs,
            "title_kana": get_kana_from_name(name_arr),
            "official_en": get_official_en(b.get("schema:alternateName")),
            "creator_qid": qid,
            "creator_name_matched": matched_name,
            "creator_names_all": creator_names,
            "brand": get_brand_label(b),
            "date_published": b.get("schema:datePublished", ""),
            "number_of_items": b.get("schema:numberOfItems", 0),
            "content_rating": b.get("schema:contentRating", ""),
        }
        cluster_key_part = qid if qid else f"name:{matched_name}"
        clusters[(cluster_key_part, base, subtitle)].append(record)

    # cluster → output dict
    clusters_out = []
    for (_, base, sub), records in clusters.items():
        kana_counter = Counter(r["title_kana"] for r in records if r["title_kana"])
        title_kana = kana_counter.most_common(1)[0][0] if kana_counter else ""
        sub_kanas = []
        for r in records:
            tk = r["title_kana"]
            if " : " in tk:
                sub_kanas.append(tk.split(" : ", 1)[1].strip())
        sub_kana = Counter(sub_kanas).most_common(1)[0][0] if sub_kanas else ""
        if " : " in title_kana:
            title_kana = title_kana.split(" : ", 1)[0].strip()

        en_counter = Counter(r["official_en"] for r in records if r["official_en"])
        official_en = en_counter.most_common(1)[0][0] if en_counter else ""

        first_rec = records[0]
        creator_qid = first_rec["creator_qid"]
        creator_name = first_rec["creator_name_matched"]
        id_part = f"qid:{creator_qid}" if creator_qid else f"name:{creator_name}"
        if sub:
            series_key = f"{id_part}|name:{base}|sub:{sub}"
        else:
            series_key = f"{id_part}|name:{base}"

        is_adult = any("成年" in (r["content_rating"] or "") for r in records)

        clusters_out.append({
            "series_key": series_key,
            "source": "madb104",
            "qid": creator_qid,
            "creator_name": creator_name,
            "title": base,
            "subtitle": sub,
            "title_kana": title_kana,
            "subtitle_kana": sub_kana,
            "title_official_en": official_en,
            "is_adult": is_adult,
            "madb_records": records,
            "n_madb_records": len(records),
            "books": [],
        })

    return clusters_out, stats


# =============================================================================
# Phase 2 + 3: metadata101 link + orphan aggregate
# =============================================================================

def link_and_aggregate(clusters: list[dict], mangaka: dict) -> dict:
    print(f"[phase 2/3] loading {META101} ...", file=sys.stderr)
    with META101.open("r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"  books: {len(data['@graph'])}", file=sys.stderr)

    # lookup index for Phase 1 clusters
    # key: (base, subtitle, creator_name) → cluster index
    cluster_idx: dict[tuple[str, str, str], int] = {}
    cluster_idx_no_sub: dict[tuple[str, str], int] = {}
    for i, c in enumerate(clusters):
        for r in c["madb_records"]:
            for nm in r["creator_names_all"]:
                cluster_idx.setdefault((c["title"], c["subtitle"], nm), i)
                cluster_idx_no_sub.setdefault((c["title"], nm), i)

    stats = {
        "total_books": 0,
        "linked": 0,
        "orphan_books": 0,
        "no_label": 0,
        "no_creator": 0,
    }
    orphan_groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)

    for b in data["@graph"]:
        stats["total_books"] += 1
        label = get_primary_label(get_name_array(b.get("schema:name")))
        if not label:
            stats["no_label"] += 1
            continue
        base, sub = parse_label(label)
        if not base:
            stats["no_label"] += 1
            continue
        names = extract_creator_names(b.get("schema:creator", ""))
        if not names:
            stats["no_creator"] += 1
            continue
        # ISBN normalize は 後段 (= sqlite 投入時) で。 ここでは生 ISBN 保持。
        book_record = {
            "isbn": get_isbn(b),
            "vol": get_vol(b),
            "date": b.get("schema:datePublished", ""),
            "brand": get_brand_label(b),
            "label": label,
            "creator_names": names,
        }
        # linkage 試行
        matched_idx = None
        for nm in names:
            if (base, sub, nm) in cluster_idx:
                matched_idx = cluster_idx[(base, sub, nm)]
                break
            if (base, nm) in cluster_idx_no_sub:
                matched_idx = cluster_idx_no_sub[(base, nm)]
                break
        if matched_idx is not None:
            clusters[matched_idx]["books"].append(book_record)
            stats["linked"] += 1
        else:
            # orphan group key: (base, sub, primary creator)
            orphan_groups[(base, sub, names[0])].append(book_record)
            stats["orphan_books"] += 1

    # orphan → cluster 化
    orphan_out = []
    for (base, sub, creator), books in orphan_groups.items():
        qid = mangaka.get(creator, {}).get("qid", "")
        id_part = f"qid:{qid}" if qid else f"name:{creator}"
        if sub:
            series_key = f"{id_part}|name:{base}|sub:{sub}|source:orphan"
        else:
            series_key = f"{id_part}|name:{base}|source:orphan"
        # title_kana: 各 book に kana が無いので 空。 後で 別 source で 補強想定
        # adult: book level の contentRating は metadata101 で 存在するなら拾う
        orphan_out.append({
            "series_key": series_key,
            "source": "orphan101",
            "qid": qid,
            "creator_name": creator,
            "title": base,
            "subtitle": sub,
            "title_kana": "",
            "subtitle_kana": "",
            "title_official_en": "",
            "is_adult": False,  # TODO: book level rating で 判定
            "madb_records": [],
            "n_madb_records": 0,
            "books": books,
            "n_orphan_books": len(books),
        })

    stats["orphan_clusters"] = len(orphan_out)
    return {
        "stats": stats,
        "orphan_clusters": orphan_out,
        "clusters_with_books": clusters,
    }


# =============================================================================
# Main
# =============================================================================

def main():
    print(f"loading mangaka.csv ...", file=sys.stderr)
    mangaka = load_mangaka_map()
    print(f"  mangaka name → qid: {len(mangaka)} entries", file=sys.stderr)

    # Phase 1
    clusters, p1_stats = build_metadata104_clusters(mangaka)
    print(f"\n[phase 1 stats]", file=sys.stderr)
    for k, v in p1_stats.items():
        print(f"  {k}: {v}", file=sys.stderr)
    print(f"  clusters: {len(clusters)}", file=sys.stderr)

    # Phase 2 + 3
    out = link_and_aggregate(clusters, mangaka)
    print(f"\n[phase 2/3 stats]", file=sys.stderr)
    for k, v in out["stats"].items():
        print(f"  {k}: {v}", file=sys.stderr)

    # combine
    all_clusters = out["clusters_with_books"] + out["orphan_clusters"]
    all_clusters.sort(key=lambda c: (c["source"], c["qid"] or "zzz", c["title"], c["subtitle"]))

    final_stats = {
        "phase1_madb104": p1_stats,
        "phase2_3_link": out["stats"],
        "total_clusters": len(all_clusters),
        "clusters_from_madb104": sum(1 for c in all_clusters if c["source"] == "madb104"),
        "clusters_from_orphan": sum(1 for c in all_clusters if c["source"] == "orphan101"),
        "clusters_with_books_attached": sum(1 for c in all_clusters if c["books"]),
        "clusters_no_books": sum(1 for c in all_clusters if not c["books"]),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump({"clusters": all_clusters, "stats": final_stats}, f, ensure_ascii=False, indent=2)

    print(f"\n=== final stats ===", file=sys.stderr)
    for k, v in final_stats.items():
        if isinstance(v, dict):
            print(f"  {k}:", file=sys.stderr)
            for kk, vv in v.items():
                print(f"    {kk}: {vv}", file=sys.stderr)
        else:
            print(f"  {k}: {v}", file=sys.stderr)
    print(f"\nwrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
