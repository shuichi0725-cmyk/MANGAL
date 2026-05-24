"""漢字 → カタカナ外来語 当て字 を 検出 (= 種1 raw 直 scan 版)。

source: .cache/madb/metadata101.json (= 660 MB)
   - book 単位 record から rdfs:label + schema:name の ja-hrkt entry を 抽出
   - unique (title, kana) で dedup

例: 「ザ・超女」 = title 漢字 「超女」 + フリガナ 「ザ スーパー ギャル」
     → pykakasi 標準読み 「チョウジョ」 != 「スーパーギャル」 = 当て字
     → かつ フリガナ 全 カタカナ (= ひらがな 含まず) = 外来語起源 強い指標
     → 「漢字 → カタカナ外来語当て字」 確定

Output: .cache/audit-kanji-loanword-ateji.txt + .cache/audit-kanji-loanword-ateji-summary.md
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
OUT_TXT = ROOT / ".cache" / "audit-kanji-loanword-ateji.txt"
OUT_MD = ROOT / ".cache" / "audit-kanji-loanword-ateji-summary.md"

KANJI_RE = re.compile(r"[一-鿿㐀-䶿]")
HIRAGANA_RE = re.compile(r"[぀-ゟ]")
KATAKANA_RE = re.compile(r"[゠-ヿㇰ-ㇿ]")

LABEL_RE = re.compile(r'^      "rdfs:label":\s*"((?:[^"\\]|\\.)*)"')
ID_RE = re.compile(r'^      "@id":\s*"([^"]+)"')
NAME_START_RE = re.compile(r'^      "schema:name":\s*\[')
NAME_END_RE = re.compile(r'^      \]')
VALUE_RE = re.compile(r'"@value":\s*"((?:[^"\\]|\\.)*)"')
LANG_RE = re.compile(r'"@language":\s*"([^"]+)"')
CREATOR_BLOCK_RE = re.compile(r'^      "dcterms:creator":\s*\{')
CREATOR_ID_INLINE = re.compile(r'"@id":\s*"https://mediaarts-db\.artmuseums\.go\.jp/id/(C\d+)"')

_KKS = pykakasi.kakasi()


def normalize_kana(s: str) -> str:
    return re.sub(r"[\s　・\-ーー!?！？。、,.]+", "", s)


def strip_title_suffix(t: str) -> str:
    """末尾の 巻数 / 「第N巻」 等 を 除去 (= false positive 削減)。"""
    t = t.strip()
    # 末尾 「第N巻」 「第N部」 「第N話」
    t = re.sub(r"[\s　]*第[0-9０-９一二三四五六七八九十百]+(?:巻|部|話)?$", "", t)
    # 末尾 算用 / 全角 / 漢数字 + 「巻」 任意
    t = re.sub(r"[\s　]+[0-9０-９一二三四五六七八九十百]+(?:巻)?$", "", t)
    return t.strip()


def strip_kana_suffix(k: str) -> str:
    """副題 ' : ' 以降 を 除去 + 末尾巻数 除去。"""
    k = k.strip()
    if " : " in k:
        k = k.split(" : ", 1)[0]
    k = re.sub(r"[\s　]+[0-9０-９一二三四五六七八九十百]+(?:カン)?$", "", k)
    return k.strip()


def predict_kana(title: str) -> str:
    result = _KKS.convert(title)
    return "".join(r["kana"] for r in result)


def parse_records():
    """metadata101.json を line stream で record 単位 buffer。 yield (madb_id, label, kana_jahrkt, creator_id)。"""
    in_record = False
    cur_id = ""
    cur_label = ""
    cur_kana = ""
    cur_creator = ""
    in_name = False
    pending_value = ""
    pending_lang = ""

    with SRC.open(encoding="utf-8") as f:
        for line in f:
            if line.startswith("    {"):
                in_record = True
                cur_id = cur_label = cur_kana = cur_creator = ""
                in_name = False
                continue
            if not in_record:
                continue
            if line.rstrip().startswith("    }"):
                yield cur_id, cur_label, cur_kana, cur_creator
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
                    if pending_lang == "ja-hrkt" and pending_value and not cur_kana:
                        cur_kana = pending_value
                    pending_value = pending_lang = ""


def dedup_key(creator: str, label: str) -> tuple[str, str]:
    """シリーズ集約 key = (creator_id, title_core)。 種3 key 形式に 近い。"""
    t = strip_title_suffix(label)
    if " : " in t:
        t = t.split(" : ", 1)[0].strip()
    return (creator, t)


def main() -> None:
    # series-key → {title_core, kana_core, madb_id}
    seen: dict[tuple[str, str], dict] = {}
    n_records = 0
    for mid, label, kana, creator in parse_records():
        n_records += 1
        if not label:
            continue
        key = dedup_key(creator, label)
        if key not in seen:
            seen[key] = {
                "mid": mid,
                "title_core": key[1],
                "kana_core": strip_kana_suffix(kana) if kana else "",
                "creator": creator,
            }
        else:
            # 既存 entry に kana 無く 今回あれば 補充
            if not seen[key]["kana_core"] and kana:
                seen[key]["kana_core"] = strip_kana_suffix(kana)
        if n_records % 50000 == 0:
            print(f"  scanned: {n_records}", file=sys.stderr)

    print(f"records scanned: {n_records}", file=sys.stderr)
    print(f"unique series (creator, title_core): {len(seen)}", file=sys.stderr)

    stats: Counter = Counter()
    ateji_kata: list[dict] = []
    ateji_mixed: list[dict] = []

    for key, info in seen.items():
        title_core = info["title_core"]
        kana_core = info["kana_core"]
        mid = info["mid"]

        if not kana_core:
            stats["no_kana"] += 1
            continue
        if not KANJI_RE.search(title_core):
            stats["no_kanji"] += 1
            continue

        predicted = predict_kana(title_core)
        if KANJI_RE.search(predicted):
            stats["kanji_unread"] += 1
            continue

        pn = normalize_kana(predicted)
        an = normalize_kana(kana_core)
        if pn == an:
            stats["ok"] += 1
            continue

        kana_has_hira = bool(HIRAGANA_RE.search(an))
        if not kana_has_hira:
            stats["ateji_kata"] += 1
            ateji_kata.append({"id": mid, "title": title_core, "kana": kana_core, "predicted": predicted})
        else:
            stats["ateji_mixed"] += 1
            ateji_mixed.append({"id": mid, "title": title_core, "kana": kana_core, "predicted": predicted})

    # txt 詳細
    lines = []
    lines.append("# 漢字 → カタカナ外来語 当て字 Audit (= 種1 raw 直)")
    lines.append("")
    lines.append(f"records scanned: {n_records:,}")
    lines.append(f"unique (title, kana): {len(seen):,}")
    lines.append("")
    lines.append("## カテゴリ件数")
    for k in ["ok", "no_kanji", "no_kana", "kanji_unread", "ateji_kata", "ateji_mixed"]:
        lines.append(f"  {k:14}: {stats.get(k, 0):>7,}")
    lines.append("")
    lines.append("## ateji_kata (= 漢字 → カタカナ外来語当て字、 本命) 全件")
    lines.append("")
    for r in ateji_kata:
        lines.append(f"  [{r['id']}] {r['title']}")
        lines.append(f"    predicted: {r['predicted']}")
        lines.append(f"    actual:    {r['kana']}")
        lines.append("")
    lines.append("")
    lines.append("## ateji_mixed (= 漢字 → ひらがな混在 当て字、 サンプル 100 件)")
    lines.append("")
    for r in ateji_mixed[:100]:
        lines.append(f"  [{r['id']}] {r['title']}")
        lines.append(f"    predicted: {r['predicted']}")
        lines.append(f"    actual:    {r['kana']}")
        lines.append("")
    if len(ateji_mixed) > 100:
        lines.append(f"  ... and {len(ateji_mixed) - 100} more")

    OUT_TXT.parent.mkdir(parents=True, exist_ok=True)
    OUT_TXT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote: {OUT_TXT}", file=sys.stderr)

    md = []
    md.append("# 漢字 → カタカナ外来語 当て字 Audit (= summary)")
    md.append("")
    md.append(f"records scanned: **{n_records:,}**")
    md.append(f"unique (title, kana): **{len(seen):,}**")
    md.append("")
    md.append("## カテゴリ件数")
    md.append("")
    md.append("| カテゴリ | 件数 | 意味 |")
    md.append("|---|---|---|")
    md.append(f"| ok | {stats.get('ok', 0):,} | pykakasi 標準読み = フリガナ (= 通常) |")
    md.append(f"| no_kanji | {stats.get('no_kanji', 0):,} | title に 漢字なし (= 対象外) |")
    md.append(f"| kanji_unread | {stats.get('kanji_unread', 0):,} | pykakasi 読めず (= 判定不能) |")
    md.append(f"| **ateji_kata** | **{stats.get('ateji_kata', 0):,}** | **漢字 → カタカナ外来語当て字 ★本命** |")
    md.append(f"| ateji_mixed | {stats.get('ateji_mixed', 0):,} | 漢字 → ひらがな混在当て字 (= 純和語当て字、 B-1a で OK) |")
    md.append("")
    md.append("## ateji_kata サンプル 先頭 50 件")
    md.append("")
    md.append("| MADB ID | title | 標準読み | 実フリガナ |")
    md.append("|---|---|---|---|")
    for r in ateji_kata[:50]:
        md.append(f"| {r['id']} | {r['title'][:30]} | {r['predicted'][:30]} | {r['kana'][:30]} |")
    if len(ateji_kata) > 50:
        md.append(f"| ... | ({len(ateji_kata)} 件 合計) | | |")
    md.append("")
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"wrote: {OUT_MD}", file=sys.stderr)

    print(f"\n=== SUMMARY ===", file=sys.stderr)
    for k in ["ok", "no_kanji", "no_kana", "kanji_unread", "ateji_kata", "ateji_mixed"]:
        print(f"  {k:14}: {stats.get(k, 0):>7,}", file=sys.stderr)


if __name__ == "__main__":
    main()
