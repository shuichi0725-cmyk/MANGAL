#!/usr/bin/env python3
"""著者の読み(ヨミ)を AniList dump から抽出 (= 50音索引の土台。 ★未適用/レビュー用)。

AniList staff = name.full(ローマ字 "Kentarou Miura")+ name.native(漢字 "三浦建太郎")。
full を 姓名(日本語順)に並べ replace、 jaconv で romaji→カタカナ = 読み。
★日本語native のみ変換。 latin native(CLAMP/ONE 等)は別扱い(アルファベット)。
出力: data/seeds/mangaka-yomi-anilist.yml (git追跡 seed、 {native: yomi})。
"""
import csv
import gzip
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import jaconv

ROOT = Path(__file__).resolve().parent.parent
DUMP = ROOT / ".cache" / "anilist-manga-dump-v3.jsonl.gz"
MANGAKA = ROOT / "data" / "seed" / "mangaka.csv"
MANGAKA_MADB = ROOT / "data" / "seed" / "mangaka-madb.csv"
OUT = ROOT / "data" / "seeds" / "mangaka-yomi-anilist.yml"

JP = re.compile(r"[぀-ゟ゠-ヿ一-鿿]")  # ひらがな/カタカナ/漢字


def is_japanese(s):
    return bool(JP.search(s or ""))


def romaji_to_yomi(full):
    """full(ローマ字 名+姓, 西洋順)→ 姓名(日本語順)カタカナ読み。"""
    toks = (full or "").strip().split()
    if len(toks) >= 2:
        rom = toks[-1] + "".join(toks[:-1])   # 姓 + 名
    else:
        rom = (full or "").strip()
    rom = rom.lower()
    for a, b in (("ō", "ou"), ("ū", "uu"), ("ā", "aa"), ("ē", "ei"), ("î", "ii"), ("ī", "ii"), ("â", "aa")):
        rom = rom.replace(a, b)
    rom = re.sub(r"[^a-z]", "", rom)
    if not rom:
        return ""
    return jaconv.hira2kata(jaconv.alphabet2kana(rom))


def norm(s):
    return re.sub(r"[\s　]+", "", (s or "")).strip()


def main():
    # 1. dump から staff {native: Counter(full)} 収集
    native_full = defaultdict(Counter)
    n_rec = 0
    with gzip.open(DUMP, "rt", encoding="utf-8") as f:
        for line in f:
            n_rec += 1
            try:
                rec = json.loads(line)
            except Exception:
                continue
            for e in (rec.get("staff") or {}).get("edges", []):
                nm = (e.get("node") or {}).get("name") or {}
                nat, full = nm.get("native"), nm.get("full")
                if nat and full:
                    native_full[norm(nat)][full] += 1
    print(f"dump {n_rec:,} 作品 / staff native ユニーク {len(native_full):,}", file=sys.stderr)

    # 2. 読み生成(日本語nativeのみ)
    yomi = {}
    latin = 0
    for nat, fulls in native_full.items():
        if not is_japanese(nat):
            latin += 1
            continue
        full = fulls.most_common(1)[0][0]
        y = romaji_to_yomi(full)
        if y:
            yomi[nat] = y
    print(f"読み生成: {len(yomi):,} (latin native除外 {latin:,})", file=sys.stderr)

    # 3. mangaka マスター突合カバレッジ
    master = set()
    for p in (MANGAKA, MANGAKA_MADB):
        if p.exists():
            for row in csv.DictReader(p.open(encoding="utf-8")):
                if row.get("name"):
                    master.add(norm(row["name"]))
    jp_master = {m for m in master if is_japanese(m)}
    covered = sum(1 for m in jp_master if m in yomi)
    print(f"mangakaマスター: {len(master):,} (日本語名 {len(jp_master):,})", file=sys.stderr)
    print(f"  AniListで読み付与可: {covered:,} / {len(jp_master):,} ({covered*100//max(1,len(jp_master))}%)", file=sys.stderr)

    # 4. 永続化(マスターに在る分のみ=本番対象)
    out = {m: yomi[m] for m in jp_master if m in yomi}
    OUT.write_text(
        "# 著者の読み(ヨミ・カタカナ)= AniList staff full(romaji)→かな逆変換。 ★50音索引用・未適用。\n"
        "# scripts/_extract-mangaka-yomi-anilist.py。 mangakaマスターに在る日本語著者のみ。 残りはNDL補完。\n"
        + json.dumps({"yomi": out}, ensure_ascii=False, indent=0),
        encoding="utf-8",
    )
    print(f"永続化: {OUT} ({len(out):,}件)", file=sys.stderr)

    # 5. 検証サンプル
    print("\n=== 検証サンプル(マスター在 × AniList読み) ===", file=sys.stderr)
    import itertools
    for nat in itertools.islice((m for m in sorted(jp_master) if m in yomi), 0, 15):
        print(f"  {nat}  →  {yomi[nat]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
