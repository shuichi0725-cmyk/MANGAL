"""種2 sqlite + 種3 yml の フリガナ (= title_kana) カバー率 + 不備調査。

確認軸:
- カバー率 (= NULL / empty / 値あり)
- 不備パターン:
  - スペース混入 (= CLAUDE.md L131 「スペース なし」 仕様 違反)
  - ローマ字混入 (= ASCII 文字 含む)
  - ひらがな混入 (= フリガナは カタカナ仕様)
  - 短すぎる (= 1-2 文字 = title に対して 不適切)
  - 異常文字 (= 「(編)」「[著]」 等)
"""
from __future__ import annotations
import sqlite3
import re
from collections import Counter
from pathlib import Path

DB = Path(".cache/db-v2.sqlite")
SEED3 = Path("data/seeds/series-supplement-v2.yml")

KATAKANA_RE = re.compile(r"^[゠-ヿー・]+$")
HAS_HIRAGANA = re.compile(r"[ぁ-ゖ]")
HAS_ASCII = re.compile(r"[A-Za-z]")
HAS_SPACE = re.compile(r"[\s　]")
WEIRD_CHAR = re.compile(r"[\[\]【】()「」『』〈-》]")


def analyze_kana(s: str | None) -> str:
    if s is None: return "null"
    s_clean = s.strip()
    if not s_clean: return "empty"
    issues = []
    if HAS_SPACE.search(s):
        issues.append("space")
    if HAS_ASCII.search(s_clean):
        issues.append("ascii")
    if HAS_HIRAGANA.search(s_clean):
        issues.append("hiragana")
    if WEIRD_CHAR.search(s_clean):
        issues.append("weird-char")
    if len(s_clean) < 3:
        issues.append("too-short")
    if KATAKANA_RE.match(s_clean) and not issues:
        return "ok"
    if issues:
        return "issue:" + ",".join(issues)
    return "other"


def main():
    print(f"=== 種2 sqlite (= db-v2.sqlite) ===")
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT id, title, title_kana, subtitle_kana FROM series").fetchall()
    n_total = len(rows)
    print(f"  series 総数: {n_total:,}")
    title_kana_dist = Counter()
    sub_kana_dist = Counter()
    issue_samples = {}
    for r in rows:
        cat = analyze_kana(r["title_kana"])
        title_kana_dist[cat] += 1
        if cat.startswith("issue") and cat not in issue_samples:
            issue_samples[cat] = (r["title"], r["title_kana"])
        cat_sub = analyze_kana(r["subtitle_kana"])
        if r["subtitle_kana"] is not None:
            sub_kana_dist[cat_sub] += 1
    print()
    print(f"  --- title_kana 分布 ---")
    for k, v in title_kana_dist.most_common():
        pct = v / n_total * 100
        sample = ""
        if k in issue_samples:
            t, kn = issue_samples[k]
            sample = f"  例: title={t!r} kana={kn!r}"
        print(f"    {k:<30}: {v:>7,} ({pct:>5.1f}%){sample}")
    n_subtitled = sum(sub_kana_dist.values())
    print()
    print(f"  --- subtitle_kana 分布 (= subtitle あり {n_subtitled:,} 件中) ---")
    for k, v in sub_kana_dist.most_common(10):
        pct = v / n_subtitled * 100 if n_subtitled else 0
        print(f"    {k:<30}: {v:>7,} ({pct:>5.1f}%)")

    print()
    print(f"=== 種3 yml (= series-supplement-v2.yml) ===")
    import yaml
    with SEED3.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    entries = data.get("series", [])
    print(f"  entries 総数: {len(entries):,}")
    seed3_kana_dist = Counter()
    seed3_kana_samples = {}
    fields_present = Counter()
    for e in entries:
        # 種3 entry に title_kana field あるか確認
        for k in e.keys():
            fields_present[k] += 1
    print()
    print(f"  --- field 出現率 top 20 ---")
    for k, v in fields_present.most_common(20):
        pct = v / len(entries) * 100
        print(f"    {k:<30}: {v:>7,} ({pct:>5.1f}%)")


if __name__ == "__main__":
    main()
