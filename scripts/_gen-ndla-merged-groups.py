#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NDL典拠IDの8桁切りで別人が1行に合体した作者(mangaka)の組 → data/seeds/ndla-merged-groups.json (2026-10-20 新設)。

背景: `_build-mangaka-madb.py` は metadata504 の `ma:ndla`(典拠ID)を `(\\d{8})` で取り、`ndl:<8桁>` を作者の
  識別子にして名寄せする。 典拠IDには9桁(27,127人)があり、頭8桁が同じ隣の典拠IDの人が1行に合体する
  (喜月かこ 001211922 + 瞳ちご 001211925 → ndl:00121192「瞳ちご」)。 種2の series_authors はこの行を指すので、
  頁の作者欄が別人になる(公開頁≥113・毎月の新刊でも起きる)。
★識別子を全桁に直すと、種2の作者表(ndl:<8桁> で登録済み・populate は新しい作者行を足さない)と繋がらなくなり、
  新作の作者が空欄になる → 識別子はそのまま、 promote が「その本のクレジットに載っている組の名前」に分け直す
  (`_split_ndla_merged`)。 この seed はその組の表 = 種2不変・再生成で冪等。 月次 intake の ndlagroups 段(promote の前)。

出力: {"groups": {作者表の名前: [組の全員の名前(504 の schema:name / rdfs:label)…]}, "qid": {名前: "ndl:<8桁>"}, ...}
  ★同じ名前の作者行が合体していない行にも在る(同名の別人)名前は入れない(頁の作者がどちらの行か名前では分からない)。
"""
import collections
import datetime
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
META504 = ROOT / ".cache" / "madb" / "metadata504.json"
DB = ROOT / ".cache" / "db-v2.sqlite"
OUT = ROOT / "data" / "seeds" / "ndla-merged-groups.json"


def _fold(s: str) -> str:
    return re.sub(r"[\s・･,，.]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()


def _strs(v) -> list[str]:
    if isinstance(v, str):
        return [v]
    if isinstance(v, dict):
        return _strs(v.get("@value"))
    if isinstance(v, list):
        return [x for y in v for x in _strs(y)]
    return []


def main():
    g = json.load(open(META504, encoding="utf-8"))
    g = g.get("@graph", g) if isinstance(g, dict) else g
    persons = collections.defaultdict(lambda: collections.defaultdict(list))   # 8桁 → 全桁 → [名前]
    for b in g:
        if b.get("ma:additionalGenre") == "団体":
            continue
        raw = str(b.get("ma:ndla", ""))
        k8 = re.search(r"(\d{8})", raw)          # ★_build-mangaka-madb.py と同じ切り方(=作者表の識別子)
        full = re.search(r"entity/(\d+)", raw)
        if not (k8 and full):
            continue
        for nm in _strs(b.get("schema:name")) + _strs(b.get("rdfs:label")):
            nm = nm.strip()
            if nm and nm not in persons[k8.group(1)][full.group(1)]:
                persons[k8.group(1)][full.group(1)].append(nm)
    merged = {}
    for k8, by_full in persons.items():
        if len(by_full) < 2:
            continue
        folds = [{_fold(n) for n in ns} for ns in by_full.values()]
        if len(set().union(*folds)) < 2 or all(f & folds[0] for f in folds[1:]):
            continue                       # 名前が同じ(同一人物の典拠ID違い)なら合体ではない
        merged[k8] = by_full
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = con.execute("SELECT name, qid FROM mangaka").fetchall()
    name_qids = collections.defaultdict(set)
    for nm, q in rows:
        name_qids[nm].add(q or "")
    groups, qid_of, ambiguous = {}, {}, []
    for nm, q in rows:
        if not (q or "").startswith("ndl:") or q[4:] not in merged:
            continue
        if any(not (x.startswith("ndl:") and x[4:] in merged) for x in name_qids[nm]):
            ambiguous.append(nm)           # 同名で合体していない作者行も在る = 名前ではどちらか決められない
            continue
        mem = sorted({n for ns in merged[q[4:]].values() for n in ns} | {nm})
        groups[nm] = sorted(set(groups.get(nm, [])) | set(mem))
        qid_of[nm] = q
    n_sa = con.execute(
        "SELECT count(*) FROM series_authors sa JOIN mangaka m ON m.id=sa.mangaka_id WHERE m.qid IN (%s)"
        % ",".join("?" * len(qid_of)), list(qid_of.values())).fetchone()[0] if qid_of else 0
    OUT.write_text(json.dumps({
        "generated_at": datetime.date.today().isoformat(),
        "generator": "scripts/_gen-ndla-merged-groups.py",
        "note": "NDL典拠ID8桁切りで合体した作者行の組。promote の _split_ndla_merged が本のクレジットに載る組の名前へ分け直す",
        "groups": dict(sorted(groups.items())),
        "qid": dict(sorted(qid_of.items())),
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"8桁で別人が合体する典拠キー {len(merged):,} / 作者表の合体行 {len(groups):,}名"
          f"(同名の別行が在り外した {len(set(ambiguous)):,})/ それを作者に持つ series の結び {n_sa:,}")
    print(f"→ {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
