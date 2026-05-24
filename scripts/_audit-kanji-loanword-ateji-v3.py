"""漢字 → カタカナ外来語当て字 audit v3 (= book副題排除 logic 追加)。

v2 比改善:
- n_books (= 同 series の book record 数) を 集計
- 多巻シリーズ (= n_books >= 2) では 「2 巻以上 で 共通する ja-hrkt entry」 のみ 採用
- 単独完結 (= n_books == 1) は 全 entry 採用 (= 短編 / 読み切り 救済)
- 「鬼平犯科帳 114 巻だけの 副題」 のような book 単位 副題 を 排除

source: .cache/madb/metadata101.json

カテゴリ:
  ok           : 全 共有 ja-hrkt = 標準読み
  has_both     : ★ 普通読み + 当て字 両方 共有 = MADB 公式当て字
  ateji_only   : 当て字のみ
  no_kanji / no_kana / kanji_unread

Output:
  .cache/audit-kanji-loanword-ateji-v3.txt
  .cache/audit-kanji-loanword-ateji-v3-summary.md
  .cache/seed3-kana-fill-source-v3.tsv
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
OUT_TXT = ROOT / ".cache" / "audit-kanji-loanword-ateji-v3.txt"
OUT_MD = ROOT / ".cache" / "audit-kanji-loanword-ateji-v3-summary.md"
OUT_FILL = ROOT / ".cache" / "seed3-kana-fill-source-v3.tsv"

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
    """yield (madb_id, label, kana_jahrkt_list, creator_id)。"""
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
    # series-key → {n_books, kana_freq, mid (= first), creator, title_core}
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
                "n_books": 0,
                "kana_freq": Counter(),
            }
        seen[key]["n_books"] += 1
        # 1 book record 内で 同じ entry を 多重 count しない (= set 化)
        unique_in_book: set[str] = set()
        for k in kana_list:
            stripped = strip_kana_suffix(k)
            if stripped:
                unique_in_book.add(stripped)
        for k in unique_in_book:
            seen[key]["kana_freq"][k] += 1
        if n_records % 50000 == 0:
            print(f"  scanned: {n_records}", file=sys.stderr)

    print(f"records scanned: {n_records}", file=sys.stderr)
    print(f"unique series (creator, title_core): {len(seen)}", file=sys.stderr)

    stats: Counter = Counter()
    has_both: list[dict] = []
    ateji_only: list[dict] = []
    fill_rows: list[tuple[str, str, str, int]] = []  # (key, title, preferred_kana, n_books)

    n_books_dist: Counter = Counter()
    excluded_book_only: Counter = Counter()  # 排除した entry の 累計

    for key, info in seen.items():
        title_core = info["title_core"]
        creator = info["creator"]
        mid = info["mid"]
        n_books = info["n_books"]
        kana_freq = info["kana_freq"]
        n_books_dist[min(n_books, 10)] += 1

        # シリーズ共通 kana の 抽出 (= 本 audit の 肝)
        if n_books == 1:
            # 単独完結 → 全 entry 採用
            shared = list(kana_freq.keys())
        else:
            # 多巻シリーズ → 2 巻以上で 共通 のみ
            shared = [k for k, c in kana_freq.items() if c >= 2]
            for k, c in kana_freq.items():
                if c == 1:
                    excluded_book_only[c] += 1

        kana_list = sorted(shared)
        preferred_kana = ""

        if not kana_list:
            stats["no_kana"] += 1
            continue
        if not KANJI_RE.search(title_core):
            stats["no_kanji"] += 1
            preferred_kana = re.sub(r"[\s　]+", "", kana_list[0])
            fill_rows.append((f"{creator}|{title_core}", title_core, preferred_kana, n_books))
            continue

        predicted = predict_kana(title_core)
        if KANJI_RE.search(predicted):
            stats["kanji_unread"] += 1
            preferred_kana = re.sub(r"[\s　]+", "", kana_list[0])
            fill_rows.append((f"{creator}|{title_core}", title_core, preferred_kana, n_books))
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
            preferred_kana = non_matches[0]
            ateji_only.append({
                "id": mid, "creator": creator, "title": title_core,
                "predicted": predicted, "kana_list": kana_list,
                "n_books": n_books,
            })
        else:
            stats["has_both"] += 1
            preferred_kana = non_matches[0]  # ★ 当て字優先
            has_both.append({
                "id": mid, "creator": creator, "title": title_core,
                "predicted": predicted, "normal": matches, "ateji": non_matches,
                "n_books": n_books,
            })

        preferred_kana_compact = re.sub(r"[\s　]+", "", preferred_kana)
        fill_rows.append((f"{creator}|{title_core}", title_core, preferred_kana_compact, n_books))

    # fill source TSV
    with OUT_FILL.open("w", encoding="utf-8") as f:
        f.write("series_key\ttitle_core\tpreferred_kana\tn_books\n")
        for r in fill_rows:
            f.write(f"{r[0]}\t{r[1]}\t{r[2]}\t{r[3]}\n")
    print(f"wrote: {OUT_FILL} ({len(fill_rows):,} rows)", file=sys.stderr)

    # txt
    lines = []
    lines.append("# 漢字 → カタカナ外来語当て字 Audit v3 (= book副題排除)")
    lines.append("")
    lines.append(f"records scanned: {n_records:,}")
    lines.append(f"unique series: {len(seen):,}")
    lines.append("")
    lines.append("## n_books 分布")
    for k in sorted(n_books_dist.keys()):
        label = f"{k}+" if k == 10 else str(k)
        lines.append(f"  n_books={label:>3}: {n_books_dist[k]:>7,}")
    lines.append("")
    lines.append("## カテゴリ件数")
    for k in ["ok", "no_kanji", "no_kana", "kanji_unread", "has_both", "ateji_only"]:
        lines.append(f"  {k:14}: {stats.get(k, 0):>7,}")
    lines.append("")
    lines.append("## has_both 全件 (= ★ MADB 公式当て字)")
    lines.append("")
    for r in has_both:
        lines.append(f"  [{r['id']}] (n={r['n_books']}) {r['title']}")
        lines.append(f"    predicted: {r['predicted']}")
        lines.append(f"    normal:    {r['normal']}")
        lines.append(f"    ateji:     {r['ateji']}")
        lines.append("")
    lines.append("")
    lines.append("## ateji_only サンプル 200 件")
    lines.append("")
    for r in ateji_only[:200]:
        lines.append(f"  [{r['id']}] (n={r['n_books']}) {r['title']}")
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
    md.append("# 漢字 → カタカナ外来語当て字 Audit v3 (= summary)")
    md.append("")
    md.append(f"records scanned: **{n_records:,}**")
    md.append(f"unique series: **{len(seen):,}**")
    md.append("")
    md.append("## n_books 分布")
    md.append("")
    md.append("| n_books | series 数 |")
    md.append("|---|---|")
    for k in sorted(n_books_dist.keys()):
        label = f"{k}+" if k == 10 else str(k)
        md.append(f"| {label} | {n_books_dist[k]:,} |")
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
    md.append("")
    md.append("## has_both 先頭 100 件 (= ★ MADB 公式当て字、 mini 辞書 seed)")
    md.append("")
    md.append("| MADB ID | n | title | 普通読み | 当て字 |")
    md.append("|---|---|---|---|---|")
    for r in has_both[:100]:
        n = " / ".join(r["normal"])[:40]
        a = " / ".join(r["ateji"])[:40]
        md.append(f"| {r['id']} | {r['n_books']} | {r['title'][:30]} | {n} | {a} |")
    if len(has_both) > 100:
        md.append(f"| ... | | ({len(has_both)} 件 合計) | | |")
    md.append("")
    md.append("## ateji_only サンプル 50 件")
    md.append("")
    md.append("| MADB ID | n | title | 標準読み | フリガナ |")
    md.append("|---|---|---|---|---|")
    for r in ateji_only[:50]:
        klst = " / ".join(r["kana_list"])[:40]
        md.append(f"| {r['id']} | {r['n_books']} | {r['title'][:30]} | {r['predicted'][:30]} | {klst} |")
    if len(ateji_only) > 50:
        md.append(f"| ... | | ({len(ateji_only)} 件 合計) | | |")
    md.append("")
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"wrote: {OUT_MD}", file=sys.stderr)

    print(f"\n=== SUMMARY ===", file=sys.stderr)
    for k in ["ok", "no_kanji", "no_kana", "kanji_unread", "has_both", "ateji_only"]:
        print(f"  {k:14}: {stats.get(k, 0):>7,}", file=sys.stderr)


if __name__ == "__main__":
    main()
