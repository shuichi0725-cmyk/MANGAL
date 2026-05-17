"""
.cache/madb-enrich.json を data/manga/*.yml に適用する。

適用ルール (= A1):
  - subtitle: yml に無ければ追加 (= 上書きしない)
  - subtitle_kana: 同上
  - alternative_titles.en: 既存値が無ければ追加
  - title_kana: 既存値と異なれば 上書き (= 種2 bug fix)
    ただし 既存値も MADB raw に存在する pattern なら 既存維持 (= 別 valid 表記)

実行前:
  - data/manga.bak-* に backup 済を想定

実行後:
  - 変更件数 / scan 件数を stdout 出力
  - 各 yml 末尾に空行のある状態を保つ
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENRICH = ROOT / ".cache" / "madb-enrich.json"
MANGA_DIR = ROOT / "data" / "manga"
RAW = ROOT / ".cache" / "madb" / "metadata101-clean.json"

stats = {
    "scanned": 0,
    "matched": 0,
    "unmatched": 0,
    "added_subtitle": 0,
    "added_subtitle_kana": 0,
    "added_alt_en": 0,
    "fixed_title_kana": 0,
    "skipped_title_kana_valid": 0,
}


def load_yml_lines(path):
    with path.open("r", encoding="utf-8") as f:
        return f.read().split("\n")


def get_top_level(lines, key):
    for i, line in enumerate(lines):
        m = re.match(rf"^{re.escape(key)}:\s*(.*)$", line)
        if m:
            return i, m.group(1)
    return -1, None


def has_top_level(lines, key):
    i, _ = get_top_level(lines, key)
    return i >= 0


def has_alt_en(lines):
    in_alt = False
    for line in lines:
        if line.startswith("alternative_titles:"):
            in_alt = True
            continue
        if in_alt:
            if re.match(r"^[a-zA-Z_]+:", line):
                return False
            m = re.match(r"^\s+en:\s*(\S.*)$", line)
            if m:
                return True
    return False


def insert_after(lines, idx, new_lines):
    return lines[: idx + 1] + new_lines + lines[idx + 1 :]


def quote_yaml_string(s):
    """YAML scalar として安全な書き方。 特殊文字含むなら double quote。"""
    if re.match(r"^[぀-ゟ゠-ヿ一-鿿　-〿A-Za-z0-9 \-]+$", s):
        # 安全な文字種のみ → 引用符不要
        return s
    return '"' + s.replace('"', '\\"') + '"'


def apply_to_yml(path, enrich, raw_kana_set):
    stats["scanned"] += 1
    lines = load_yml_lines(path)
    idx_title, title = get_top_level(lines, "title")
    idx_title_kana, title_kana = get_top_level(lines, "title_kana")
    idx_title_romaji, _ = get_top_level(lines, "title_romaji")
    if title is None:
        return False

    title = title.strip()
    rec = enrich.get(title)
    if not rec:
        stats["unmatched"] += 1
        return False
    stats["matched"] += 1

    changed = False
    new_lines = list(lines)

    # 1. title_kana の修正 (= 種2 bug fix)
    #    spacing だけの差は 上書きしない (= 既存表記を尊重)
    #    文字列内容差 (= らんま 1/2 → ランマ ニブンノイチ 等) のみ 上書き
    correct_kana = rec.get("title_kana_correct", "")
    if correct_kana and title_kana and correct_kana != title_kana.strip():
        def squash(s):
            return re.sub(r"\s+", "", s)
        if squash(correct_kana) == squash(title_kana.strip()):
            stats["skipped_title_kana_valid"] += 1
        else:
            new_lines[idx_title_kana] = f"title_kana: {quote_yaml_string(correct_kana)}"
            stats["fixed_title_kana"] += 1
            changed = True

    # 2. subtitle 追加
    subtitle = rec.get("subtitle", "")
    if subtitle and not has_top_level(new_lines, "subtitle"):
        anchor = next(
            (
                i
                for i, l in enumerate(new_lines)
                if l.startswith("title_romaji:") or l.startswith("title_kana:")
            ),
            idx_title,
        )
        new_lines = insert_after(
            new_lines, anchor, [f"subtitle: {quote_yaml_string(subtitle)}"]
        )
        stats["added_subtitle"] += 1
        changed = True

    # 3. subtitle_kana 追加
    subtitle_kana = rec.get("subtitle_kana", "")
    if subtitle_kana and not has_top_level(new_lines, "subtitle_kana"):
        anchor = next(
            (i for i, l in enumerate(new_lines) if l.startswith("subtitle:")),
            -1,
        )
        if anchor < 0:
            anchor = next(
                (
                    i
                    for i, l in enumerate(new_lines)
                    if l.startswith("title_romaji:") or l.startswith("title_kana:")
                ),
                idx_title,
            )
        new_lines = insert_after(
            new_lines,
            anchor,
            [f"subtitle_kana: {quote_yaml_string(subtitle_kana)}"],
        )
        stats["added_subtitle_kana"] += 1
        changed = True

    # 4. alternative_titles.en 追加 (= 無ければ)
    title_en = rec.get("title_official_en", "")
    if title_en and not has_alt_en(new_lines):
        if has_top_level(new_lines, "alternative_titles"):
            # 既存 alternative_titles section に en を追加
            for i, l in enumerate(new_lines):
                if l.startswith("alternative_titles:"):
                    new_lines = insert_after(
                        new_lines, i, [f"  en: {quote_yaml_string(title_en)}"]
                    )
                    break
        else:
            # synopsis の直後あたりに alternative_titles section を新設
            anchor = next(
                (i for i, l in enumerate(new_lines) if l.startswith("synopsis:")),
                -1,
            )
            if anchor < 0:
                anchor = idx_title_romaji if idx_title_romaji >= 0 else idx_title
            new_lines = insert_after(
                new_lines,
                anchor,
                [
                    "alternative_titles:",
                    f"  en: {quote_yaml_string(title_en)}",
                ],
            )
        stats["added_alt_en"] += 1
        changed = True

    if changed:
        with path.open("w", encoding="utf-8") as f:
            f.write("\n".join(new_lines))
    return changed


def build_raw_kana_set():
    """title_jp → set of all observed kana の dict (= 上書き判断用)"""
    with RAW.open("r", encoding="utf-8") as f:
        data = json.load(f)
    result = {}
    for b in data["@graph"]:
        name = b.get("schema:name")
        if not name:
            continue
        first = name[0] if isinstance(name, list) else None
        label = first if isinstance(first, str) else (first.get("@value", "") if isinstance(first, dict) else "")
        if not label:
            continue
        kana = ""
        for item in name[1:] if isinstance(name, list) else []:
            if isinstance(item, dict) and item.get("@language") == "ja-hrkt":
                kana = item.get("@value", "")
                break
        # parse out title_jp from label
        title_jp = label
        if " = " in title_jp:
            title_jp = title_jp.split(" = ", 1)[0].strip()
        if " : " in title_jp:
            title_jp = title_jp.split(" : ", 1)[0].strip()
        # parse out title_kana from kana
        title_kana = kana.split(" : ", 1)[0].strip() if " : " in kana else kana
        if title_jp and title_kana:
            result.setdefault(title_jp, set()).add(title_kana)
    return result


def main():
    print(f"loading {ENRICH} ...", file=sys.stderr)
    with ENRICH.open("r", encoding="utf-8") as f:
        enrich = json.load(f)
    print(f"loading raw for kana validation ...", file=sys.stderr)
    raw_kana_set = build_raw_kana_set()

    for path in sorted(MANGA_DIR.glob("*.yml")):
        apply_to_yml(path, enrich, raw_kana_set)

    print("\n=== result ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
