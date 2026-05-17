"""新 sqlite (= .cache/db-v2.sqlite) を 初期化する。

- 既存 .cache/db-v2.sqlite があれば backup (= .bak-YYYYMMDD-HHMMSS) して 再作成
- db/schema-v2.sql を 適用
- mangaka.csv / publishers.yml / magazines.yml を seed
  (= 既存 .cache/db.sqlite から 移し替えるのが 安全)
"""

import csv
import shutil
import sqlite3
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "db" / "schema-v2.sql"
DB_NEW = ROOT / ".cache" / "db-v2.sqlite"
DB_OLD = ROOT / ".cache" / "db.sqlite"
MANGAKA_CSV = ROOT / "data" / "seed" / "mangaka.csv"
PUBLISHERS_YML = ROOT / "data" / "publishers.yml"
MAGAZINES_YML = ROOT / "data" / "magazines.yml"


def backup_old(path: Path) -> Path | None:
    if not path.exists():
        return None
    stamp = time.strftime("%Y%m%d-%H%M%S")
    bak = path.with_suffix(path.suffix + f".bak-{stamp}")
    shutil.copy2(path, bak)
    return bak


def apply_schema(db: sqlite3.Connection) -> None:
    with SCHEMA.open("r", encoding="utf-8") as f:
        sql = f.read()
    db.executescript(sql)


def seed_publishers(db: sqlite3.Connection) -> int:
    if not PUBLISHERS_YML.exists():
        return 0
    with PUBLISHERS_YML.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    n = 0
    for key, val in data.items():
        if not isinstance(val, dict):
            continue
        name = val.get("name", key)
        db.execute(
            "INSERT OR IGNORE INTO publishers (key, name) VALUES (?, ?)",
            (key, name),
        )
        n += 1
    return n


def seed_magazines(db: sqlite3.Connection) -> int:
    if not MAGAZINES_YML.exists():
        return 0
    with MAGAZINES_YML.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    n = 0
    for key, val in data.items():
        if not isinstance(val, dict):
            continue
        db.execute(
            "INSERT OR IGNORE INTO magazines (key, name, publisher, demographic) VALUES (?, ?, ?, ?)",
            (key, val.get("name", key), val.get("publisher", ""), val.get("demographic", "shounen")),
        )
        n += 1
    return n


def seed_mangaka(db: sqlite3.Connection) -> int:
    if not MANGAKA_CSV.exists():
        return 0
    n = 0
    with MANGAKA_CSV.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            db.execute(
                """INSERT OR IGNORE INTO mangaka
                   (qid, name, birth_year, death_year, alt_names, has_adult_credit)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    row["qid"],
                    row["name"],
                    int(row["birth_year"]) if row.get("birth_year") else None,
                    int(row["death_year"]) if row.get("death_year") else None,
                    row.get("alt_names") or None,
                    1 if row.get("has_adult_credit", "false").lower() == "true" else 0,
                ),
            )
            n += 1
    return n


def main():
    print(f"target: {DB_NEW}", file=sys.stderr)
    bak = backup_old(DB_NEW)
    if bak:
        print(f"  backed up old → {bak.name}", file=sys.stderr)
    if DB_NEW.exists():
        DB_NEW.unlink()
        print(f"  removed old db-v2.sqlite", file=sys.stderr)

    print(f"applying schema: {SCHEMA}", file=sys.stderr)
    db = sqlite3.connect(DB_NEW)
    db.row_factory = sqlite3.Row
    apply_schema(db)
    db.commit()

    n_pub = seed_publishers(db)
    n_mag = seed_magazines(db)
    n_mk = seed_mangaka(db)
    db.commit()

    # 確認
    cur = db.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r["name"] for r in cur.fetchall()]
    cur.execute("SELECT value FROM meta WHERE key='schema_version'")
    ver = cur.fetchone()
    print(f"\n=== init complete ===", file=sys.stderr)
    print(f"  schema_version : {ver['value'] if ver else '?'}", file=sys.stderr)
    print(f"  tables ({len(tables)}): {', '.join(tables)}", file=sys.stderr)
    print(f"  seeded publishers : {n_pub}", file=sys.stderr)
    print(f"  seeded magazines  : {n_mag}", file=sys.stderr)
    print(f"  seeded mangaka    : {n_mk}", file=sys.stderr)

    # series 列確認 (= v2 新規 columns)
    cur.execute("PRAGMA table_info(series)")
    cols = [r["name"] for r in cur.fetchall()]
    print(f"\n  series columns ({len(cols)}):", file=sys.stderr)
    for c in cols:
        marker = "★" if c in ("subtitle", "subtitle_kana", "title_official_en", "madb_series_ids", "source") else "  "
        print(f"    {marker} {c}", file=sys.stderr)
    cur.execute("PRAGMA table_info(editions)")
    cols = [r["name"] for r in cur.fetchall()]
    print(f"\n  editions columns ({len(cols)}):", file=sys.stderr)
    for c in cols:
        marker = "★" if c == "madb_series_id" else "  "
        print(f"    {marker} {c}", file=sys.stderr)
    cur.execute("PRAGMA table_info(volumes)")
    cols = [r["name"] for r in cur.fetchall()]
    print(f"\n  volumes columns ({len(cols)}):", file=sys.stderr)
    for c in cols:
        marker = "★" if c == "volume_label" else "  "
        print(f"    {marker} {c}", file=sys.stderr)

    db.close()


if __name__ == "__main__":
    main()
