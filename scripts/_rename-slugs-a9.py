"""A 9 件 (= カタカナ外来語 + alt_en あり) の slug を 自動 rename + alias 生成。

旧 slug → 新 slug:
  beruseruku → berserk
  buriichi → bleach
  desunooto → death-note
  doragon-booru → dragon-ball
  hantaa-hantaa → hunter-x-hunter
  kingudamu → kingdom
  mezon-ikkoku → maison-ikkoku
  wan-piisu → one-piece
  aoashi → ao-ashi

操作:
  1. data/manga/<旧>.yml の slug field 更新 + file rename
  2. data/slug-aliases.yml に 旧 → 新 を 追記 (= 新規 file 作成)
"""
from __future__ import annotations

import re
from pathlib import Path

MANGA_DIR = Path("data/manga")
ALIAS_FILE = Path("data/slug-aliases.yml")

RENAMES = [
    ("beruseruku", "berserk"),
    ("buriichi", "bleach"),
    ("desunooto", "death-note"),
    ("doragon-booru", "dragon-ball"),
    ("hantaa-hantaa", "hunter-x-hunter"),
    ("kingudamu", "kingdom"),
    ("mezon-ikkoku", "maison-ikkoku"),
    ("wan-piisu", "one-piece"),
    ("aoashi", "ao-ashi"),
]


def main() -> None:
    # 既存 alias 読み込み (= なければ 新規)
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
        # yml 内の slug field 更新
        text = old_path.read_text(encoding="utf-8")
        new_text = re.sub(rf"^slug:\s*{re.escape(old)}\s*$", f"slug: {new}", text, count=1, flags=re.M)
        if new_text == text:
            print(f"  [warn] slug field 置換 失敗: {old}")
        new_path.write_text(new_text, encoding="utf-8")
        old_path.unlink()
        aliases[old] = new
        print(f"  [ok] {old} → {new}")

    # alias yml 出力 (= sort 順)
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
