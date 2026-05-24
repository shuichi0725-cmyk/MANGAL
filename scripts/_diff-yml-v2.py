"""data/manga/ vs data/manga.v2/ の 主要 field diff レポート 出力。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

OLD = Path("data/manga")
NEW = Path("data/manga.v2")
OUT = Path(".cache/yml-diff-v2.md")


def parse_yml(p: Path) -> dict:
    """yml の 主要 field と 巻数を 簡易 parse (= 全 yml load 重いので 必要 field のみ)。"""
    if not p.exists():
        return {}
    text = p.read_text(encoding="utf-8")
    d = {}
    for key in ["slug", "title", "title_kana", "title_romaji", "year_started", "year_ended",
                "status", "publisher", "magazine", "demographic"]:
        m = re.search(rf"^{key}:\s*(.+?)\s*$", text, re.M)
        if m:
            d[key] = m.group(1)
    # 巻数 = `- number:` 行 count
    d["volumes"] = len(re.findall(r"^  - number:", text, re.M))
    # editions = `- type:` 行 count
    d["editions"] = len(re.findall(r"^- type:", text, re.M))
    # authors = `- name:` 行 count (= authors セクション内)
    auth_m = re.search(r"^authors:\n((?:- .+\n(?:  .+\n)*)+)", text, re.M)
    d["authors"] = len(re.findall(r"^- name:", auth_m.group(1), re.M)) if auth_m else 0
    # alt_en
    alt_m = re.search(r"^  en:\s*(.+?)\s*$", text, re.M)
    if alt_m:
        d["alt_en"] = alt_m.group(1)
    return d


def main() -> None:
    new_files = sorted(NEW.glob("*.yml"))
    old_files_set = {p.name for p in OLD.glob("*.yml")}
    new_files_set = {p.name for p in new_files}

    only_new = new_files_set - old_files_set
    only_old = old_files_set - new_files_set
    common = sorted(old_files_set & new_files_set)

    lines = []
    lines.append("# yml diff report (= data/manga vs data/manga.v2)")
    lines.append("")
    lines.append(f"- 旧 only: {len(only_old)} 件")
    lines.append(f"- 新 only: {len(only_new)} 件")
    lines.append(f"- 両方: {len(common)} 件")
    lines.append("")

    if only_old:
        lines.append(f"## 旧 only (= 削除候補) {sorted(only_old)}")
        lines.append("")
    if only_new:
        lines.append(f"## 新 only (= 追加候補) {sorted(only_new)}")
        lines.append("")

    lines.append("## 主要 field diff 一覧")
    lines.append("")
    lines.append("| file | title_kana | volumes | editions | year_ended | status | publisher | alt_en |")
    lines.append("|---|---|---|---|---|---|---|---|")

    diff_count = {"title_kana": 0, "volumes": 0, "year_ended": 0, "status": 0,
                  "publisher": 0, "alt_en": 0}
    no_diff = 0

    for fn in common:
        old = parse_yml(OLD / fn)
        new = parse_yml(NEW / fn)
        cells = []
        has_diff = False
        for key in ["title_kana", "volumes", "editions", "year_ended", "status", "publisher", "alt_en"]:
            o = old.get(key, "")
            n = new.get(key, "")
            if o != n:
                cells.append(f"**{o}** → **{n}** ★")
                has_diff = True
                if key in diff_count:
                    diff_count[key] += 1
            else:
                cells.append(str(n) if n else "-")
        if not has_diff:
            no_diff += 1
            continue
        cell_str = " | ".join(cells)
        lines.append(f"| {fn} | {cell_str} |")

    lines.append("")
    lines.append(f"## サマリ")
    lines.append("")
    lines.append(f"- 全 {len(common)} 件 中 diff あり: {len(common) - no_diff}")
    lines.append(f"- diff なし: {no_diff}")
    lines.append("")
    lines.append("### field 別 diff 件数")
    lines.append("")
    for k, c in diff_count.items():
        lines.append(f"- {k}: {c}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote: {OUT}", file=sys.stderr)
    print(f"diff あり: {len(common) - no_diff} / {len(common)}", file=sys.stderr)


if __name__ == "__main__":
    main()
