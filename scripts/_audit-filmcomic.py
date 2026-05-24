"""metadata104 (= シリーズ entity) から フィルムコミック / アニメコミカライズ を 検出。

検出 signal (= 4 つ):
  1. schema:version に 「アニメ」「劇場」「映画」「OVA」「TV」「フィルム」 等 含む  ← ★ 最強
  2. schema:brand に 「アニメ版」「フィルムコミック」 等 含む
  3. schema:creator に 「[著]」 無く 「[カバー]」「[デザイン]」「[作画]」 等 のみ
  4. ma:originalWorkCreator あり (= 原作者 別 = コミカライズ可能性、 弱 signal)

Output:
  .cache/audit-filmcomic-version-dist.md       = schema:version 値分布
  .cache/audit-filmcomic-排除候補.tsv          = 排除対象 シリーズ一覧
  .cache/audit-filmcomic-summary.md            = サマリ
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / ".cache" / "madb" / "metadata104.json"
OUT_VERSION = ROOT / ".cache" / "audit-filmcomic-version-dist.md"
OUT_TSV = ROOT / ".cache" / "audit-filmcomic-targets.tsv"
OUT_MD = ROOT / ".cache" / "audit-filmcomic-summary.md"

# 排除キーワード (= schema:version / schema:brand に 含めば 排除候補)
VERSION_DROP_KEYWORDS = [
    "アニメ", "劇場", "映画", "OVA", "TV", "テレビ", "フィルム", "ノベライズ",
    "ノベル", "小説",
]
BRAND_DROP_KEYWORDS = [
    "アニメ版", "アニメコミック", "フィルムコミック", "フィルム・コミック",
    "TVアニメ", "劇場版",
]
# creator role が これらしか ない = 漫画家本人 が 無い signal
CREATOR_NON_AUTHOR_ROLES = {
    "[カバー]", "[カバー・イラスト]", "[カバー・デザイン]", "[デザイン]",
    "[イラスト]", "[原作]", "[原案]", "[企画]", "[編集]", "[構成]",
    "[脚本]", "[制作]", "[監修]", "[協力]", "[キャラクター・デザイン]",
}

LABEL_RE = re.compile(r'^      "rdfs:label":\s*"((?:[^"\\]|\\.)*)"')
ID_RE = re.compile(r'^      "@id":\s*"([^"]+)"')
VERSION_RE = re.compile(r'^      "schema:version":\s*"((?:[^"\\]|\\.)*)"')
BRAND_ARRAY_RE = re.compile(r'^      "schema:brand":\s*\[')
BRAND_INLINE_RE = re.compile(r'^      "schema:brand":\s*"((?:[^"\\]|\\.)*)"')
CREATOR_ARRAY_RE = re.compile(r'^      "schema:creator":\s*\[')
CREATOR_INLINE_RE = re.compile(r'^      "schema:creator":\s*"((?:[^"\\]|\\.)*)"')
ORIGWORK_RE = re.compile(r'^      "ma:originalWorkCreator":')
STRING_IN_ARRAY = re.compile(r'^        "((?:[^"\\]|\\.)*)"')

RECORD_START = re.compile(r"^    \{")
RECORD_END = re.compile(r"^    \},?")


def has_drop_keyword(s: str, keywords: list[str]) -> str:
    for kw in keywords:
        if kw in s:
            return kw
    return ""


def main() -> None:
    version_counts: Counter = Counter()
    targets: list[dict] = []

    in_rec = False
    cur_id = ""
    cur_label = ""
    cur_version = ""
    cur_brand_items: list[str] = []
    cur_creator_items: list[str] = []
    cur_has_origwork = False
    in_brand_array = False
    in_creator_array = False

    n = 0
    with SRC.open(encoding="utf-8") as f:
        for line in f:
            if RECORD_START.match(line):
                in_rec = True
                cur_id = cur_label = cur_version = ""
                cur_brand_items = []
                cur_creator_items = []
                cur_has_origwork = False
                in_brand_array = in_creator_array = False
                continue
            if RECORD_END.match(line):
                n += 1
                if n % 20000 == 0:
                    print(f"  scanned: {n}", file=sys.stderr)

                if cur_version:
                    version_counts[cur_version] += 1

                signals: list[str] = []
                version_kw = has_drop_keyword(cur_version, VERSION_DROP_KEYWORDS)
                if version_kw:
                    signals.append(f"version=「{cur_version}」")

                for b in cur_brand_items:
                    brand_kw = has_drop_keyword(b, BRAND_DROP_KEYWORDS)
                    if brand_kw:
                        signals.append(f"brand=「{b}」")
                        break

                # creator: 全て non-author role か?
                if cur_creator_items:
                    has_author = False
                    for c in cur_creator_items:
                        # role tag 抽出: 先頭の [...]
                        m = re.match(r"^(\[[^\]]+\])", c)
                        if m:
                            role = m.group(1)
                            if role not in CREATOR_NON_AUTHOR_ROLES:
                                has_author = True
                                break
                        else:
                            has_author = True
                            break
                    if not has_author:
                        signals.append("creator=漫画家不在")

                if signals:
                    targets.append({
                        "id": cur_id,
                        "title": cur_label,
                        "version": cur_version,
                        "brand": cur_brand_items[0] if cur_brand_items else "",
                        "creator": " / ".join(cur_creator_items),
                        "has_origwork": cur_has_origwork,
                        "signals": signals,
                    })

                in_rec = False
                continue

            if not in_rec:
                continue

            m = ID_RE.match(line)
            if m and not cur_id:
                cur_id = m.group(1).rsplit("/", 1)[-1]
                continue
            m = LABEL_RE.match(line)
            if m:
                cur_label = json.loads(f'"{m.group(1)}"')
                continue
            m = VERSION_RE.match(line)
            if m:
                cur_version = json.loads(f'"{m.group(1)}"')
                continue
            m = BRAND_INLINE_RE.match(line)
            if m:
                cur_brand_items = [json.loads(f'"{m.group(1)}"')]
                continue
            if BRAND_ARRAY_RE.match(line):
                in_brand_array = True
                continue
            m = CREATOR_INLINE_RE.match(line)
            if m:
                cur_creator_items = [json.loads(f'"{m.group(1)}"')]
                continue
            if CREATOR_ARRAY_RE.match(line):
                in_creator_array = True
                continue
            if in_brand_array:
                sm = STRING_IN_ARRAY.match(line)
                if sm:
                    cur_brand_items.append(json.loads(f'"{sm.group(1)}"'))
                if line.rstrip().endswith("]") or line.rstrip().endswith("],"):
                    in_brand_array = False
            if in_creator_array:
                sm = STRING_IN_ARRAY.match(line)
                if sm:
                    cur_creator_items.append(json.loads(f'"{sm.group(1)}"'))
                if line.rstrip().endswith("]") or line.rstrip().endswith("],"):
                    in_creator_array = False
            if ORIGWORK_RE.match(line):
                cur_has_origwork = True

    print(f"records: {n:,}", file=sys.stderr)
    print(f"targets: {len(targets):,}", file=sys.stderr)

    # version 値分布
    OUT_VERSION.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# schema:version 値分布", "", f"records: **{n:,}**", f"version-having: **{sum(version_counts.values()):,}**", "", "| version | 件数 | 排除keyword |", "|---|---|---|"]
    for v, c in version_counts.most_common(50):
        kw = has_drop_keyword(v, VERSION_DROP_KEYWORDS)
        kw_disp = f"**{kw}**" if kw else ""
        lines.append(f"| {v} | {c:,} | {kw_disp} |")
    OUT_VERSION.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote: {OUT_VERSION}", file=sys.stderr)

    # 排除対象 TSV
    with OUT_TSV.open("w", encoding="utf-8") as f:
        f.write("series_id\ttitle\tversion\tbrand\tcreator\thas_origwork\tsignals\n")
        for t in targets:
            f.write(f"{t['id']}\t{t['title']}\t{t['version']}\t{t['brand']}\t{t['creator']}\t{t['has_origwork']}\t{' | '.join(t['signals'])}\n")
    print(f"wrote: {OUT_TSV}", file=sys.stderr)

    # サマリ
    sig_counts: Counter = Counter()
    for t in targets:
        for s in t["signals"]:
            key = s.split("=", 1)[0]
            sig_counts[key] += 1

    md = []
    md.append("# Filmcomic / アニメコミカライズ 排除候補 Audit")
    md.append("")
    md.append(f"records: **{n:,}**")
    md.append(f"排除候補 (= 何らかの signal あり): **{len(targets):,}**")
    md.append("")
    md.append("## signal 種別 件数")
    md.append("")
    md.append("| signal | 件数 |")
    md.append("|---|---|")
    for k, c in sig_counts.most_common():
        md.append(f"| {k} | {c:,} |")
    md.append("")
    md.append("## 排除候補 先頭 50 件")
    md.append("")
    md.append("| シリーズID | title | version | brand | creator | signals |")
    md.append("|---|---|---|---|---|---|")
    for t in targets[:50]:
        sig = " + ".join(t["signals"])
        md.append(f"| {t['id']} | {t['title'][:25]} | {t['version'][:15]} | {t['brand'][:20]} | {t['creator'][:30]} | {sig[:50]} |")
    if len(targets) > 50:
        md.append(f"| ... | ({len(targets)} 件合計) | | | | |")
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"wrote: {OUT_MD}", file=sys.stderr)


if __name__ == "__main__":
    main()
