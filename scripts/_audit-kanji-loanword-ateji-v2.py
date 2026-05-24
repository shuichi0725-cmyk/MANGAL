"""漢字 → カタカナ外来語当て字 audit v2 (= 全 ja-hrkt entry 取得 + has_both 検出)。

source: .cache/madb/metadata101.json

カテゴリ:
  ok           : 全 ja-hrkt entry が pykakasi 標準読み と 一致 (= 通常)
  has_both     : 一致 entry + 不一致 entry 両方 ★ MADB 公式当て字 (= 最強 seed)
  ateji_only   : 全 entry が 不一致 (= 当て字のみ、 普通読み 持たず)
  no_kanji     : title 漢字なし (= 対象外)
  no_kana      : ja-hrkt entry 1 つもなし
  kanji_unread : pykakasi 読めず (= 判定不能)

副産物:
  .cache/seed3-kana-fill-source.tsv = (series-key, title_core, preferred_kana)
    preferred_kana = 当て字 あれば 当て字優先 (= CLAUDE.md ルール)、 なければ 普通読み

Output:
  .cache/audit-kanji-loanword-ateji-v2.txt
  .cache/audit-kanji-loanword-ateji-v2-summary.md
  .cache/seed3-kana-fill-source.tsv
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import pykakasi

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / ".cache" / "madb" / "metadata101.json"
OUT_TXT = ROOT / ".cache" / "audit-kanji-loanword-ateji-v2.txt"
OUT_MD = ROOT / ".cache" / "audit-kanji-loanword-ateji-v2-summary.md"
OUT_FILL = ROOT / ".cache" / "seed3-kana-fill-source.tsv"

KANJI_RE = re.compile(r"[一-鿿㐀-䶿]")
HIRAGANA_RE = re.compile(r"[぀-ゟ]")
KATAKANA_RE = re.compile(r"[゠-ヿㇰ-ㇿ]")

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


def strip_title_suffix(t: str) -> str:
    t = t.strip()
    t = re.sub(r"[\s　]*第[0-90-9一二三四五六七八九十百]+(?:巻|部|話)?$", "", t)
    t = re.sub(r"[\s　]+[0-90-9一二三四五六七八九十百]+(?:巻)?$", "", t)
    return t.strip()


def strip_kana_suffix(k: str) -> str:
    k = k.strip()
    if " : " in k:
        k = k.split(" : ", 1)[0]
    k = re.sub(r"[\s　]+[0-90-9一二三四五六七八九十百]+(?:カン)?$", "", k)
    return k.strip()


def predict_kana(title: str) -> str:
    result = _KKS.convert(title)
    return "".join(r["kana"] for r in result)


def parse_records():
    """yield (madb_id, label, kana_jahrkt_list, creator_id)。 ja-hrkt entry を 全て収集。"""
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


def dedup_key(creator: str, label: str) -> tuple[str, str]:
    t = strip_title_suffix(label)
    if " : " in t:
        t = t.split(" : ", 1)[0].strip()
    return (creator, t)


def main() -> None:
    seen: dict[tuple[str, str], dict] = {}
    n_records = 0
    for mid, label, kana_list, creator in parse_records():
        n_records += 1
        if not label:
            continue
        key = dedup_key(creator, label)
        if key not in seen:
            seen[key] = {
                "mid": mid,
                "title_core": key[1],
                "creator": creator,
                "kana_set": set(),
            }
        for k in kana_list:
            stripped = strip_kana_suffix(k)
            if stripped:
                seen[key]["kana_set"].add(stripped)
        if n_records % 50000 == 0:
            print(f"  scanned: {n_records}", file=sys.stderr)

    print(f"records scanned: {n_records}", file=sys.stderr)
    print(f"unique series (creator, title_core): {len(seen)}", file=sys.stderr)

    stats: Counter = Counter()
    has_both: list[dict] = []
    ateji_only: list[dict] = []
    fill_rows: list[tuple[str, str, str]] = []  # (series_key_str, title_core, preferred_kana)

    for key, info in seen.items():
        title_core = info["title_core"]
        creator = info["creator"]
        mid = info["mid"]
        kana_set = info["kana_set"]
        kana_list = sorted(kana_set)

        # fill source: preferred_kana = 当て字 (= 標準読みと不一致) があれば 優先、 なければ 標準一致
        preferred_kana = ""
        if kana_list:
            preferred_kana = kana_list[0]  # 暫定: 後で 当て字優先 に更新

        if not kana_list:
            stats["no_kana"] += 1
            continue
        if not KANJI_RE.search(title_core):
            stats["no_kanji"] += 1
            fill_rows.append((f"{creator}|{title_core}", title_core, kana_list[0]))
            continue

        predicted = predict_kana(title_core)
        if KANJI_RE.search(predicted):
            stats["kanji_unread"] += 1
            fill_rows.append((f"{creator}|{title_core}", title_core, kana_list[0]))
            continue

        pn = normalize_kana(predicted)
        matches: list[str] = []
        non_matches: list[str] = []
        for k in kana_list:
            an = normalize_kana(k)
            if an == pn:
                matches.append(k)
            else:
                non_matches.append(k)

        if not non_matches:
            stats["ok"] += 1
            preferred_kana = matches[0]
        elif not matches:
            stats["ateji_only"] += 1
            preferred_kana = non_matches[0]  # 当て字 のみ なので そのまま
            ateji_only.append({
                "id": mid, "creator": creator, "title": title_core,
                "predicted": predicted, "kana_list": kana_list,
            })
        else:
            stats["has_both"] += 1
            preferred_kana = non_matches[0]  # ★ 当て字優先 (= CLAUDE.md ルール)
            has_both.append({
                "id": mid, "creator": creator, "title": title_core,
                "predicted": predicted, "normal": matches, "ateji": non_matches,
            })

        # スペース除去 (= CLAUDE.md title_kana ルール)
        preferred_kana_compact = re.sub(r"[\s　]+", "", preferred_kana)
        fill_rows.append((f"{creator}|{title_core}", title_core, preferred_kana_compact))

    # write fill source TSV
    with OUT_FILL.open("w", encoding="utf-8") as f:
        f.write("series_key\ttitle_core\tpreferred_kana\n")
        for r in fill_rows:
            f.write("\t".join(r) + "\n")
    print(f"wrote: {OUT_FILL} ({len(fill_rows):,} rows)", file=sys.stderr)

    # txt detail
    lines = []
    lines.append("# 漢字 → カタカナ外来語当て字 Audit v2")
    lines.append("")
    lines.append(f"records scanned: {n_records:,}")
    lines.append(f"unique series: {len(seen):,}")
    lines.append("")
    lines.append("## カテゴリ件数")
    for k in ["ok", "no_kanji", "no_kana", "kanji_unread", "has_both", "ateji_only"]:
        lines.append(f"  {k:14}: {stats.get(k, 0):>7,}")
    lines.append("")
    lines.append("## has_both (= ★ MADB 公式当て字、 最強 mini 辞書 seed) 全件")
    lines.append("")
    for r in has_both:
        lines.append(f"  [{r['id']}] {r['title']}")
        lines.append(f"    predicted: {r['predicted']}")
        lines.append(f"    normal:    {r['normal']}")
        lines.append(f"    ateji:     {r['ateji']}")
        lines.append("")
    lines.append("")
    lines.append("## ateji_only (= 当て字のみ、 普通読み持たず、 サンプル 200 件)")
    lines.append("")
    for r in ateji_only[:200]:
        lines.append(f"  [{r['id']}] {r['title']}")
        lines.append(f"    predicted: {r['predicted']}")
        lines.append(f"    kana_list: {r['kana_list']}")
        lines.append("")
    if len(ateji_only) > 200:
        lines.append(f"  ... and {len(ateji_only) - 200} more")

    OUT_TXT.parent.mkdir(parents=True, exist_ok=True)
    OUT_TXT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote: {OUT_TXT}", file=sys.stderr)

    # summary md
    md = []
    md.append("# 漢字 → カタカナ外来語当て字 Audit v2 (= summary)")
    md.append("")
    md.append(f"records scanned: **{n_records:,}**")
    md.append(f"unique series: **{len(seen):,}**")
    md.append("")
    md.append("## カテゴリ件数")
    md.append("")
    md.append("| カテゴリ | 件数 | 意味 |")
    md.append("|---|---|---|")
    md.append(f"| ok | {stats.get('ok', 0):,} | 全 ja-hrkt = 標準読み (= 通常) |")
    md.append(f"| no_kanji | {stats.get('no_kanji', 0):,} | title 漢字なし |")
    md.append(f"| no_kana | {stats.get('no_kana', 0):,} | ja-hrkt 0 件 (= 種3 fill 補完必要) |")
    md.append(f"| kanji_unread | {stats.get('kanji_unread', 0):,} | pykakasi 読めず |")
    md.append(f"| **has_both** | **{stats.get('has_both', 0):,}** | **★ MADB公式当て字 (= 普通読み + 当て字 両方持ち)** |")
    md.append(f"| ateji_only | {stats.get('ateji_only', 0):,} | 当て字のみ (= 真の当て字 + 訓読み揺れ noise 混在) |")
    md.append("")
    md.append("## has_both 全件 (= 最強 mini 辞書 seed)")
    md.append("")
    md.append("| MADB ID | title | 普通読み | 当て字 |")
    md.append("|---|---|---|---|")
    for r in has_both[:200]:
        n = " / ".join(r["normal"])[:40]
        a = " / ".join(r["ateji"])[:40]
        md.append(f"| {r['id']} | {r['title'][:30]} | {n} | {a} |")
    if len(has_both) > 200:
        md.append(f"| ... | ({len(has_both)} 件 合計) | | |")
    md.append("")
    md.append("## ateji_only サンプル 50 件")
    md.append("")
    md.append("| MADB ID | title | 標準読み | フリガナ list |")
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


if __name__ == "__main__":
    main()
