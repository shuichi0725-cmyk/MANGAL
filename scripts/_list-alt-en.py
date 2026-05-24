"""data/manga/*.yml の alt_en 一覧 を 出力 (= ユーザ目視 audit 用)。"""
import re
from pathlib import Path

DIR = Path("data/manga")
OUT = Path(".cache/alt-en-list.md")


def parse(p: Path) -> dict:
    text = p.read_text(encoding="utf-8")
    d = {}
    for key in ["slug", "title", "title_kana", "wikidata_qid"]:
        m = re.search(rf"^{key}:\s*(.+?)\s*$", text, re.M)
        if m:
            d[key] = m.group(1)
    alt = re.search(r"^  en:\s*(.+?)\s*$", text, re.M)
    d["alt_en"] = alt.group(1) if alt else ""
    # author
    auth = re.search(r"^- name:\s*(.+?)\s*$", text, re.M)
    d["author"] = auth.group(1) if auth else ""
    return d


lines = []
lines.append("# data/manga/*.yml alt_en 一覧 (= ユーザ目視 audit 用)")
lines.append("")
lines.append(f"対象 = data/manga/ 全 yml ({len(list(DIR.glob('*.yml')))} 件)")
lines.append("")
lines.append("判定凡例:")
lines.append("- OK = alt_en そのまま")
lines.append("- 修正 = 別 値に 書換 (= 修正案 記入)")
lines.append("- 削除 = alt_en 削除 (= slug は kana fallback)")
lines.append("")
lines.append("| # | slug 現状 | title (= 漢字) | 作者 | qid | alt_en (= 現状) | 判定 | 修正案 |")
lines.append("|---|---|---|---|---|---|---|---|")

entries = []
for f in sorted(DIR.glob("*.yml")):
    d = parse(f)
    entries.append(d)

for i, d in enumerate(entries, 1):
    slug = d.get("slug", "")
    title = d.get("title", "")
    author = d.get("author", "")
    qid = d.get("wikidata_qid", "")
    alt_en = d.get("alt_en", "(なし)")
    lines.append(f"| {i} | {slug} | {title} | {author} | {qid} | {alt_en} |  |  |")

lines.append("")
lines.append(f"## サマリ")
lines.append("")
lines.append(f"- 全件: {len(entries)}")
lines.append(f"- alt_en あり: {sum(1 for d in entries if d.get('alt_en') and d['alt_en'] != '(なし)')}")
lines.append(f"- alt_en なし: {sum(1 for d in entries if not d.get('alt_en') or d['alt_en'] == '(なし)')}")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"wrote: {OUT}")
print(f"entries: {len(entries)}")
