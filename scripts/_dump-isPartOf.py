"""指定 series_id に isPartOf する book record の rdfs:label 全件 list。"""
import re
import sys
from pathlib import Path

SRC = Path(".cache/madb/metadata101.json")
target = sys.argv[1] if len(sys.argv) > 1 else "C274933"

in_rec = False
buf: list[str] = []
matches: list[tuple[str, str]] = []

with SRC.open(encoding="utf-8") as f:
    for line in f:
        if line.startswith("    {"):
            in_rec = True
            buf = [line]
            continue
        if not in_rec:
            continue
        buf.append(line)
        if line.rstrip().startswith("    }"):
            text = "".join(buf)
            if f"id/{target}" in text:
                # isPartOf 内に target ある か 確認 (= 別 fieldの ID と 区別)
                m_part = re.search(rf'"schema:isPartOf":\s*\{{[^}}]*"@id":\s*"https://[^"]+/{target}"', text)
                if m_part:
                    m_label = re.search(r'"rdfs:label":\s*"((?:[^"\\]|\\.)*)"', text)
                    m_id = re.search(r'"@id":\s*"https://[^"]+/(M\d+)"', text)
                    if m_label and m_id:
                        matches.append((m_id.group(1), m_label.group(1)))
            in_rec = False

print(f"= isPartOf {target} = {len(matches)} 件 =\n")
for mid, lbl in matches:
    print(f"  [{mid}] {lbl}")
