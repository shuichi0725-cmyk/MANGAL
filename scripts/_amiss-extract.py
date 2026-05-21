"""A-miss 候補抽出: seed3 の カタカナ含む + en 未fill entries 全件。

完結/連載問わず全件対象 (= 本番 DB は全漫画掲載のため)。

出力: .cache/amiss/input.json (= [{title, key}, ...])
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED3 = ROOT / "data" / "seeds" / "series-supplement-v2.yml"
OUT = ROOT / ".cache" / "amiss" / "input.json"

KATA = re.compile(r"[゠-ヿㇰ-ㇿ]")


def extract_title(key: str) -> str:
    names = re.findall(r"name:([^|]+?)(?:\||$)", key)
    return names[-1] if names else key


def main():
    text = SEED3.read_text(encoding="utf-8")
    entries = []
    cur_key = None
    cur_has_en = False
    in_alt_titles = False

    for line in text.splitlines():
        m = re.match(r"^  - key:\s*(.+)$", line)
        if m:
            if cur_key is not None:
                title = extract_title(cur_key)
                if KATA.search(title) and not cur_has_en:
                    entries.append({"title": title, "key": cur_key})
            cur_key = m.group(1).strip()
            cur_has_en = False
            in_alt_titles = False
            continue
        if re.match(r"^    alternative_titles:", line):
            in_alt_titles = True
            continue
        if re.match(r"^    \S", line):
            in_alt_titles = False
        if in_alt_titles:
            me = re.match(r"^\s+en:\s*(.+)$", line)
            if me:
                v = me.group(1).strip().strip("\"'")
                if v and v not in ("null", "~", ""):
                    cur_has_en = True

    if cur_key is not None:
        title = extract_title(cur_key)
        if KATA.search(title) and not cur_has_en:
            entries.append({"title": title, "key": cur_key})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"A-miss 合計: {len(entries):,}件", file=sys.stderr)
    print(f"wrote: {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
