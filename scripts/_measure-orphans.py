"""metadata101 個別 book を metadata104 cluster に紐づけ試行し、
orphan (= 紐づかない book) の規模 + cluster 数を 実測する。

linkage rule:
  - parsed_label (= ` : ` 副題分離後の base title) が一致
  - creator name (= 主要 1 名) が一致
  - 補助: brand 一致 (= cluster の records[].brand と)

orphan の grouping:
  - (parsed_label, creator_name) で grouping = 自前で series cluster 化した時の単位
  - top N サンプル表示
"""

import json
import re
import sys
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
META101 = ROOT / ".cache" / "madb" / "metadata101-clean.json"
META104_CLUSTERS = ROOT / ".cache" / "series-v2.json"


def get_label(name):
    if not name:
        return ""
    if isinstance(name, list) and name:
        first = name[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("@value", "")
    return name if isinstance(name, str) else ""


def parse_label(label: str) -> tuple[str, str]:
    if not label:
        return "", ""
    t = label.strip()
    if " = " in t:
        t = t.split(" = ", 1)[0].strip()
    if " : " in t:
        b, y = t.split(" : ", 1)
        return b.strip(), y.strip()
    return t, ""


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


def main():
    print(f"loading {META104_CLUSTERS} ...", file=sys.stderr)
    with META104_CLUSTERS.open("r", encoding="utf-8") as f:
        v2 = json.load(f)
    clusters = v2["clusters"]

    # cluster lookup key: (base, subtitle, creator_qid_or_name)
    cluster_lookup: dict[tuple[str, str, str], dict] = {}
    cluster_lookup_name_only: dict[tuple[str, str, str], dict] = {}
    for c in clusters:
        # 各 cluster の 紐づけ key 候補:
        # (title, subtitle, creator name from records)
        for r in c["madb_records"]:
            for nm in r["creator_names_all"]:
                key = (c["title"], c["subtitle"], nm)
                cluster_lookup[key] = c
                # name only (= 副題 ignore)
                cluster_lookup_name_only[(c["title"], nm)] = c

    print(f"clusters: {len(clusters)}", file=sys.stderr)
    print(f"linkage keys: {len(cluster_lookup)}", file=sys.stderr)

    print(f"loading {META101} ...", file=sys.stderr)
    with META101.open("r", encoding="utf-8") as f:
        data101 = json.load(f)
    print(f"books: {len(data101['@graph'])}", file=sys.stderr)

    linked = 0
    orphan = 0
    no_creator = 0
    no_label = 0
    orphan_groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)

    for b in data101["@graph"]:
        label = get_label(b.get("schema:name"))
        if not label:
            no_label += 1
            continue
        base, sub = parse_label(label)
        if not base:
            no_label += 1
            continue
        names = extract_creator_names(b.get("schema:creator", ""))
        if not names:
            no_creator += 1
            continue
        # name → cluster lookup (= 副題込みで 厳格 match)
        matched = False
        for nm in names:
            if (base, sub, nm) in cluster_lookup:
                matched = True
                break
            # 副題 ignore でも 試す
            if (base, nm) in cluster_lookup_name_only:
                matched = True
                break
        if matched:
            linked += 1
        else:
            orphan += 1
            # orphan grouping key: (base, sub, primary creator)
            orphan_groups[(base, sub, names[0])].append(
                {
                    "isbn": b.get("schema:isbn", ""),
                    "label": label,
                    "vol": b.get("schema:volumeNumber", ""),
                    "date": b.get("schema:datePublished", ""),
                }
            )

    print("\n=== orphan 規模 ===")
    print(f"  total books     : {len(data101['@graph']):>7}")
    print(f"  linked          : {linked:>7}  ({linked*100/len(data101['@graph']):.1f}%)")
    print(f"  orphan          : {orphan:>7}  ({orphan*100/len(data101['@graph']):.1f}%)")
    print(f"  no label        : {no_label:>7}")
    print(f"  no creator      : {no_creator:>7}")
    print(f"\n  orphan groups (= 自前で 補完 cluster 化必要) : {len(orphan_groups):>7}")

    # orphan group の 規模分布
    sizes = Counter(len(books) for books in orphan_groups.values())
    print(f"\n=== orphan group size 分布 ===")
    for n in sorted(sizes.keys())[:15]:
        print(f"  {n:>3} books × {sizes[n]:>6} groups")

    # top orphan groups (= 大きい順)
    print(f"\n=== top 20 orphan groups (= 巻数最多) ===")
    top = sorted(orphan_groups.items(), key=lambda x: -len(x[1]))[:20]
    for (base, sub, creator), books in top:
        print(f"  {len(books):>4} books  base={base!r:.40} sub={sub!r:.20} creator={creator!r:.20}")

    # 既知の メジャー作品 chk
    print(f"\n=== 既知メジャー作品の linkage 確認 ===")
    probes = [
        ("HUNTER×HUNTER", "", "冨樫義博"),
        ("半妖の夜叉姫", "", "高橋留美子"),
        ("ハンター×ハンター", "", "冨樫義博"),
        ("うる星やつら", "", "高橋留美子"),
        ("らんま1/2", "", "高橋留美子"),
    ]
    for base, sub, creator in probes:
        key = (base, sub, creator)
        if key in cluster_lookup:
            print(f"  ✅ linked  : {base!r} sub={sub!r}")
        else:
            orphan_size = len(orphan_groups.get(key, []))
            print(f"  ❌ orphan  : {base!r} sub={sub!r} (= {orphan_size} books)")


if __name__ == "__main__":
    main()
