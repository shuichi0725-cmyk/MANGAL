"""draft-2000 の slug を 現状の seed3 (= en fill 状態) で 再評価。

各 draft entry に対して:
1. 現 slug を取得
2. seed3 から alt_en を取得 (= もし fill されていれば)
3. alt_en があれば slug 候補を 再生成 (= slug_from_alt_en 相当)
4. 現 slug と 再生成候補 が違ったら 「変更要」 list に追加

slug 命名規則 (CLAUDE.md):
1. 種3 slug field 手動 (= override)
2. alt_en → slug ← C-1/2a/2b で fill した en は ここで効くはず
3. ASCII title 直接
4. 数字 keep
5. kana fallback ← en 未 fill の時 ここに落ちる

Output: .cache/slug-audit.txt
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRAFT_DIR = ROOT / "data" / "manga.draft-2000"
SEED3 = ROOT / "data" / "seeds" / "series-supplement-v2.yml"
OUT = ROOT / ".cache" / "slug-audit.txt"


# --- seed3 を line-based parse して key → {slug, alt_en} map に ---
def parse_seed3():
    text = SEED3.read_text(encoding="utf-8")
    result = {}
    cur_key = None
    cur_slug = None
    cur_alt_en = None
    in_alt_titles = False

    for line in text.splitlines():
        m = re.match(r'^  - key:\s*(.+)$', line)
        if m:
            if cur_key is not None:
                result[cur_key] = {"slug": cur_slug, "alt_en": cur_alt_en}
            cur_key = m.group(1).strip()
            cur_slug = None
            cur_alt_en = None
            in_alt_titles = False
            continue
        # slug field (= 種3 手動 override)
        ms = re.match(r'^    slug:\s*(.+)$', line)
        if ms and cur_key is not None:
            v = ms.group(1).strip().strip("'\"")
            if v and v != "null":
                cur_slug = v
        # alternative_titles section
        if re.match(r'^    alternative_titles:', line):
            in_alt_titles = True
            continue
        if re.match(r'^    \S', line):
            in_alt_titles = False
        if in_alt_titles:
            me = re.match(r'^\s+en:\s*(.+)$', line)
            if me:
                v = me.group(1).strip().strip("'\"")
                if v and v != "null":
                    cur_alt_en = v

    if cur_key is not None:
        result[cur_key] = {"slug": cur_slug, "alt_en": cur_alt_en}
    return result


# --- slug_from_alt_en 相当 (= _extract-top-completed.py から移植) ---
def slug_from_alt_en(en):
    if not en:
        return ""
    s = en.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s


KATA = re.compile(r"[゠-ヿㇰ-ㇿ]")


def main():
    seed3 = parse_seed3()
    print(f"seed3 keys: {len(seed3)}", file=sys.stderr)

    # qid → keys map (= draft の qid から逆引き)
    qid_to_keys = {}
    for k in seed3:
        qid_m = re.match(r'^qid:(Q\d+)\|', k)
        if qid_m:
            qid_to_keys.setdefault(qid_m.group(1), []).append(k)

    drafts = sorted(DRAFT_DIR.glob("*.yml"))
    print(f"draft files: {len(drafts)}", file=sys.stderr)

    issues = []
    # categories
    cat_kana_fallback_en_now_filled = []  # 旧 slug = kana fallback、 今 en あり → rebuild 要
    cat_kana_fallback_no_en = []          # 旧 slug = kana fallback、 今も en 無し → en fill が必要 or 純和語で OK
    cat_other_potential = []              # その他 (= 数字 / 助詞 等)

    for path in drafts:
        content = path.read_text(encoding="utf-8")
        slug_m = re.search(r'^slug:\s*(.+)$', content, re.M)
        title_m = re.search(r'^title:\s*(.+)$', content, re.M)
        kana_m = re.search(r'^title_kana:\s*(.+)$', content, re.M)
        qid_m = re.search(r'^wikidata_qid:\s*(.+)$', content, re.M)
        if not (slug_m and title_m):
            continue
        slug = slug_m.group(1).strip()
        title = title_m.group(1).strip()
        kana = (kana_m.group(1).strip() if kana_m else "")
        qid = (qid_m.group(1).strip() if qid_m else "")
        if qid == "null" or not qid:
            qid = ""

        # seed3 から alt_en 取得
        alt_en = None
        manual_slug = None
        if qid:
            keys = qid_to_keys.get(qid, [])
            for k in keys:
                # title が key 内の name と一致するか? (= 完全一致は厳しいので、 含まれるかで判定)
                if f"name:{title}" in k:
                    entry = seed3.get(k, {})
                    alt_en = entry.get("alt_en")
                    manual_slug = entry.get("slug")
                    break
            else:
                # title 一致しない → どれか 1 個 (= 第一候補) を見る
                if keys:
                    entry = seed3.get(keys[0], {})
                    alt_en = entry.get("alt_en")

        # 再生成 候補 (= 優先順 #1 種3 slug、 #2 alt_en)
        candidate_slug = None
        priority = None
        if manual_slug:
            candidate_slug = manual_slug
            priority = "manual"
        elif alt_en:
            candidate_slug = slug_from_alt_en(alt_en)
            priority = "alt_en"

        # 比較: 現 slug が candidate と違ったら 「変更要」
        # 但し suffix '-2' '-3' は許容
        norm_slug = re.sub(r'-\d+$', '', slug)
        if candidate_slug and candidate_slug != norm_slug:
            # 旧 slug が kana fallback (= alt_en 利用前) の可能性
            # 判定: norm_slug が title 内の カタカナ を ローマ字化 した形 (= 大雑把に判定)
            has_kata = bool(KATA.search(title))
            issues.append({
                "slug": slug,
                "title": title,
                "kana": kana,
                "qid": qid,
                "alt_en": alt_en,
                "candidate": candidate_slug,
                "priority": priority,
                "has_kata": has_kata,
            })
            if has_kata:
                cat_kana_fallback_en_now_filled.append({
                    "current": slug,
                    "candidate": candidate_slug,
                    "title": title,
                    "alt_en": alt_en,
                    "priority": priority,
                })
            else:
                cat_other_potential.append({
                    "current": slug,
                    "candidate": candidate_slug,
                    "title": title,
                    "alt_en": alt_en,
                    "priority": priority,
                })

    # report
    lines = []
    lines.append(f"# Slug Audit Report")
    lines.append(f"")
    lines.append(f"draft-2000 entries: {len(drafts)}")
    lines.append(f"slug 不一致 (= 現 vs 再生成候補) 合計: {len(issues)}")
    lines.append(f"")
    lines.append(f"## カテゴリ別")
    lines.append(f"")
    lines.append(f"- A: カタカナ含む title で 現 slug != alt_en/manual 候補: {len(cat_kana_fallback_en_now_filled)}")
    lines.append(f"  → C-1/2a/2b で en fill 後、 draft 再生成 されていない 可能性 (= 要 rebuild)")
    lines.append(f"- B: カタカナ含まない title で 不一致: {len(cat_other_potential)}")
    lines.append(f"  → 純和語 で manual slug or alt_en 由来 (= 妥当性 個別判断要)")
    lines.append(f"")
    lines.append(f"## 詳細 list (= カテゴリ A、 最大 200件)")
    lines.append(f"")
    for it in cat_kana_fallback_en_now_filled[:200]:
        lines.append(f"  current: {it['current']}")
        lines.append(f"    candidate: {it['candidate']}   ({it['priority']})")
        lines.append(f"    title: {it['title']}")
        if it['alt_en']:
            lines.append(f"    alt_en: {it['alt_en']}")
        lines.append("")
    if len(cat_kana_fallback_en_now_filled) > 200:
        lines.append(f"  ... and {len(cat_kana_fallback_en_now_filled) - 200} more")
    lines.append(f"")
    lines.append(f"## 詳細 list (= カテゴリ B、 最大 100件)")
    lines.append(f"")
    for it in cat_other_potential[:100]:
        lines.append(f"  current: {it['current']}")
        lines.append(f"    candidate: {it['candidate']}   ({it['priority']})")
        lines.append(f"    title: {it['title']}")
        if it['alt_en']:
            lines.append(f"    alt_en: {it['alt_en']}")
        lines.append("")
    if len(cat_other_potential) > 100:
        lines.append(f"  ... and {len(cat_other_potential) - 100} more")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote: {OUT}", file=sys.stderr)
    print(f"total mismatch: {len(issues)}, A={len(cat_kana_fallback_en_now_filled)}, B={len(cat_other_potential)}", file=sys.stderr)


if __name__ == "__main__":
    main()
