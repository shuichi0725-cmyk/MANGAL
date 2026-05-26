"""Phase 1 = 種2 sqlite から 種3 yml への フリガナ 自動 inject JSON 生成。

対象 = 種3 ∩ 種2 join 成功 で 種2 kana が ok / space カテゴリな entry
       (= 56,777 件 + subtitle 該当分)。

null カテゴリ (= 19,620 件) は Phase 2 (= AI fill) で別途。
MISSING カテゴリ (= 38 件) は 別途 cleanup。

出力 = data/seeds/_fills/phase1-kana-auto.json (= _apply-fills.ts で 適用可能形式)

形式:
{
  "key1": {"title_kana": "...", "title_kana_segmented": "..."},
  ...
}
"""
from __future__ import annotations
import sqlite3
import yaml
import json
import re
from pathlib import Path

DB = Path(".cache/db-v2.sqlite")
SEED3 = Path("data/seeds/series-supplement-v2.yml")
OUT = Path("data/seeds/_fills/phase1-kana-auto.json")

HAS_SPACE = re.compile(r"[\s　]")


def to_kana_pair(raw: str | None) -> tuple[str | None, str | None]:
    """raw kana (= MADB ja-hrkt) を (title_kana, title_kana_segmented) に変換。

    - null → (None, None) = skip
    - space あり → スペース除去 + 元、 両方
    - スペースなし → 元、 元 (= 同値、 1単語扱い)
    """
    if raw is None:
        return (None, None)
    raw_stripped = raw.strip()
    if not raw_stripped:
        return (None, None)
    if HAS_SPACE.search(raw_stripped):
        no_space = re.sub(r"[\s　]+", "", raw_stripped)
        return (no_space, raw_stripped)
    return (raw_stripped, raw_stripped)


def main():
    print(f"=== 種3 yml load ===")
    with SEED3.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    seed3_keys = set(e["key"] for e in data.get("series", []))
    print(f"  種3 keys: {len(seed3_keys):,}")

    print(f"=== 種2 sqlite load ===")
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT series_key, title, title_kana, subtitle, subtitle_kana "
        "FROM series WHERE title_kana IS NOT NULL OR subtitle_kana IS NOT NULL"
    ).fetchall()
    print(f"  種2 kana あり row: {len(rows):,}")

    print(f"=== fill JSON 生成 ===")
    fills = {}
    n_title_only = 0
    n_subtitle = 0
    n_both = 0
    n_skip_no_seed3 = 0
    for r in rows:
        key = r["series_key"]
        if key not in seed3_keys:
            n_skip_no_seed3 += 1
            continue
        t_kana, t_seg = to_kana_pair(r["title_kana"])
        s_kana, s_seg = to_kana_pair(r["subtitle_kana"])
        entry = {}
        if t_kana:
            entry["title_kana"] = t_kana
            entry["title_kana_segmented"] = t_seg
        if s_kana:
            entry["subtitle_kana"] = s_kana
            entry["subtitle_kana_segmented"] = s_seg
        if not entry:
            continue
        fills[key] = entry
        if t_kana and s_kana:
            n_both += 1
        elif t_kana:
            n_title_only += 1
        else:
            n_subtitle += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(fills, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  title のみ: {n_title_only:,}")
    print(f"  subtitle のみ: {n_subtitle:,}")
    print(f"  両方: {n_both:,}")
    print(f"  total fills: {len(fills):,}")
    print(f"  skipped (= 種3 にない): {n_skip_no_seed3:,}")
    print(f"  wrote {OUT}")


if __name__ == "__main__":
    main()
