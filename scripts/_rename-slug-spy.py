"""supai-fuamirii → spy-x-family rename + alias 追加 (= L3 Phase C 後の 追加 rename)。"""
import re
from pathlib import Path

MANGA_DIR = Path("data/manga")
ALIAS_FILE = Path("data/slug-aliases.yml")

OLD, NEW = "supai-fuamirii", "spy-x-family"

old_path = MANGA_DIR / f"{OLD}.yml"
new_path = MANGA_DIR / f"{NEW}.yml"

text = old_path.read_text(encoding="utf-8")
new_text = re.sub(rf"^slug:\s*{re.escape(OLD)}\s*$", f"slug: {NEW}", text, count=1, flags=re.M)
new_path.write_text(new_text, encoding="utf-8")
old_path.unlink()
print(f"  [ok] {OLD} → {NEW}")

# alias 追加
aliases: dict[str, str] = {}
for line in ALIAS_FILE.read_text(encoding="utf-8").splitlines():
    m = re.match(r"^(\S+):\s*(.+)$", line)
    if m:
        aliases[m.group(1)] = m.group(2).strip()
aliases[OLD] = NEW

out_lines = [
    "# 旧 slug → 新 slug の alias mapping。",
    "# Next.js middleware で 旧 URL を 新 URL に 301 redirect する用。",
    "",
]
for k in sorted(aliases):
    out_lines.append(f"{k}: {aliases[k]}")
ALIAS_FILE.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
print(f"  wrote: {ALIAS_FILE} ({len(aliases)} aliases)")
