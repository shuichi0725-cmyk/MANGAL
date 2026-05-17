"""metadata104 を 全件 load → cluster 化 → .cache/series-v2.json 出力。

cluster 化 ロジック (= path B'):
  - 各 MADB series record (= C25xxxx) を 以下の key で 集約:
      (qid, base_title, subtitle)
  - 同じ key の records は 1 user-facing series (= edition variants として 統合)

抽出ロジック:
  - creator: schema:creator (= '[著]高橋留美子' 等) から 名前抽出
            → mangaka.csv で name + alt_names match → qid 解決
  - base_title + subtitle: rdfs:label の ` : ` で split (= 副題込みで identity)
  - title_kana: schema:name の ja-hrkt entry から (= 最初の カタカナ)
  - title_official_en: schema:alternateName から ASCII のみ entry を 選択

入力:
  - .cache/madb/metadata104.json (= 139,130 series records)
  - data/seed/mangaka.csv (= 6,751 mangaka with qid)

出力:
  - .cache/series-v2.json (= 全 cluster の dict array)
  - stats: cluster 数 / qid 解決率 / 副題分離数 等を stderr に
"""

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
META104 = ROOT / ".cache" / "madb" / "metadata104.json"
MANGAKA_CSV = ROOT / "data" / "seed" / "mangaka.csv"
OUT = ROOT / ".cache" / "series-v2.json"


def load_mangaka_map() -> dict[str, dict]:
    """name (+ alt_names) → mangaka info (qid, name, has_adult_credit)"""
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
    """'[著]高橋留美子' '[原作]X / [漫画]Y' '[著]X∥xxxx' '[原作]X, Y' 等から 名前 list 抽出。"""
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
    # ' / ' (= space slash space) または ', ' で 複数著者分割
    parts = re.split(r"\s*[/,]\s+", s)
    names = []
    for chunk in parts:
        # 役職 tag '[著]' '[原作]' 等を 剥がす
        chunk = re.sub(r"^\[[^\]]+\]\s*", "", chunk)
        # ∥ (= U+2225) 以降 (= 振り仮名) を 落とす
        if "∥" in chunk:
            chunk = chunk.split("∥", 1)[0]
        # 全/半角スペース trim
        chunk = chunk.strip().rstrip(",").strip()
        # 末尾 「[ほか]」「[ほか作画]」 等のメタ tag を 剥がす
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
    """schema:name[0] = 主題 (= 副題込みの日本語題)"""
    if not name_arr:
        return ""
    first = name_arr[0]
    if isinstance(first, str):
        return first
    if isinstance(first, dict):
        return first.get("@value", "")
    return ""


def get_kana_from_name(name_arr) -> str:
    """schema:name の ja-hrkt language tag の中で 最初の katakana を 採用。"""
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
        # カタカナ含むなら 採用 (= 「URUSEI YATSURA」 は ローマ字 で skip、 「ウルセイ ヤツラ」 を 取る)
        if re.search(r"[ァ-ヿ]", v):
            return v
    return ""


def get_official_en(alt_name) -> str:
    """schema:alternateName から ASCII のみの 1 つを 採用。"""
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
        # ASCII の英数記号のみ ?
        if re.match(r"^[A-Za-z0-9\s\-\!\?\.\,\:\;\/\&\(\)']+$", v):
            return v
    return ""


def parse_label(label: str) -> tuple[str, str]:
    """rdfs:label → (base, subtitle)
    ` : ` で 副題分離。 ` = ` 以降は (= 英語題) 剥がす。
    巻番号 (` 第N巻` etc.) は metadata104 では 普通含まれないので 簡易処理。
    """
    if not label:
        return "", ""
    t = label.strip()
    # ` = ` 以降 strip (= 英語題は alternateName 側で取る)
    if " = " in t:
        t = t.split(" = ", 1)[0].strip()
    # 副題 ` : Y` 分離
    if " : " in t:
        b, y = t.split(" : ", 1)
        return b.strip(), y.strip()
    return t, ""


def get_qid_id(b) -> str:
    c = b.get("dcterms:creator", {})
    if isinstance(c, dict):
        return c.get("@id", "").split("/")[-1]
    return ""


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


def main():
    print(f"loading mangaka.csv ...", file=sys.stderr)
    mangaka = load_mangaka_map()
    print(f"  mangaka name → qid: {len(mangaka)} entries", file=sys.stderr)

    print(f"loading metadata104 ...", file=sys.stderr)
    with META104.open("r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"  MADB series records: {len(data['@graph'])}", file=sys.stderr)

    # cluster: (qid, base, subtitle) → list of MADB records
    clusters: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    no_qid_records: list[dict] = []  # qid 解決失敗
    stats = {
        "total_series_records": 0,
        "qid_resolved": 0,
        "qid_unresolved": 0,
        "no_creator": 0,
        "no_label": 0,
    }

    for b in data["@graph"]:
        stats["total_series_records"] += 1
        rdfs = b.get("rdfs:label", "")
        if not rdfs:
            stats["no_label"] += 1
            continue
        base, subtitle = parse_label(rdfs)
        if not base:
            stats["no_label"] += 1
            continue

        # creator 解決
        creator_names = extract_creator_names(b.get("schema:creator", ""))
        if not creator_names:
            stats["no_creator"] += 1
            continue
        # 最初に hit する creator の qid を採用
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
            # fallback: 作家名 (= 最初の name) を qid 代用 identifier に
            matched_name = creator_names[0]

        # cluster に 追加
        name_arr = get_name_array(b.get("schema:name"))
        record = {
            "madb_id": b.get("schema:identifier"),
            "rdfs_label": rdfs,
            "name_primary": get_primary_label(name_arr),
            "name_array": name_arr,
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
        # cluster key: qid あれば qid、 なければ creator_name で 区別
        creator_id_part = qid if qid else f"name:{matched_name}"
        clusters[(creator_id_part, base, subtitle)].append(record)

    # cluster を list 化、 各 cluster で 集約値生成
    clusters_out = []
    for (creator_id_part, base, sub), records in clusters.items():
        # title_kana: records の最頻値 (= 副題 と同じ logic)
        from collections import Counter
        kana_counter = Counter(r["title_kana"] for r in records if r["title_kana"])
        title_kana = kana_counter.most_common(1)[0][0] if kana_counter else ""
        # subtitle_kana: 各 record の ` : ` 右側 kana
        sub_kanas = []
        for r in records:
            tk = r["title_kana"]
            if " : " in tk:
                sub_kanas.append(tk.split(" : ", 1)[1].strip())
        sub_kana = Counter(sub_kanas).most_common(1)[0][0] if sub_kanas else ""
        # title_kana から ` : ` 以降剥がす
        if " : " in title_kana:
            title_kana = title_kana.split(" : ", 1)[0].strip()

        # official_en: 最頻値
        en_counter = Counter(r["official_en"] for r in records if r["official_en"])
        official_en = en_counter.most_common(1)[0][0] if en_counter else ""

        # series_key (= qid あり / なし で分岐)
        # qid 取得は cluster 単位ではなく records[0] の qid を 採用 (= 同 cluster は同 creator)
        first_rec = records[0]
        creator_qid = first_rec["creator_qid"]
        creator_name = first_rec["creator_name_matched"]
        if creator_qid:
            id_part = f"qid:{creator_qid}"
        else:
            id_part = f"name:{creator_name}"
        if sub:
            series_key = f"{id_part}|name:{base}|sub:{sub}"
        else:
            series_key = f"{id_part}|name:{base}"

        # adult flag: いずれかの record で 「成年コミック」 なら true
        is_adult = any(
            "成年" in (r["content_rating"] or "") for r in records
        )

        clusters_out.append(
            {
                "series_key": series_key,
                "qid": creator_qid,             # 解決済 qid (= 無ければ "")
                "creator_name": creator_name,   # name fallback 用
                "title": base,
                "subtitle": sub,
                "title_kana": title_kana,
                "subtitle_kana": sub_kana,
                "title_official_en": official_en,
                "is_adult": is_adult,
                "madb_records": records,
                "n_madb_records": len(records),
            }
        )

    # 出力 sort: qid → base → subtitle
    clusters_out.sort(key=lambda c: (c["qid"] or "zzz", c["title"], c["subtitle"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(
            {"clusters": clusters_out, "stats": stats},
            f,
            ensure_ascii=False,
            indent=2,
        )

    # stats を stderr へ
    print("\n=== stats ===", file=sys.stderr)
    print(f"  total series records   : {stats['total_series_records']:>7}", file=sys.stderr)
    print(f"  qid resolved           : {stats['qid_resolved']:>7}", file=sys.stderr)
    print(f"  qid unresolved (= log) : {stats['qid_unresolved']:>7}", file=sys.stderr)
    print(f"  no creator             : {stats['no_creator']:>7}", file=sys.stderr)
    print(f"  no label               : {stats['no_label']:>7}", file=sys.stderr)
    print(f"  clusters (= 新 series) : {len(clusters_out):>7}", file=sys.stderr)
    # 副題持ち cluster
    with_sub = sum(1 for c in clusters_out if c["subtitle"])
    print(f"  cluster with subtitle  : {with_sub:>7}", file=sys.stderr)
    print(f"\nwrote {OUT}", file=sys.stderr)

    # 旧 種2 series 数 と 比較
    try:
        import sqlite3
        c = sqlite3.connect(ROOT / ".cache" / "db.sqlite")
        cur = c.cursor()
        cur.execute("SELECT COUNT(*) FROM series")
        old = cur.fetchone()[0]
        print(f"\n  (reference) old 種 2 series rows: {old}", file=sys.stderr)
        # qid resolution rate も
        cur.execute("SELECT COUNT(*) FROM series WHERE qid IS NOT NULL")
        old_qid = cur.fetchone()[0]
        print(f"  (reference) old qid 解決済   : {old_qid}", file=sys.stderr)
    except Exception:
        pass


if __name__ == "__main__":
    main()
