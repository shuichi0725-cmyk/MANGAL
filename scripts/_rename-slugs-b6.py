"""B 6 件 = 訳語採用 or 本編 slug 修正 を 一括 rename + alias 追加。"""
from __future__ import annotations

import re
from pathlib import Path

MANGA_DIR = Path("data/manga")
ALIAS_FILE = Path("data/slug-aliases.yml")

RENAMES = [
    ("hagane-no-renkinjutsushi", "fullmetal-alchemist"),
    ("jojo-no-kimyouna-bouken", "jojos-bizarre-adventure"),
    ("kimetsu-no-yaiba", "demon-slayer"),
    ("shingeki-no-kyojin", "attack-on-titan"),
    ("kyoukai-no-rinne", "rin-ne"),
    ("inuyasha-tetsusaiga", "inuyasha"),
]


def main() -> None:
    aliases: dict[str, str] = {}
    if ALIAS_FILE.exists():
        for line in ALIAS_FILE.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^(\S+):\s*(.+)$", line)
            if m:
                aliases[m.group(1)] = m.group(2).strip()

    for old, new in RENAMES:
        old_path = MANGA_DIR / f"{old}.yml"
        new_path = MANGA_DIR / f"{new}.yml"
        if not old_path.exists():
            print(f"  [skip] {old_path} 不在")
            continue
        if new_path.exists():
            print(f"  [skip] {new_path} 既存 = 衝突")
            continue
        text = old_path.read_text(encoding="utf-8")
        new_text = re.sub(rf"^slug:\s*{re.escape(old)}\s*$", f"slug: {new}", text, count=1, flags=re.M)
        if new_text == text:
            print(f"  [warn] slug field 置換 失敗: {old}")
        new_path.write_text(new_text, encoding="utf-8")
        old_path.unlink()
        aliases[old] = new
        print(f"  [ok] {old} → {new}")

    out_lines = [
        "# 旧 slug → 新 slug の alias mapping。",
        "# Next.js middleware で 旧 URL を 新 URL に 301 redirect する用。",
        "",
    ]
    for k in sorted(aliases):
        out_lines.append(f"{k}: {aliases[k]}")
    ALIAS_FILE.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"\nwrote: {ALIAS_FILE} ({len(aliases)} aliases)")


if __name__ == "__main__":
    main()
