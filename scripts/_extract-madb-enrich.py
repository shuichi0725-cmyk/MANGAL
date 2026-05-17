"""
MADB raw (= .cache/madb/metadata101-clean.json) から series 単位で
enrichment 情報を抽出し .cache/madb-enrich.json に出力する。

抽出する情報 (= A1 scope):
  - title_jp         : 主題 (= name[0] の `=` 左 + ` : ` 左)
  - title_official_en: 公式英語題 (= name[0] の `=` 右)
  - subtitle         : 副題 (= name[0] の ` : ` 右)
  - title_kana       : 主題ふりがな 最頻値 (= name[ja-hrkt] の ` : ` 左)
  - subtitle_kana    : 副題ふりがな 最頻値 (= name[ja-hrkt] の ` : ` 右)

集約 strategy (= D 案):
  - subtitle, subtitle_kana, title_official_en: 全 book で値が一致したら採用、 不一致なら null
  - title_kana: 最頻値採用 (= 50% 以上なら採用)
"""

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / ".cache" / "madb" / "metadata101-clean.json"
OUT = ROOT / ".cache" / "madb-enrich.json"


def get_label(name):
    if not name:
        return ""
    if isinstance(name, str):
        return name
    if isinstance(name, list) and len(name) > 0:
        first = name[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("@value", "")
    return ""


def get_kana(name):
    if not name or not isinstance(name, list):
        return ""
    for item in name:
        if isinstance(item, dict) and item.get("@language") == "ja-hrkt":
            return item.get("@value", "")
    return ""


def parse_label(label):
    """name[0] → (title_jp, title_en, subtitle_jp)"""
    title_en = ""
    subtitle_jp = ""
    if " = " in label:
        parts = label.split(" = ", 1)
        title_jp = parts[0].strip()
        rest = parts[1].strip()
        if " : " in rest:
            en_part, sub_jp = rest.split(" : ", 1)
            title_en = en_part.strip()
            subtitle_jp = sub_jp.strip()
        else:
            title_en = rest
    else:
        title_jp = label.strip()
        if " : " in title_jp:
            t, s = title_jp.split(" : ", 1)
            title_jp = t.strip()
            subtitle_jp = s.strip()
    return title_jp, title_en, subtitle_jp


def parse_kana(kana):
    """kana → (title_kana, subtitle_kana)"""
    if " : " in kana:
        t, s = kana.split(" : ", 1)
        return t.strip(), s.strip()
    return kana, ""


def aggregate(books):
    """同一 title_jp の book 群 → 集約値
    - subtitle / subtitle_kana / title_en: 全一致時のみ採用
    - title_kana: 最頻値採用
    """

    def majority_value(vals, threshold=0.5):
        """空文字列を含めた全 book 中で 最頻値が threshold 以上なら採用。
        - キングダム例: 13% が "完全版"、 87% が "" → top "" が勝つ → "" 返却
        - 半妖の夜叉姫例: 78% が "異伝・絵本草子" → top 採用 → 副題返却
        旧実装の strict all_agree は MADB の data 揺れで弱すぎ、
        旧 majority は空文字列を pre-filter して 13% でも採用してしまう bug があった。"""
        if not vals:
            return ""
        c = Counter(vals)
        top, top_cnt = c.most_common(1)[0]
        if top_cnt / len(vals) >= threshold:
            return top
        return ""

    def majority_nonempty(vals):
        """空を除外して 最頻値採用 (= title_kana 用、 空 kana 本は除外して 多数決)。"""
        s = [v for v in vals if v]
        if not s:
            return ""
        c = Counter(s)
        top, top_cnt = c.most_common(1)[0]
        if top_cnt * 2 >= len(s):
            return top
        return ""

    return {
        "title_official_en": majority_value([b["title_en"] for b in books]),
        "subtitle": majority_value([b["subtitle_jp"] for b in books]),
        "subtitle_kana": majority_value([b["subtitle_kana"] for b in books]),
        "title_kana_correct": majority_nonempty([b["title_kana"] for b in books]),
        "n_books": len(books),
    }


def main():
    print(f"loading {RAW} ...", file=sys.stderr)
    with RAW.open("r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"raw books: {len(data['@graph'])}", file=sys.stderr)

    groups = {}
    for b in data["@graph"]:
        name = b.get("schema:name")
        label = get_label(name)
        if not label:
            continue
        kana = get_kana(name)
        title_jp, title_en, subtitle_jp = parse_label(label)
        title_kana, subtitle_kana = parse_kana(kana)
        if not title_jp:
            continue
        rec = {
            "title_en": title_en,
            "subtitle_jp": subtitle_jp,
            "title_kana": title_kana,
            "subtitle_kana": subtitle_kana,
        }
        groups.setdefault(title_jp, []).append(rec)

    print(f"unique series-level titles: {len(groups)}", file=sys.stderr)

    result = {}
    has_subtitle = 0
    has_official_en = 0
    for title_jp, books in groups.items():
        agg = aggregate(books)
        result[title_jp] = agg
        if agg["subtitle"]:
            has_subtitle += 1
        if agg["title_official_en"]:
            has_official_en += 1

    print(
        f"series with subtitle: {has_subtitle} ({has_subtitle*100/len(groups):.1f}%)",
        file=sys.stderr,
    )
    print(
        f"series with official_en: {has_official_en} ({has_official_en*100/len(groups):.1f}%)",
        file=sys.stderr,
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"wrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
