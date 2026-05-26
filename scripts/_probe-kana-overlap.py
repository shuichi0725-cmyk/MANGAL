"""種3 ∩ 種2_kana_null の 重なり調査。

目的 = 種3 yml に title_kana / title_kana_segmented field を追加する とき、
★ 真の AI fill 対象 = 「種3 にある + 種2 で kana null な entry」 の件数を確認。

出力 = utf-8 ファイル (= console 文字化け 回避)。
"""
from __future__ import annotations
import sqlite3
import yaml
import re
from pathlib import Path
from collections import Counter

DB = Path(".cache/db-v2.sqlite")
SEED3 = Path("data/seeds/series-supplement-v2.yml")
OUT = Path(".cache/probe-kana-overlap.txt")

HAS_SPACE = re.compile(r"[\s　]")


def main():
    lines = []
    def p(s=""): lines.append(s)

    # === 種3 yml load ===
    p("=== 種3 yml load ===")
    with SEED3.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    seed3_entries = data.get("series", [])
    seed3_keys = set(e["key"] for e in seed3_entries)
    p(f"  種3 entries: {len(seed3_entries):,}")
    p(f"  ユニーク key: {len(seed3_keys):,}")
    p()

    # === 種2 sqlite load ===
    p("=== 種2 sqlite load ===")
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT series_key, title, title_kana, subtitle, subtitle_kana FROM series").fetchall()
    p(f"  種2 series 総数: {len(rows):,}")
    seed2_by_key = {r["series_key"]: r for r in rows}
    p()

    # === 重なり調査 ===
    p("=== 種3 entry の 種2 join 結果 ===")
    n_in_seed2 = 0
    n_not_in_seed2 = 0
    kana_status = Counter()
    samples = {"null": [], "space": [], "ok": [], "missing_in_seed2": []}
    for key in seed3_keys:
        r = seed2_by_key.get(key)
        if r is None:
            n_not_in_seed2 += 1
            kana_status["MISSING_IN_SEED2"] += 1
            if len(samples["missing_in_seed2"]) < 10:
                samples["missing_in_seed2"].append(key)
            continue
        n_in_seed2 += 1
        kana = r["title_kana"]
        if kana is None:
            kana_status["null"] += 1
            if len(samples["null"]) < 10:
                samples["null"].append((key, r["title"]))
        elif HAS_SPACE.search(kana):
            kana_status["space (= MADB 仕様)"] += 1
            if len(samples["space"]) < 5:
                samples["space"].append((key, r["title"], kana))
        else:
            kana_status["ok (= スペースなし)"] += 1
            if len(samples["ok"]) < 5:
                samples["ok"].append((key, r["title"], kana))

    p(f"  種3 entry のうち 種2 join 成功: {n_in_seed2:,}")
    p(f"  種3 entry のうち 種2 にない: {n_not_in_seed2:,}")
    p()
    p("  --- kana 状態 分布 ---")
    for k, v in kana_status.most_common():
        pct = v / len(seed3_keys) * 100
        p(f"    {k:<30}: {v:>7,} ({pct:>5.1f}%)")
    p()

    # === サンプル ===
    p("=== サンプル: 種3 ∩ 種2_kana_null (= ★ AI fill 対象) ===")
    for key, title in samples["null"]:
        p(f"  key={key}")
        p(f"    title={title!r}")
        p()
    p()
    p("=== サンプル: 種3 ∩ 種2_kana_space (= ★ 自動変換可能) ===")
    for key, title, kana in samples["space"]:
        p(f"  key={key}")
        p(f"    title={title!r}")
        p(f"    kana ={kana!r}")
        p()
    p()
    p("=== サンプル: 種3 ∩ 種2_kana_ok (= ★ そのまま) ===")
    for key, title, kana in samples["ok"]:
        p(f"  key={key}")
        p(f"    title={title!r}")
        p(f"    kana ={kana!r}")
        p()
    p()
    p("=== サンプル: 種3 にあるが 種2 にない (= ★ 異常、 もしくは MADB 削除済) ===")
    for key in samples["missing_in_seed2"]:
        p(f"  key={key}")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} ({len(lines)} lines)")


if __name__ == "__main__":
    main()
