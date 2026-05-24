"""漢字 → カタカナ外来語当て字 audit v4 (= metadata104 = シリーズ entity 直 scan)。

v3 比改善:
- source = .cache/madb/metadata104.json (= class:MangaBookSeries、 179 MB)
- 集約 logic 不要 (= シリーズ entity = 1 件 = unique)
- 表記揺れ / book 副題 noise が 構造的に 排除
- ASCII 含む ja-hrkt entry は 別カテゴリ (= alt_en source 副産物)、 当て字 判定からは除外

カテゴリ:
  ok           : 純カタカナ entry が 標準読みと 一致
  has_both     : ★ 純カタカナで 普通読み + 当て字 両方持ち (= MADB公式 当て字)
  ateji_only   : 純カタカナで 当て字のみ
  no_kanji     : title 漢字なし
  no_kana      : ja-hrkt entry 1 つもなし (= or 全部 ASCII)
  kanji_unread : pykakasi 読めず

副産物:
  .cache/seed3-kana-fill-source-v4.tsv = (series_id, title, preferred_kana)
  .cache/madb-series-alt-en-v4.tsv     = (series_id, title, ascii_entries) ← alt_en source

Output:
  .cache/audit-kanji-loanword-ateji-v4.txt
  .cache/audit-kanji-loanword-ateji-v4-summary.md
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import pykakasi

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / ".cache" / "madb" / "metadata104.json"
OUT_TXT = ROOT / ".cache" / "audit-kanji-loanword-ateji-v4.txt"
OUT_MD = ROOT / ".cache" / "audit-kanji-loanword-ateji-v4-summary.md"
OUT_FILL = ROOT / ".cache" / "seed3-kana-fill-source-v4.tsv"
OUT_ALTEN = ROOT / ".cache" / "madb-series-alt-en-v4.tsv"

KANJI_RE = re.compile(r"[一-鿿㐀-䶿]")
HIRAGANA_RE = re.compile(r"[぀-ゟ]")
KATAKANA_RE = re.compile(r"[゠-ヿㇰ-ㇿ]")
ASCII_RE = re.compile(r"[A-Za-z]")

LABEL_RE = re.compile(r'^      "rdfs:label":\s*"((?:[^"\\]|\\.)*)"')
ID_RE = re.compile(r'^      "@id":\s*"([^"]+)"')
NAME_START_RE = re.compile(r'^      "schema:name":\s*\[')
NAME_END_RE = re.compile(r'^      \]')
VALUE_RE = re.compile(r'"@value":\s*"((?:[^"\\]|\\.)*)"')
LANG_RE = re.compile(r'"@language":\s*"([^"]+)"')
CREATOR_ID_INLINE = re.compile(r'"@id":\s*"https://mediaarts-db\.artmuseums\.go\.jp/id/(C\d+)"')

_KKS = pykakasi.kakasi()


def normalize_kana(s: str) -> str:
    return re.sub(r"[\s　・\-ーー!?！？。、,.]+", "", s)


def predict_kana(title: str) -> str:
    result = _KKS.convert(title)
    return "".join(r["kana"] for r in result)


def parse_records():
    """metadata104.json を line stream で record 単位 buffer。
       yield (series_id, label, kana_jahrkt_list, creator_id)。"""
    in_record = False
    cur_id = ""
    cur_label = ""
    cur_kana_list: list[str] = []
    cur_creator = ""
    in_name = False
    pending_value = ""
    pending_lang = ""

    with SRC.open(encoding="utf-8") as f:
        for line in f:
            if line.startswith("    {"):
                in_record = True
                cur_id = cur_label = cur_creator = ""
                cur_kana_list = []
                in_name = False
                continue
            if not in_record:
                continue
            if line.rstrip().startswith("    }"):
                yield cur_id, cur_label, cur_kana_list, cur_creator
                in_record = False
                continue

            m = ID_RE.match(line)
            if m and not cur_id:
                cur_id = m.group(1).rsplit("/", 1)[-1]
                continue
            m = LABEL_RE.match(line)
            if m:
                cur_label = json.loads(f'"{m.group(1)}"')
                continue
            if not cur_creator:
                cm = CREATOR_ID_INLINE.search(line)
                if cm:
                    cur_creator = cm.group(1)
            if NAME_START_RE.match(line):
                in_name = True
                pending_value = pending_lang = ""
                continue
            if in_name:
                if NAME_END_RE.match(line):
                    in_name = False
                    pending_value = pending_lang = ""
                    continue
                v = VALUE_RE.search(line)
                if v:
                    pending_value = json.loads(f'"{v.group(1)}"')
                l = LANG_RE.search(line)
                if l:
                    pending_lang = l.group(1)
                    if pending_lang == "ja-hrkt" and pending_value:
                        if pending_value not in cur_kana_list:
                            cur_kana_list.append(pending_value)
                    pending_value = pending_lang = ""


def main() -> None:
    stats: Counter = Counter()
    has_both: list[dict] = []
    ateji_only: list[dict] = []
    fill_rows: list[tuple[str, str, str]] = []
    alten_rows: list[tuple[str, str, str]] = []

    n_records = 0
    for sid, label, kana_list, creator in parse_records():
        n_records += 1
        if not sid or not label:
            continue
        if n_records % 20000 == 0:
            print(f"  scanned: {n_records}", file=sys.stderr)

        # ASCII 含む entry を 抽出 (= alt_en source、 当て字 判定からは 除外)
        kata_entries: list[str] = []
        ascii_entries: list[str] = []
        for k in kana_list:
            ks = k.strip()
            if not ks:
                continue
            if ASCII_RE.search(ks):
                ascii_entries.append(ks)
            else:
                kata_entries.append(ks)

        if ascii_entries:
            alten_rows.append((sid, label, " | ".join(ascii_entries)))

        # 判定
        if not kata_entries:
            stats["no_kana"] += 1
            continue
        if not KANJI_RE.search(label):
            stats["no_kanji"] += 1
            fill_rows.append((sid, label, re.sub(r"[\s　]+", "", kata_entries[0])))
            continue

        predicted = predict_kana(label)
        if KANJI_RE.search(predicted):
            stats["kanji_unread"] += 1
            fill_rows.append((sid, label, re.sub(r"[\s　]+", "", kata_entries[0])))
            continue

        pn = normalize_kana(predicted)
        matches: list[str] = []
        non_matches: list[str] = []
        for k in kata_entries:
            an = normalize_kana(k)
            if an == pn:
                matches.append(k)
            else:
                non_matches.append(k)

        preferred_kana = ""
        if not non_matches:
            stats["ok"] += 1
            preferred_kana = matches[0]
        elif not matches:
            stats["ateji_only"] += 1
            preferred_kana = non_matches[0]
            ateji_only.append({
                "id": sid, "title": label,
                "predicted": predicted, "kana_list": kata_entries,
            })
        else:
            stats["has_both"] += 1
            preferred_kana = non_matches[0]  # ★ 当て字優先 (= CLAUDE.md ルール)
            has_both.append({
                "id": sid, "title": label,
                "predicted": predicted, "normal": matches, "ateji": non_matches,
            })

        preferred_kana_compact = re.sub(r"[\s　]+", "", preferred_kana)
        fill_rows.append((sid, label, preferred_kana_compact))

    print(f"records scanned: {n_records:,}", file=sys.stderr)

    # write TSVs
    OUT_FILL.parent.mkdir(parents=True, exist_ok=True)
    with OUT_FILL.open("w", encoding="utf-8") as f:
        f.write("series_id\ttitle\tpreferred_kana\n")
        for r in fill_rows:
            f.write("\t".join(r) + "\n")
    print(f"wrote: {OUT_FILL} ({len(fill_rows):,} rows)", file=sys.stderr)

    with OUT_ALTEN.open("w", encoding="utf-8") as f:
        f.write("series_id\ttitle\tascii_entries\n")
        for r in alten_rows:
            f.write("\t".join(r) + "\n")
    print(f"wrote: {OUT_ALTEN} ({len(alten_rows):,} rows)", file=sys.stderr)

    # txt detail
    lines = []
    lines.append("# 漢字 → カタカナ外来語当て字 Audit v4 (= シリーズ entity 直)")
    lines.append("")
    lines.append(f"records scanned: {n_records:,}")
    lines.append("")
    lines.append("## カテゴリ件数")
    for k in ["ok", "no_kanji", "no_kana", "kanji_unread", "has_both", "ateji_only"]:
        lines.append(f"  {k:14}: {stats.get(k, 0):>7,}")
    lines.append("")
    lines.append("## has_both 全件 (= ★ MADB公式 シリーズ単位 当て字、 mini 辞書 seed)")
    lines.append("")
    for r in has_both:
        lines.append(f"  [{r['id']}] {r['title']}")
        lines.append(f"    predicted: {r['predicted']}")
        lines.append(f"    normal:    {r['normal']}")
        lines.append(f"    ateji:     {r['ateji']}")
        lines.append("")
    lines.append("")
    lines.append("## ateji_only サンプル 300 件")
    lines.append("")
    for r in ateji_only[:300]:
        lines.append(f"  [{r['id']}] {r['title']}")
        lines.append(f"    predicted: {r['predicted']}")
        lines.append(f"    kana_list: {r['kana_list']}")
        lines.append("")
    if len(ateji_only) > 300:
        lines.append(f"  ... and {len(ateji_only) - 300} more")

    OUT_TXT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote: {OUT_TXT}", file=sys.stderr)

    # summary md
    md = []
    md.append("# 漢字 → カタカナ外来語当て字 Audit v4 (= summary、 シリーズ entity 直)")
    md.append("")
    md.append(f"records scanned: **{n_records:,}**")
    md.append("")
    md.append("## カテゴリ件数")
    md.append("")
    md.append("| カテゴリ | 件数 |")
    md.append("|---|---|")
    md.append(f"| ok | {stats.get('ok', 0):,} |")
    md.append(f"| no_kanji | {stats.get('no_kanji', 0):,} |")
    md.append(f"| no_kana | {stats.get('no_kana', 0):,} |")
    md.append(f"| kanji_unread | {stats.get('kanji_unread', 0):,} |")
    md.append(f"| **has_both** | **{stats.get('has_both', 0):,}** |")
    md.append(f"| ateji_only | {stats.get('ateji_only', 0):,} |")
    md.append(f"| alt_en source (= 副産物) | {len(alten_rows):,} |")
    md.append("")
    md.append("## has_both 先頭 100 件")
    md.append("")
    md.append("| シリーズID | title | 普通読み | 当て字 |")
    md.append("|---|---|---|---|")
    for r in has_both[:100]:
        n = " / ".join(r["normal"])[:40]
        a = " / ".join(r["ateji"])[:40]
        md.append(f"| {r['id']} | {r['title'][:30]} | {n} | {a} |")
    if len(has_both) > 100:
        md.append(f"| ... | ({len(has_both)} 件 合計) | | |")
    md.append("")
    md.append("## ateji_only サンプル 50 件")
    md.append("")
    md.append("| シリーズID | title | 標準読み | フリガナ |")
    md.append("|---|---|---|---|")
    for r in ateji_only[:50]:
        klst = " / ".join(r["kana_list"])[:40]
        md.append(f"| {r['id']} | {r['title'][:30]} | {r['predicted'][:30]} | {klst} |")
    if len(ateji_only) > 50:
        md.append(f"| ... | ({len(ateji_only)} 件 合計) | | |")
    md.append("")
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"wrote: {OUT_MD}", file=sys.stderr)

    print(f"\n=== SUMMARY ===", file=sys.stderr)
    for k in ["ok", "no_kanji", "no_kana", "kanji_unread", "has_both", "ateji_only"]:
        print(f"  {k:14}: {stats.get(k, 0):>7,}", file=sys.stderr)
    print(f"  alt_en source : {len(alten_rows):>7,}", file=sys.stderr)


if __name__ == "__main__":
    main()
