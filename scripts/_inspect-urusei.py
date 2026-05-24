"""metadata104 から 指定 title family 全 シリーズ entity 抽出 + 採用/排除分類。"""
from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

SRC = Path(".cache/madb/metadata104.json")
MANGAKA_CSV = Path("data/seed/mangaka.csv")


def normalize_name(s: str) -> str:
    """name 比較用 normalize = NFKC + 空白/中黒/記号 除去 + lowercase。"""
    n = unicodedata.normalize("NFKC", s)
    return re.sub(r"[\s　・,，、.\-_'’]+", "", n).lower()


def load_mangaka_names() -> set[str]:
    """mangaka.csv から 全 name + alt_names を normalize して set 化。"""
    names: set[str] = set()
    with MANGAKA_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            n = row.get("name", "").strip()
            if n:
                names.add(normalize_name(n))
            alt = row.get("alt_names", "").strip()
            if alt:
                for a in alt.split("|"):
                    a = a.strip()
                    if a:
                        names.add(normalize_name(a))
    return names


MANGAKA_NAMES = load_mangaka_names()
print(f"[mangaka.csv] loaded {len(MANGAKA_NAMES):,} normalized names", file=sys.stderr)


def load_bookcount() -> dict[str, tuple[int, int]]:
    """metadata101 集計結果 (= series_id → (volume_unique, record_count)) を load。"""
    p = Path(".cache/series-bookcount.tsv")
    if not p.exists():
        print("[bookcount] .cache/series-bookcount.tsv 不在、 真巻数 表示なし", file=sys.stderr)
        return {}
    bc: dict[str, tuple[int, int]] = {}
    with p.open(encoding="utf-8") as f:
        next(f)  # header
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                bc[parts[0]] = (int(parts[1]), int(parts[2]))
    return bc


SERIES_BOOKCOUNT = load_bookcount()
print(f"[bookcount] loaded {len(SERIES_BOOKCOUNT):,} series 真巻数", file=sys.stderr)

VERSION_DROP_KEYWORDS = ["アニメ", "劇場", "映画", "OVA", "TV", "テレビ", "フィルム", "ノベライズ", "ノベル", "小説"]
# brand 排除 keyword (= CLAUDE.md L195-222 + 今回発見)
BRAND_DROP_KEYWORDS = [
    # アニメ系
    "アニメ版", "アニメコミック", "フィルムコミック", "TVアニメ", "劇場版", "ANIME",
    # 廉価版 / 限定 (= CLAUDE.md L196 同期)
    "My first big", "コンビニ", "増刊", "同人", "ジャンプremix", "bilingual",
    # ファンブック / 設定資料
    "グラフィック",
    # ノベル / 小説
    "novels", "novel", "小説",
    # ムック誌 (= 雑誌系、 漫画ではない 慣例)
    "mook", "ムック",
    # ファンブック企画 brand (= ダイアプレス系 ムック)
    "DIA Collection", "Consideration Books",
]
# title prefix 排除 (= CLAUDE.md L195 同期)
TITLE_DROP_PREFIX = [
    "テレビアニメ版", "TVアニメ版", "TVアニメ", "アニメコミック",
    "劇場版", "映画", "OVA",
    "ノベライズ", "ノベル", "小説",
    "英訳",
]
# title CONTAINS 排除 (= CLAUDE.md L222 同期)
TITLE_DROP_CONTAINS = [
    "ガイドブック", "ファンブック", "設定資料集",
    "公式図録", "公式読本", "公式ファン", "公式コミックガイド",
    "アンソロジー", "キャラクター名鑑", "人物名鑑",
    "心理分析", "心理解析", "完全解析", "完全攻略", "攻略本",
    "解析書", "解体新書", "解体全書",
    "大研究", "最終研究", "超研究", "大事典", "大百科", "大解剖",
    "パーフェクトガイド", "完全読本", "完全ガイド", "必勝法",
    "の秘密", "の謎", "コミック大全", "コミックスペシャル",
    "ナビゲーション", "考察",
    "空想科学読本",
]
CREATOR_NON_AUTHOR_ROLES = {
    "[カバー]", "[カバー・イラスト]", "[カバー・デザイン]", "[デザイン]",
    "[イラスト]", "[原作]", "[原作者]", "[原案]", "[企画]", "[企画制作]",
    "[編集]", "[構成]", "[脚本]", "[制作]", "[監修]", "[協力]",
    "[キャラクター・デザイン]", "[ほか原作]",
}

# creator name に これらの 集団名 keyword 含めば 漫画家不在 認定 (= 「[著]研究会」 等の 評論本対策)
NON_AUTHOR_NAME_KEYWORDS = [
    "研究会", "研究所", "研究班", "調査兵団", "ギルド", "同好会", "漫研団",
    "解読班", "編集部", "研究家",
]
# title CONTAINS 追加 keyword (= 進撃の巨人 audit で 発見)
EXTRA_TITLE_CONTAINS = [
    "空想科学読本",
]


def normalize_brand(s: str) -> str:
    """brand を 空白 / 中黒 除去 して 比較用 normalize。"""
    return re.sub(r"[\s　・]+", "", s)

import argparse
_parser = argparse.ArgumentParser()
_parser.add_argument("title", nargs="?", default="うる星やつら",
                    help="title 部分一致で family を 抽出 (= default: うる星やつら)")
_args = _parser.parse_args()
TARGET_TITLE = _args.title

RECORD_START = re.compile(r"^    \{")
RECORD_END = re.compile(r"^    \},?")


def parse_records():
    in_rec = False
    cur_buf: list[str] = []
    with SRC.open(encoding="utf-8") as f:
        for line in f:
            if RECORD_START.match(line):
                in_rec = True
                cur_buf = [line]
                continue
            if not in_rec:
                continue
            cur_buf.append(line)
            if RECORD_END.match(line):
                text = "".join(cur_buf)
                yield text
                in_rec = False


def has_drop(s: str, keywords: list[str]) -> str:
    for kw in keywords:
        if kw in s:
            return kw
    return ""


def has_drop_brand(brand_raw: str, keywords: list[str]) -> str:
    """brand 比較 = 空白除去 + lowercase で 比較 (= 「BILINGUAL」 ↔ 「bilingual」、 「アニメ バン」 ↔ 「アニメ版」)。"""
    norm = normalize_brand(brand_raw).lower()
    for kw in keywords:
        if normalize_brand(kw).lower() in norm:
            return kw
    return ""


def extract_field(text: str, key: str) -> str:
    """単純 inline string field 抽出 (= "key": "value")."""
    m = re.search(rf'"{re.escape(key)}":\s*"((?:[^"\\]|\\.)*)"', text)
    if m:
        return json.loads(f'"{m.group(1)}"')
    return ""


def extract_array(text: str, key: str) -> list[str]:
    """key の 配列から **トップレベル string entry のみ** 抽出 (= @value / @language 等は 弾く)。
    """
    pat = re.compile(rf'"{re.escape(key)}":\s*\[(.*?)\]', re.S)
    m = pat.search(text)
    if not m:
        return []
    body = m.group(1)
    items = []
    depth = 0
    for line in body.splitlines():
        for ch in line:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
        if depth != 0:
            continue
        sm = re.match(r'^\s*"((?:[^"\\]|\\.)*)"\s*,?\s*$', line)
        if sm:
            items.append(json.loads(f'"{sm.group(1)}"'))
    return items


def extract_all_text(text: str, key: str) -> list[str]:
    """key の 全 string (= トップ + ネスト @value)。 ja-hrkt カナ表記 も含む。"""
    # inline string か 配列 か 判定
    inline = re.search(rf'"{re.escape(key)}":\s*"((?:[^"\\]|\\.)*)"', text)
    if inline:
        return [json.loads(f'"{inline.group(1)}"')]
    pat = re.compile(rf'"{re.escape(key)}":\s*\[(.*?)\n      \]', re.S)
    m = pat.search(text)
    if not m:
        return []
    body = m.group(1)
    items = []
    # トップレベル string entry (= indent 8 + "...")
    for sm in re.finditer(r'^        "((?:[^"\\]|\\.)*)"\s*,?\s*$', body, re.M):
        items.append(json.loads(f'"{sm.group(1)}"'))
    # @value (= ネスト object 内の カナ表記等)
    for sm in re.finditer(r'"@value":\s*"((?:[^"\\]|\\.)*)"', body):
        items.append(json.loads(f'"{sm.group(1)}"'))
    return items


def main() -> None:
    matches = []
    for text in parse_records():
        label = extract_field(text, "rdfs:label")
        if not label or TARGET_TITLE not in label:
            continue
        sid_m = re.search(r'"@id":\s*"https://mediaarts-db\.artmuseums\.go\.jp/id/(C\d+)"', text)
        sid = sid_m.group(1) if sid_m else "?"
        version = extract_field(text, "schema:version")
        date = extract_field(text, "schema:datePublished")
        items = extract_field(text, "schema:numberOfItems")
        # creator (= 配列 or string)
        creators = extract_array(text, "schema:creator")
        if not creators:
            c = extract_field(text, "schema:creator")
            if c:
                creators = [c]
        # brand (= 全 text、 カナ表記も 含む)
        brands = extract_all_text(text, "schema:brand")
        # ma:seriesName / schema:alternateName (= 排除 keyword scan 対象、 ★ 新規)
        series_names = extract_all_text(text, "ma:seriesName")
        alt_names = extract_all_text(text, "schema:alternateName")
        # creator @id 群
        creator_ids = re.findall(r'"@id":\s*"https://mediaarts-db\.artmuseums\.go\.jp/id/(C\d+)"', text)
        primary_creator = creator_ids[1] if len(creator_ids) > 1 else ""  # 0番目は @id 自身

        # 排除 signal 判定
        signals = []
        v_kw = has_drop(version, VERSION_DROP_KEYWORDS)
        if v_kw:
            signals.append(f"version=「{version}」")
        for b in brands:
            b_kw = has_drop_brand(b, BRAND_DROP_KEYWORDS)
            if b_kw:
                signals.append(f"brand=「{b}」(= {b_kw})")
                break
        # ma:seriesName 排除 scan ★
        for sn in series_names:
            sn_kw = has_drop_brand(sn, BRAND_DROP_KEYWORDS)
            if sn_kw:
                signals.append(f"seriesName=「{sn}」(= {sn_kw})")
                break
        # schema:alternateName 排除 scan ★
        for an in alt_names:
            an_kw = has_drop_brand(an, BRAND_DROP_KEYWORDS)
            if an_kw:
                signals.append(f"altName=「{an}」(= {an_kw})")
                break
        # title prefix / contains
        for pat in TITLE_DROP_PREFIX:
            if label.startswith(pat):
                signals.append(f"title-prefix=「{pat}」")
                break
        for pat in TITLE_DROP_CONTAINS:
            if pat in label:
                signals.append(f"title-contains=「{pat}」")
                break
        if creators:
            has_author = False
            has_mangaka_match = False
            mangaka_check_names: list[str] = []
            for c in creators:
                m = re.match(r"^(\[[^\]]+\])(.*)$", c)
                if m:
                    role, name = m.group(1), m.group(2)
                    if role in CREATOR_NON_AUTHOR_ROLES:
                        continue
                    # [著] でも name に 「研究会」 等 集団名 含めば 漫画家不在 認定
                    name_norm = name.strip().strip("　 ")
                    if any(kw in name_norm for kw in NON_AUTHOR_NAME_KEYWORDS):
                        continue
                    mangaka_check_names.append(name_norm)
                else:
                    mangaka_check_names.append(c.strip())
                has_author = True
            # mangaka.csv 一致 check (= 1 つでも 一致あれば 漫画家本人確定)
            for n in mangaka_check_names:
                if normalize_name(n) in MANGAKA_NAMES:
                    has_mangaka_match = True
                    break
            if not has_author:
                signals.append("creator=漫画家不在")
            elif mangaka_check_names and not has_mangaka_match:
                # 「[著]」 だが mangaka.csv 不在 = 漫画家以外の 個人著者 (= 評論家 等)
                signals.append(f"mangaka.csv不在=「{','.join(mangaka_check_names[:3])}」")

        matches.append({
            "id": sid,
            "title": label,
            "date": date,
            "items": items,
            "creator": " / ".join(creators),
            "brand": " / ".join(brands),
            "version": version,
            "primary_creator_id": primary_creator,
            "n_creators": len(creator_ids) - 1,
            "signals": signals,
        })

    matches.sort(key=lambda x: (x["date"] or "9999", x["id"]))

    print(f"= 「{TARGET_TITLE}」 family = {len(matches)} シリーズ =\n")

    keep = [m for m in matches if not m["signals"]]
    drop = [m for m in matches if m["signals"]]

    print(f"## 採用候補 (= 排除 signal なし) = {len(keep)} 件\n")
    for m in keep:
        print(f"  [{m['id']}] {m['title']}")
        bc = SERIES_BOOKCOUNT.get(m['id'], (0, 0))
        n_disp = f"MADB={m['items']:>3} / 真={bc[0]:>3}巻 ({bc[1]}件)"
        print(f"    開始: {m['date']:>10} | {n_disp} | creators: {m['n_creators']}")
        print(f"    creator: {m['creator']}")
        print(f"    brand: {m['brand']}")
        print(f"    version: {m['version']}")
        print()

    print(f"\n## 排除候補 (= 派生 signal あり) = {len(drop)} 件\n")
    for m in drop:
        print(f"  [{m['id']}] {m['title']}")
        bc = SERIES_BOOKCOUNT.get(m['id'], (0, 0))
        n_disp = f"MADB={m['items']:>3} / 真={bc[0]:>3}巻 ({bc[1]}件)"
        print(f"    開始: {m['date']:>10} | {n_disp}")
        print(f"    creator: {m['creator'][:80]}")
        print(f"    brand: {m['brand']}")
        print(f"    version: {m['version']}")
        print(f"    signals: {' + '.join(m['signals'])}")
        print()


if __name__ == "__main__":
    main()
