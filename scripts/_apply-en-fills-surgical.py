"""option1 = 種a(AniList) english → 種3 alternative_titles.en の surgical 純粋追加。

★ 既存行は一切変更せず、 en 行だけを挿入する(33MB 保護ファイルの diff 最小化)。
   - CASE B (alternative_titles ブロック無し): entry 末尾に
       `    alternative_titles:` + `      en: <value>` を追加
   - CASE A (ブロック有り/en無し): `    alternative_titles:` 行直後に `      en: <value>` を挿入
   - 既に en がある entry は対象に含めない(= 純粋追加、 上書き禁止)

対象 = match-v9-all.tsv の verdict==S180 かつ s3_en 空 かつ a_en 有。

出力: data/seeds/series-supplement-v2.yml.new (検証用)。 --commit で本体置換。
"""
from __future__ import annotations
import csv
import pickle
import re
import sys
from pathlib import Path

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
YML = ROOT / "data" / "seeds" / "series-supplement-v2.yml"
TSV = ROOT / ".cache" / "match-v9-all.tsv"
PKL = ROOT / ".cache" / "seed3-promote.pkl"

KEY_RE = re.compile(r"^  - key: (.*)$")


def unq(s: str) -> str:
    s = s.rstrip("\n")
    if len(s) >= 2 and s[0] in "\"'" and s[-1] == s[0]:
        inner = s[1:-1]
        if s[0] == '"':
            inner = inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner
    return s


def en_line(en: str) -> str:
    """yaml で正しくクォートした `      en: <value>` 行を返す。"""
    assert "\n" not in en, f"newline in en title: {en!r}"
    s = yaml.safe_dump({"en": en}, allow_unicode=True, default_flow_style=False, width=10**9)
    s = s.rstrip("\n")
    assert "\n" not in s, f"multi-line en scalar: {en!r}"
    return "      " + s + "\n"


def build_targets():
    # TSV から S180 / s3_en空 / a_en有
    raw = {}
    with TSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["verdict"] == "S180" and not row["s3_en"].strip() and row["a_en"].strip():
                raw[row["s3_key"]] = row["a_en"].strip()
    # pickle で case 判定 + 既存en/missing 除外
    d = pickle.load(PKL.open("rb"))
    targets = {}
    skipped_has_en = missing = 0
    for k, en in raw.items():
        e = d.get(k)
        if e is None:
            missing += 1
            continue
        alt = e.get("alternative_titles")
        if isinstance(alt, dict) and alt.get("en"):
            skipped_has_en += 1
            continue
        case = "A" if (isinstance(alt, dict) and alt) else "B"
        targets[k] = (case, en)
    return targets, skipped_has_en, missing


def main():
    commit = "--commit" in sys.argv
    targets, skipped_has_en, missing = build_targets()
    nA = sum(1 for c, _ in targets.values() if c == "A")
    nB = sum(1 for c, _ in targets.values() if c == "B")
    print(f"targets={len(targets):,} (CASE A={nA}, CASE B={nB}) | 既存en除外={skipped_has_en} missing={missing}")

    lines = YML.read_text(encoding="utf-8").splitlines(keepends=True)

    # 単一行 `  - key:` のみ surgical 可能。 折返し(複数行 quoted)キーは除外。
    yml_keys = set()
    for line in lines:
        m = KEY_RE.match(line)
        if m:
            yml_keys.add(unq(m.group(1)))
    excluded = [k for k in targets if k not in yml_keys]
    for k in excluded:
        del targets[k]
    if excluded:
        print(f"除外(yml内で折返しキー、 surgical不可) {len(excluded)}件:")
        for k in excluded:
            print(f"  - {k[:80]}...")
    nA = sum(1 for c, _ in targets.values() if c == "A")
    nB = sum(1 for c, _ in targets.values() if c == "B")

    out = []
    cur_key = None
    pending_b = None  # CASE B: entry 末尾で追加する en value
    appliedA = appliedB = 0

    def flush_b():
        nonlocal pending_b, appliedB
        if pending_b is not None:
            out.append("    alternative_titles:\n")
            out.append(en_line(pending_b))
            appliedB += 1
            pending_b = None

    for line in lines:
        m = KEY_RE.match(line)
        if m:
            flush_b()  # 前 entry の CASE B を確定
            cur_key = unq(m.group(1))
            t = targets.get(cur_key)
            pending_b = t[1] if (t and t[0] == "B") else None
            out.append(line)
            continue
        # CASE A: alternative_titles: 行直後に en 挿入
        t = targets.get(cur_key)
        if t and t[0] == "A" and line.strip() == "alternative_titles:":
            out.append(line)
            out.append(en_line(t[1]))
            appliedA += 1
            continue
        out.append(line)
    flush_b()  # EOF: 最終 entry

    print(f"applied: CASE A={appliedA}, CASE B={appliedB}, 計={appliedA + appliedB:,}")
    if appliedA != nA or appliedB != nB:
        print(f"✗ ABORT: applied 数が targets と不一致 (A {appliedA}/{nA}, B {appliedB}/{nB})")
        sys.exit(1)

    dest = YML if commit else YML.with_suffix(".yml.new")
    dest.write_text("".join(out), encoding="utf-8")
    print(f"wrote: {dest.name} ({'本体置換' if commit else '検証用'})")


if __name__ == "__main__":
    main()
