"""B 残り 5 件 + inuyasha の yml 中身検証 (= 別作品リスクチェック)。"""
import re
from pathlib import Path

TARGETS = [
    "hagane-no-renkinjutsushi",
    "jojo-no-kimyouna-bouken",
    "kimetsu-no-yaiba",
    "shingeki-no-kyojin",
    "kyoukai-no-rinne",
    "inuyasha-tetsusaiga",
]


def parse(slug: str) -> dict:
    p = Path(f"data/manga/{slug}.yml")
    if not p.exists():
        return {}
    text = p.read_text(encoding="utf-8")
    d = {}
    for key in ["title", "title_kana", "year_started", "year_ended", "status", "wikidata_qid"]:
        m = re.search(rf"^{key}:\s*(.+?)\s*$", text, re.M)
        if m:
            d[key] = m.group(1)
    auth = re.search(r"^- name:\s*(.+?)\s*$", text, re.M)
    d["author"] = auth.group(1) if auth else ""
    alt = re.search(r"^  en:\s*(.+?)\s*$", text, re.M)
    d["alt_en"] = alt.group(1) if alt else ""
    syn = re.search(r"^synopsis:\s*(.+?)\s*$", text, re.M)
    d["synopsis"] = syn.group(1)[:80] if syn else ""
    d["volumes"] = len(re.findall(r"^  - number:", text, re.M))
    return d


print(f"| slug 現状 | title | 作者 | qid | 期間 | 巻数 | alt_en (= 期待 en slug) | synopsis 冒頭 |")
print("|---|---|---|---|---|---|---|---|")
for slug in TARGETS:
    d = parse(slug)
    period = f"{d.get('year_started', '?')}-{d.get('year_ended', '?')}"
    new_slug = ""
    en = d.get("alt_en", "")
    if en:
        s = en.strip().replace("×", "x")
        s = re.sub(r"['!?.,]", "", s)
        s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
        new_slug = re.sub(r"-+", "-", s).strip("-")
    print(f"| {slug} | {d.get('title','')} | {d.get('author','')} | {d.get('wikidata_qid','')} | {period} | {d.get('volumes',0)} | {en} (= {new_slug}) | {d.get('synopsis','')} |")
