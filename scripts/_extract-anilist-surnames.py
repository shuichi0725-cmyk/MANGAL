"""AniList dump の staff から 著者native→姓ローマ字 を抽出 → .cache/anilist-author-surname.json。

CLAUDE.md slug規則の姓ソース「種a staff.full(「名 姓」順、 姓=最後の語)」を実体化。
role に 'Art'(作画)を含む方を優先(原作より作画家姓)。 長音は適用側で drop_long。
※調査/中間生成のみ。 gap c-1 (_gap-c1-suffix.py) が読む。
"""
import gzip
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DUMP = ROOT / ".cache" / "anilist-manga-dump-v3.jsonl.gz"
OUT = ROOT / ".cache" / "anilist-author-surname.json"


def surname(full):
    toks = re.findall(r"[A-Za-z'-]+", full)
    return re.sub(r"[^a-z]", "", toks[-1].lower()) if toks else ""


def main():
    nat2full, pref = {}, {}
    with gzip.open(DUMP, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            for e in (r.get("staff") or {}).get("edges", []):
                nm = e["node"]["name"]
                nat, full = nm.get("native"), nm.get("full")
                if not nat or not full:
                    continue
                role = e.get("role") or ""
                score = 2 if "Art" in role else (1 if "Story" in role else 0)
                if nat not in pref or score > pref[nat]:
                    pref[nat] = score
                    nat2full[nat] = full
    nat2sur = {k: surname(v) for k, v in nat2full.items() if surname(v)}
    OUT.write_text(json.dumps(nat2sur, ensure_ascii=False), encoding="utf-8")
    print(f"AniList 著者 native→姓romaji: {len(nat2sur):,} → {OUT.name}")


if __name__ == "__main__":
    main()
