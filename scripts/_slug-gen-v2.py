#!/usr/bin/env python3
"""slug 生成器 v2 = 決定ロジック (= 7分岐 + 音写フィルタ + 衝突検出 + 信頼度)。

★適用しない。 確定slug候補を TSV 出力 → 人がレビュー → GO で別途適用。
v1 (_slug-gen-v1.py) の helper を再利用。 規則裁定: docs/anilist-match-slug-investigation.md C節、
CLAUDE.md「ローマ字化4規則」(★2026-06-10: 長音保持/を=o/敬称ハイフン/カタカナ=英綴り)。

決定 (class 別分岐):
  latin (題がほぼASCII)         → 題を直接 slug 化 (ONE PIECE→one-piece)         conf=high
  kata  (カタカナ外来語主体)     → ★音写フィルタで AniList romaji 元綴り採否       conf=high/review
                                   (音写=採用[berserk]、 非類似=ヘボンfallback)
  kanji / hira (既定)           → kana_slug (ヘボン、 segmented起点)              conf=high
  num   (数字含む)              → kana_slug + ★4分岐未実装 flag                  conf=review
  other / empty                → flag                                          conf=review
後段: 全件で slug 衝突を検出 (= -姓+年 suffix の対象、 本スクリプトは検出のみ)。
"""
import csv
import difflib
import importlib.util
import pickle
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKL = ROOT / ".cache" / "seed3-promote.pkl"
MATCH = ROOT / ".cache" / "match-v14-all.tsv"
OUT = ROOT / ".cache" / "slug-gen-v2.tsv"
S = {"S180", "S150", "S130", "S100"}


def _load_v1():
    spec = importlib.util.spec_from_file_location("sg1", ROOT / "scripts" / "_slug-gen-v1.py")
    m = importlib.util.module_from_spec(spec)
    sys.argv = ["x"]
    spec.loader.exec_module(m)
    return m


v1 = _load_v1()


def consonant_skel(s):
    return re.sub(r"[aeiou\W_]", "", (s or "").lower())


def is_onsha(latin_slug, title_kana):
    """latin が title_kana の音写か = 子音骨格の類似度 (0..1)。 1=完全一致。"""
    a = consonant_skel(latin_slug)
    b = consonant_skel(v1.drop_long(v1.hep(title_kana)))
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def decide(title, seg, title_kana, a_rom_slug, a_eng_slug):
    """→ (slug, source, conf, onsha_ratio)。"""
    cls = v1.classify(title)
    ks = v1.kana_slug(seg) if seg else v1.slugify_latin(v1.hep(title_kana))

    if cls == "latin":
        return v1.slugify_latin(title), "latin-title", "high", ""
    if cls == "num":
        return ks, "kana-num", "review", ""  # ★4分岐(音読み数詞/訓読み助数詞/特殊/英語読み)未実装
    if cls == "kata":
        if a_rom_slug:
            r = is_onsha(a_rom_slug, title_kana)
            if r >= 0.70:
                return a_rom_slug, "anilist-romaji", "high", f"{r:.2f}"
            if r >= 0.45:
                return a_rom_slug, "anilist-romaji", "review", f"{r:.2f}"
        if a_eng_slug:
            r = is_onsha(a_eng_slug, title_kana)
            if r >= 0.70:
                return a_eng_slug, "anilist-english", "review", f"{r:.2f}"
        return ks, "kana-fallback", "high" if ks else "review", ""
    # kanji / hira / other
    if not ks:
        return "", "empty", "review", ""
    return ks, "kana-hepburn", "high" if cls in ("kanji", "hira") else "review", ""


def main():
    d = pickle.load(PKL.open("rb"))
    a_rom, a_eng = {}, {}
    with MATCH.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["verdict"] in S:
                if r.get("a_romaji"):
                    a_rom[r["s3_key"]] = r["a_romaji"]
                if r.get("a_english"):
                    a_eng[r["s3_key"]] = r["a_english"]

    rows = []
    src_count, conf_count = Counter(), Counter()
    slug_groups = defaultdict(list)
    for e in d.values():
        key = e["key"]
        title = v1.base_title(key)
        seg = e.get("title_kana_segmented") or e.get("title_kana") or ""
        tk = re.sub(r"[\s　]+", "", e.get("title_kana") or seg)
        ars = v1.slugify_latin(a_rom.get(key, ""))
        aes = v1.slugify_latin(a_eng.get(key, ""))
        slug, src, conf, ratio = decide(title, seg, tk, ars, aes)
        src_count[src] += 1
        conf_count[conf] += 1
        if slug:
            slug_groups[slug].append(title)
        rows.append((key, title, v1.classify(title), slug, src, conf, ratio, v1.kana_slug(seg) if seg else "", ars, aes))

    # 衝突
    collisions = {s: ts for s, ts in slug_groups.items() if len(ts) > 1}
    coll_keys = set()
    for s in collisions:
        coll_keys.add(s)

    with OUT.open("w", encoding="utf-8") as f:
        f.write("key\ttitle\tclass\tslug\tsource\tconf\tonsha\tkana_slug\ta_romaji\ta_english\tcollision\n")
        for row in rows:
            coll = "COLLIDE" if row[3] in coll_keys else ""
            f.write("\t".join(str(x) for x in row) + f"\t{coll}\n")

    print(f"=== 全 {len(rows):,} 件 → {OUT} (適用なし) ===")
    print("source(決定の由来):")
    for k, v in src_count.most_common():
        print(f"  {k}: {v:,} ({v*100//len(rows)}%)")
    print("confidence:")
    for k, v in conf_count.most_common():
        print(f"  {k}: {v:,} ({v*100//len(rows)}%)")
    coll_entry = sum(len(ts) for ts in collisions.values())
    print(f"衝突: {len(collisions):,} 群 / {coll_entry:,} entry (= -姓+年 suffix 対象、 本スクリプトは検出のみ)")

    print("\n=== CLAUDE.md 既知例の検証 ===")
    want = ["鬼滅の刃", "進撃の巨人", "七つの大罪", "ベルセルク", "ワンピース", "ONE PIECE",
            "東京喰種", "鋼の錬金術師", "ドラゴンボール", "幽☆遊☆白書", "らんま"]
    for w in want:
        hit = [r for r in rows if w in r[1]]
        if hit:
            r = sorted(hit, key=lambda x: len(x[1]))[0]
            print(f"  {r[1][:18]:<18} [{r[2]}] -> {r[3]:<28} (src={r[4]}, conf={r[5]}, 音写={r[6]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
