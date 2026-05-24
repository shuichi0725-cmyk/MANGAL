"""ONE PIECE 巻 book record の (label, position, isPartOf) 全件 list、 isPartOf 欠落 別表示。"""
import re
import sys
from pathlib import Path

SRC = Path(".cache/madb/metadata101.json")

ID_RE = re.compile(r'"@id":\s*"https://mediaarts-db\.artmuseums\.go\.jp/id/(C\d+)"')
MID_RE = re.compile(r'"@id":\s*"https://mediaarts-db\.artmuseums\.go\.jp/id/(M\d+)"')
LABEL_RE = re.compile(r'^      "rdfs:label":\s*"((?:[^"\\]|\\.)*)"')
POS_RE = re.compile(r'"schema:position":\s*"((?:[^"\\]|\\.)*)"')
VOLNUM_RE = re.compile(r'"schema:volumeNumber":\s*"((?:[^"\\]|\\.)*)"')

records = []
in_rec = False
cur = {}
in_ispartof = False
with SRC.open(encoding="utf-8") as f:
    for line in f:
        if line.startswith("    {"):
            in_rec = True
            cur = {"label": "", "mid": "", "pos": "", "volnum": "", "ispartof": ""}
            in_ispartof = False
            continue
        if not in_rec:
            continue
        if line.rstrip().startswith("    }"):
            if cur["label"].startswith("ONE PIECE"):
                records.append(cur)
            in_rec = False
            continue
        m = LABEL_RE.match(line)
        if m:
            cur["label"] = m.group(1)
        m = MID_RE.search(line)
        if m and not cur["mid"]:
            cur["mid"] = m.group(1)
        p = POS_RE.search(line)
        if p:
            cur["pos"] = p.group(1)
        v = VOLNUM_RE.search(line)
        if v:
            cur["volnum"] = v.group(1)
        if '"schema:isPartOf"' in line:
            in_ispartof = True
            continue
        if in_ispartof:
            m = ID_RE.search(line)
            if m and not cur["ispartof"]:
                cur["ispartof"] = m.group(1)
            if "}" in line or "]" in line:
                in_ispartof = False

# 「ONE PIECE 巻」 始まり + position あり に 絞る
volume_records = [r for r in records if re.match(r"^ONE PIECE 巻", r["label"])]
print(f"= 'ONE PIECE 巻' 始まり book = {len(volume_records)} 件 =\n")

# C268196 紐づく vs 欠落
with_main = [r for r in volume_records if r["ispartof"] == "C268196"]
without_main = [r for r in volume_records if r["ispartof"] != "C268196"]

print(f"isPartOf=C268196: {len(with_main)} 件")
print(f"isPartOf 別 or 無し: {len(without_main)} 件\n")

print("= 別 / 無し record 詳細 =")
for r in without_main:
    ip = r["ispartof"] or "(無し)"
    print(f"  [{r['mid']}] {r['label']} | pos={r['pos']} vn={r['volnum']} isPartOf={ip}")
