"""kaitai-chain-strong.csv から data/seeds/series-merge.yml を 生成。

graph 構築:
  各 (new, old) ペア を 双方向 edge として扱い、 connected component を 抽出。
  → 1 component = 1 cluster (= 同一作品の改題群)

main (= 親) 選定 logic:
  1. qid 持つ row > qid なし
  2. volumes 数 多い > 少ない
  3. それでも 同点 = title 文字数 短い順 (= 原則 元シリーズ名 短い)

出力形式:
  - main: <親 title>
    aliases:
      - <子 title 1>
      - <子 title 2>
    note: |
      MADB ma:note 由来の根拠
"""
from __future__ import annotations
import csv
import sqlite3
from pathlib import Path
import yaml

SRC = Path(".cache/kaitai-chain-strong.csv")
DB = Path(".cache/db-v2.sqlite")
OUT = Path("data/seeds/series-merge.yml")


def find_root(node: str, parent_of: dict[str, str]) -> str:
    """union-find: 根まで辿る。"""
    while parent_of[node] != node:
        parent_of[node] = parent_of[parent_of[node]]  # path compression
        node = parent_of[node]
    return node


def union(a: str, b: str, parent_of: dict[str, str]) -> None:
    ra, rb = find_root(a, parent_of), find_root(b, parent_of)
    if ra != rb:
        parent_of[ra] = rb


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing: {SRC}")

    # CSV 読込
    pairs: list[tuple[str, str, str, str]] = []  # (new, old, madb_id, note)
    with SRC.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pairs.append((row["new_name"], row["old_name"], row["madb_id"], row["note"]))

    if not pairs:
        print("(no strong pairs)")
        return

    # 全 node + union-find
    nodes = set()
    for new, old, *_ in pairs:
        nodes.add(new)
        nodes.add(old)
    parent_of = {n: n for n in nodes}
    for new, old, *_ in pairs:
        union(new, old, parent_of)

    # cluster 集約
    clusters: dict[str, set[str]] = {}
    for n in nodes:
        r = find_root(n, parent_of)
        clusters.setdefault(r, set()).add(n)

    # DB から 各 title の (qid, volume count) を 取得 → main 選定
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    def title_meta(t: str) -> tuple[int, int, int]:
        """(has_qid 0/1, total volumes, -len_title) を 返す。 sort key: 降順。"""
        rows = con.execute(
            "SELECT s.id, s.qid FROM series s WHERE s.title=?", (t,)
        ).fetchall()
        if not rows:
            return (0, 0, -len(t))
        has_qid = 1 if any(r["qid"] for r in rows) else 0
        sids = [r["id"] for r in rows]
        ph = ",".join("?" * len(sids))
        vol_count = con.execute(
            f"SELECT COUNT(*) FROM volumes v "
            f"JOIN editions e ON e.id=v.edition_id "
            f"WHERE e.series_id IN ({ph})",
            sids,
        ).fetchone()[0]
        return (has_qid, vol_count, -len(t))

    # cluster note まとめ (= 全 source の madb_id + note 結合)
    cluster_notes: dict[str, list[str]] = {}
    for new, old, madb_id, note in pairs:
        r = find_root(new, parent_of)
        cluster_notes.setdefault(r, []).append(f"{madb_id}: {note}")

    out_entries = []
    for root, members in sorted(clusters.items(), key=lambda x: x[0]):
        sorted_members = sorted(members, key=title_meta, reverse=True)
        main_title = sorted_members[0]
        aliases = sorted_members[1:]
        entry = {
            "main": main_title,
            "aliases": aliases,
        }
        note_lines = cluster_notes.get(root, [])
        # dedupe note
        seen = set()
        unique_notes = []
        for n in note_lines:
            if n not in seen:
                seen.add(n)
                unique_notes.append(n)
        entry["note"] = "\n".join(unique_notes)
        out_entries.append(entry)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# 改題 chain による series 統合定義。\n"
        "# 種2 sqlite は不変、 audit script + 本番 yml 生成時に lookup する mapping のみ。\n"
        "# 自動生成元: scripts/_gen-series-merge.py (= kaitai-chain-strong.csv 由来)\n"
        "# 各 entry: main = 統合先 (= 検索性/知名度高い親 title)、 aliases = 統合元 子 title 配列。\n"
        "#\n"
    )
    with OUT.open("w", encoding="utf-8") as f:
        f.write(header)
        yaml.dump(out_entries, f, allow_unicode=True, sort_keys=False, width=200)

    print(f"wrote: {OUT}")
    print(f"clusters: {len(out_entries)}")
    for e in out_entries:
        print(f"  main='{e['main']}'  aliases={e['aliases']}")


if __name__ == "__main__":
    main()
