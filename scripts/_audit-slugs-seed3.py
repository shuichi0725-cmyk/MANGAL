"""seed3 全 76,435件 の slug 品質 audit。

各 entry に対して:
1. alt_en があれば slug_from_alt_en で候補生成 → バグ検出 (= アポストロフィ / × / 等)
2. alt_en なし + カタカナ含む title → en fill 未実施 (= kana fallback 対象)
3. 手動 slug field → そのまま使用

Output: .cache/slug-audit-seed3.txt / .cache/slug-audit-seed3-summary.md
"""
import re
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
SEED3 = ROOT / "data" / "seeds" / "series-supplement-v2.yml"
OUT_TXT = ROOT / ".cache" / "slug-audit-seed3.txt"
OUT_MD = ROOT / ".cache" / "slug-audit-seed3-summary.md"

KATA = re.compile(r"[゠-ヿㇰ-ㇿ]")


def slug_from_alt_en(en: str) -> str:
    if not en:
        return ""
    s = en.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s


def slug_from_alt_en_fixed(en: str) -> str:
    """バグ修正版: アポストロフィ削除 + × → x"""
    if not en:
        return ""
    s = en
    s = s.replace("×", "x")
    s = re.sub(r"[''']", "", s)  # apostrophe 削除
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s


def parse_seed3():
    text = SEED3.read_text(encoding="utf-8")
    entries = []
    cur_key = None
    cur_slug = None
    cur_alt_en = None
    in_alt_titles = False

    for line in text.splitlines():
        m = re.match(r'^  - key:\s*(.+)$', line)
        if m:
            if cur_key is not None:
                entries.append({
                    "key": cur_key,
                    "slug": cur_slug,
                    "alt_en": cur_alt_en,
                })
            cur_key = m.group(1).strip()
            cur_slug = None
            cur_alt_en = None
            in_alt_titles = False
            continue

        ms = re.match(r'^    slug:\s*(.+)$', line)
        if ms and cur_key is not None:
            v = ms.group(1).strip().strip("'\"")
            if v and v != "null":
                cur_slug = v

        if re.match(r'^    alternative_titles:', line):
            in_alt_titles = True
            continue
        if re.match(r'^    \S', line):
            in_alt_titles = False
        if in_alt_titles:
            me = re.match(r'^\s+en:\s*(.+)$', line)
            if me:
                v = me.group(1).strip().strip("'\"")
                if v and v not in ("null", "~", ""):
                    cur_alt_en = v

    if cur_key is not None:
        entries.append({
            "key": cur_key,
            "slug": cur_slug,
            "alt_en": cur_alt_en,
        })
    return entries


def extract_title_from_key(key: str) -> str:
    """key の最後の name: 部分を title として返す"""
    # key 例: qid:Q123|name:タイトル|sub:サブタイトル
    # name: 部分を全部取り出して最後を返す
    names = re.findall(r'name:([^|]+?)(?:\||$)', key)
    if names:
        return names[-1]
    return key


def main():
    print("parsing seed3...", file=sys.stderr)
    entries = parse_seed3()
    print(f"total entries: {len(entries)}", file=sys.stderr)

    # カテゴリ分類
    cat = defaultdict(list)

    for e in entries:
        key = e["key"]
        alt_en = e["alt_en"]
        manual_slug = e["slug"]
        title = extract_title_from_key(key)
        has_kata = bool(KATA.search(title))

        if manual_slug:
            # 手動 slug あり → slug 自体のバグチェック
            # (手動なので基本 OK だが apostrophe / × が紛れ込んでいないか)
            if "'" in manual_slug or "'" in manual_slug:
                cat["manual_apostrophe"].append({"key": key, "title": title, "slug": manual_slug, "alt_en": alt_en})
            continue  # 手動 slug は問題なければスキップ

        if alt_en:
            slug_current = slug_from_alt_en(alt_en)
            slug_fixed = slug_from_alt_en_fixed(alt_en)

            # B-3: アポストロフィバグ
            if re.search(r"[''']", alt_en):
                cat["apostrophe_bug"].append({
                    "key": key, "title": title, "alt_en": alt_en,
                    "slug_bad": slug_current, "slug_fixed": slug_fixed,
                })
                continue

            # B-4: × バグ
            if "×" in alt_en:
                cat["times_bug"].append({
                    "key": key, "title": title, "alt_en": alt_en,
                    "slug_bad": slug_current, "slug_fixed": slug_fixed,
                })
                continue

            # B-5: 括弧 () が alt_en に残っている
            if re.search(r"[()]", alt_en):
                cat["paren_in_en"].append({
                    "key": key, "title": title, "alt_en": alt_en,
                    "slug_bad": slug_current, "slug_fixed": slug_fixed,
                })
                continue

            # B-6: alt_en が極端に短い (= 1文字 or 2文字)
            if len(alt_en.strip()) <= 2:
                cat["short_en"].append({
                    "key": key, "title": title, "alt_en": alt_en,
                    "slug_bad": slug_current,
                })
                continue

            # B-1: カタカナなし (= 純和語/漢語) なのに alt_en あり → Hepburn keep 候補
            if not has_kata:
                cat["hepburn_candidate"].append({
                    "key": key, "title": title, "alt_en": alt_en,
                    "slug_would_be": slug_current,
                })
                continue

            # A: カタカナあり + alt_en あり → 良好 (= slug は alt_en ベースで生成される)
            cat["ok_with_en"].append({"key": key, "title": title, "alt_en": alt_en})

        else:
            # alt_en なし
            if has_kata:
                # A-miss: カタカナ含む = 外来語の可能性 → en fill 未実施
                cat["kata_no_en"].append({
                    "key": key, "title": title,
                })
            else:
                # C: 純和語/漢語 + en なし → Hepburn slug になる = 正常
                cat["pure_japanese_no_en"].append({"key": key, "title": title})

    # レポート生成
    lines_txt = []
    lines_txt.append("# Slug Audit Report (= seed3 全件)")
    lines_txt.append("")
    lines_txt.append(f"seed3 total entries: {len(entries)}")
    lines_txt.append("")

    def section(label, items, limit=500):
        lines_txt.append(f"## {label} ({len(items)}件)")
        lines_txt.append("")
        for it in items[:limit]:
            lines_txt.append(f"  key: {it['key'][:120]}")
            if it.get("title"):
                lines_txt.append(f"    title: {it['title']}")
            if it.get("alt_en"):
                lines_txt.append(f"    alt_en: {it['alt_en']}")
            if it.get("slug_bad"):
                lines_txt.append(f"    slug_BAD: {it['slug_bad']}")
            if it.get("slug_fixed"):
                lines_txt.append(f"    slug_FIXED: {it['slug_fixed']}")
            if it.get("slug_would_be"):
                lines_txt.append(f"    slug_would_be: {it['slug_would_be']}")
            if it.get("slug"):
                lines_txt.append(f"    manual_slug: {it['slug']}")
            lines_txt.append("")
        if len(items) > limit:
            lines_txt.append(f"  ... and {len(items) - limit} more")
            lines_txt.append("")

    section("B-3: アポストロフィ バグ (= slug に -s- が入る)", cat["apostrophe_bug"])
    section("B-4: × バグ (= slug から x が消える)", cat["times_bug"])
    section("B-5: 括弧 () が alt_en に含まれる", cat["paren_in_en"])
    section("B-6: alt_en が極端に短い", cat["short_en"])
    section("B-1: Hepburn keep 候補 (= 純和語/漢語 なのに alt_en あり)", cat["hepburn_candidate"], limit=200)
    section("A-miss: カタカナ含む + en 未fill (= kana fallback slug になる)", cat["kata_no_en"], limit=300)
    section("manual slug に apostrophe 混入", cat["manual_apostrophe"])

    OUT_TXT.parent.mkdir(parents=True, exist_ok=True)
    OUT_TXT.write_text("\n".join(lines_txt), encoding="utf-8")

    # サマリー MD
    md = []
    md.append("# Slug Audit Summary (= seed3 全 76,435件)")
    md.append("")
    md.append(f"seed3 全 {len(entries):,}件 を スキャン。")
    md.append("")
    md.append("## 件数サマリー")
    md.append("")
    md.append("| カテゴリ | 件数 | 対応 |")
    md.append("|---|---|---|")
    md.append(f"| A: カタカナ + alt_en あり (= 良好) | {len(cat['ok_with_en']):,} | draft 再生成で slug 改善 |")
    md.append(f"| A-miss: カタカナ + en 未fill | {len(cat['kata_no_en']):,} | en fill が必要 or 純和語で OK |")
    md.append(f"| B-1: Hepburn keep 候補 (= 純和語 + alt_en あり) | {len(cat['hepburn_candidate']):,} | 方針確認 |")
    md.append(f"| B-3: アポストロフィ バグ | {len(cat['apostrophe_bug']):,} | slug logic 修正 |")
    md.append(f"| B-4: × バグ | {len(cat['times_bug']):,} | slug logic 修正 |")
    md.append(f"| B-5: 括弧 () バグ | {len(cat['paren_in_en']):,} | alt_en 修正 or slug logic |")
    md.append(f"| B-6: alt_en 極端に短い | {len(cat['short_en']):,} | 個別確認 |")
    md.append(f"| C: 純和語 + en なし (= 正常) | {len(cat['pure_japanese_no_en']):,} | 対応不要 |")
    total_issues = (len(cat['apostrophe_bug']) + len(cat['times_bug']) + len(cat['paren_in_en'])
                    + len(cat['short_en']) + len(cat['hepburn_candidate']) + len(cat['kata_no_en']))
    md.append(f"| **問題合計** | **{total_issues:,}** | - |")
    md.append("")

    md.append("## バグ詳細 (= B-3: アポストロフィ)")
    md.append("")
    md.append("| title | alt_en | slug_BAD | slug_FIXED |")
    md.append("|---|---|---|---|")
    for it in cat["apostrophe_bug"][:30]:
        md.append(f"| {it['title'][:40]} | {it['alt_en'][:40]} | {it['slug_bad']} | {it['slug_fixed']} |")
    if len(cat["apostrophe_bug"]) > 30:
        md.append(f"| ... | ... ({len(cat['apostrophe_bug'])}件 合計) | | |")
    md.append("")

    md.append("## バグ詳細 (= B-4: ×)")
    md.append("")
    md.append("| title | alt_en | slug_BAD | slug_FIXED |")
    md.append("|---|---|---|---|")
    for it in cat["times_bug"][:30]:
        md.append(f"| {it['title'][:40]} | {it['alt_en'][:40]} | {it['slug_bad']} | {it['slug_fixed']} |")
    if len(cat["times_bug"]) > 30:
        md.append(f"| ... | ... ({len(cat['times_bug'])}件 合計) | | |")
    md.append("")

    md.append("## A-miss: カタカナ + en 未fill (= 先頭 50件)")
    md.append("")
    md.append("| title |")
    md.append("|---|")
    for it in cat["kata_no_en"][:50]:
        md.append(f"| {it['title'][:60]} |")
    if len(cat["kata_no_en"]) > 50:
        md.append(f"| ... ({len(cat['kata_no_en'])}件 合計) |")
    md.append("")

    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    print(f"wrote: {OUT_TXT}", file=sys.stderr)
    print(f"wrote: {OUT_MD}", file=sys.stderr)

    print(f"\n=== SUMMARY ===")
    print(f"total: {len(entries):,}")
    print(f"ok_with_en (A): {len(cat['ok_with_en']):,}")
    print(f"kata_no_en (A-miss): {len(cat['kata_no_en']):,}")
    print(f"hepburn_candidate (B-1): {len(cat['hepburn_candidate']):,}")
    print(f"apostrophe_bug (B-3): {len(cat['apostrophe_bug']):,}")
    print(f"times_bug (B-4): {len(cat['times_bug']):,}")
    print(f"paren_in_en (B-5): {len(cat['paren_in_en']):,}")
    print(f"short_en (B-6): {len(cat['short_en']):,}")
    print(f"pure_japanese_no_en (C): {len(cat['pure_japanese_no_en']):,}")
    print(f"manual_apostrophe: {len(cat['manual_apostrophe']):,}")


if __name__ == "__main__":
    main()
