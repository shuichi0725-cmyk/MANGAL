"""Phase 2 todo list 生成 = 種3 で title_kana なし な entry を 全部抽出。

出力 = data/seeds/_fills/phase2-todo.json
形式 = [{key, title, subtitle, qid, alt_en, synopsis, demographic, genres}, ...]

加えて = data/seeds/_fills/phase2-unknown.json (= 空 array 初期化、 skip 一覧 累積用)
"""
from __future__ import annotations
import sqlite3
import yaml
import json
import re
from pathlib import Path

DB = Path(".cache/db-v2.sqlite")
SEED3 = Path("data/seeds/series-supplement-v2.yml")
TODO = Path("data/seeds/_fills/phase2-todo.json")
UNKNOWN = Path("data/seeds/_fills/phase2-unknown.json")


def parse_seed3_key(key: str) -> tuple[str | None, str, str | None]:
    """種3 key を (qid, title, subtitle) に分解。
    形式: "qid:Q12345|name:タイトル|sub:サブ" or "name:著者|name:タイトル|sub:サブ"
    """
    parts = key.split("|")
    qid = None
    title = None
    subtitle = None
    name_parts = []
    for p in parts:
        if p.startswith("qid:"):
            qid = p[4:]
        elif p.startswith("name:"):
            name_parts.append(p[5:])
        elif p.startswith("sub:"):
            subtitle = p[4:]
    # name_parts の最後 = 作品 title (= 著者 が 前 に来る case あり)
    title = name_parts[-1] if name_parts else ""
    return qid, title, subtitle


def main():
    print(f"=== 種3 yml load ===")
    with SEED3.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    entries = data.get("series", [])
    print(f"  種3 entries: {len(entries):,}")

    print(f"=== 種2 sqlite load ===")
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    seed2_by_key = {}
    for r in con.execute("SELECT series_key, title, subtitle, title_kana FROM series").fetchall():
        seed2_by_key[r["series_key"]] = r

    print(f"=== todo 生成 ===")
    todo = []
    n_already_have = 0
    n_seed2_join = 0
    n_seed2_missing = 0
    for e in entries:
        key = e["key"]
        if e.get("title_kana"):
            n_already_have += 1
            continue
        # title / subtitle 取得 (= 種2 にあれば そちら 優先、 なければ key parse)
        s2 = seed2_by_key.get(key)
        if s2:
            title = s2["title"]
            subtitle = s2["subtitle"]
            n_seed2_join += 1
        else:
            qid, title, subtitle = parse_seed3_key(key)
            n_seed2_missing += 1
        qid_parsed, _, _ = parse_seed3_key(key)
        alt_en = None
        alt_titles = e.get("alternative_titles")
        if alt_titles and isinstance(alt_titles, dict):
            alt_en = alt_titles.get("en")
        todo.append({
            "key": key,
            "title": title,
            "subtitle": subtitle,
            "qid": qid_parsed,
            "alt_en": alt_en,
            "synopsis": e.get("synopsis"),
            "demographic": e.get("demographic"),
            "genres": e.get("genres"),
        })

    print(f"  既に title_kana あり (skip): {n_already_have:,}")
    print(f"  todo (= null + MISSING): {len(todo):,}")
    print(f"    うち 種2 join 成功: {n_seed2_join:,}")
    print(f"    うち 種2 にない (MISSING): {n_seed2_missing:,}")

    TODO.parent.mkdir(parents=True, exist_ok=True)
    TODO.write_text(json.dumps(todo, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  wrote {TODO}")

    if not UNKNOWN.exists():
        UNKNOWN.write_text("[]", encoding="utf-8")
        print(f"  initialized {UNKNOWN}")
    else:
        print(f"  {UNKNOWN} 既存、 skip")


if __name__ == "__main__":
    main()
