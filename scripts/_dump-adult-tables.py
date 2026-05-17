"""adult_publishers + adult_mangaka_known を sqlite から yml に dump する。

GitHub Actions の fetch-adult-lists.yml で 使用。
出力: data/seeds/adult-wikipedia-cache.yml

用途:
  scripts/fetch-adult-lists.ts (= Wikipedia 由来) で seed された 2 tables を、
  git 管理可能な yml に export する。 サンドボックス環境 (= Wikipedia 直接 fetch 不可)
  でも、 この cache yml を 経由して adult_publishers / adult_mangaka_known を
  再現できる。
"""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db.sqlite"  # fetch-adult-lists の出力先 (= 既定)
OUT = ROOT / "data" / "seeds" / "adult-wikipedia-cache.yml"


def main():
    if not DB.exists():
        print(f"ERROR: {DB} not found", file=sys.stderr)
        sys.exit(1)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    def fetch(tbl: str) -> list[dict]:
        cur.execute(f"SELECT * FROM {tbl} ORDER BY name")
        return [dict(r) for r in cur.fetchall()]

    publishers = fetch("adult_publishers")
    mangaka = fetch("adult_mangaka_known")
    print(f"adult_publishers: {len(publishers)} rows", file=sys.stderr)
    print(f"adult_mangaka_known: {len(mangaka)} rows", file=sys.stderr)

    lines = [
        "# data/seeds/adult-wikipedia-cache.yml",
        "# JA Wikipedia の 「成人向け漫画雑誌の一覧」 「日本の成人向け漫画家の一覧」 由来。",
        "# 生成: GitHub Actions fetch-adult-lists.yml (= scripts/fetch-adult-lists.ts +",
        "#       scripts/_dump-adult-tables.py)",
        "# 用途: scripts/_apply-adult-filter-v2.py が読込、 db-v2.sqlite に seed。",
        "",
        "schema_version: 1",
        "",
        "adult_publishers:",
    ]

    def yml_str(s: str) -> str:
        import re
        if re.match(r"^[\w\-\.]+$", s):
            return s
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'

    for r in publishers:
        lines.append(f"  - name: {yml_str(r['name'])}")
        lines.append(f"    source: {yml_str(r['source'])}")

    lines.append("")
    lines.append("adult_mangaka_known:")
    for r in mangaka:
        lines.append(f"  - name: {yml_str(r['name'])}")
        lines.append(f"    display: {yml_str(r['display'])}")
        lines.append(f"    source: {yml_str(r['source'])}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
