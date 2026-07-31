#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""楽天 booksGenreId の **主題性のある枝** から genre を純粋追加する(surgical)。

★背景: 楽天のコミック枝(001001…)は出版社×レーベル/判型の分類で主題を持たない
  (300件以上ある76枝のうち71枝が単一出版社80%以上)。だが別枝に主題性のあるものが在る:

    001029002 (TL系) → romance  : trusted 168作で P=100%
    001021002 (BL系) → romance  : trusted 564作で P=90%
    001021002 (BL系) → bl       : P=64% ★閾値未達につき**振らない**
                                   (BL語彙[ノンケ/オメガバース/発情期…]を掛けても64%でリフト無し)

  = 既存パイプライン([[genre_from_rakuten_story_plan]] / docs/genre-rakuten-learning.md)と同じ
    「適合率P≥0.8のラベルだけ振る」規律に従う。

安全策:
- **trusted には絶対に触らない**(genres_provisional が立っている作 or genres 空 のみ)。
- 既存 genres は消さず **union で純粋追加**。他フィールド不変。
- 触る前に .cache へバックアップ。来歴は data/seeds/genre-branch-changelog.jsonl に1行/作。
- ★新しい schema フィールドは足さない(loadData の Zod に無い key を増やさない)。

usage: python scripts/_genre-rakuten-branch-apply.py [--apply]
  既定は dry-run。 .cache/rk-branch-slug.json (slug→枝) が要る。
"""
import json, io, sys, shutil, time, re
from pathlib import Path
from collections import Counter

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
MANGA = ROOT / "data" / "manga.v2"
BRANCH = ROOT / ".cache" / "rk-branch-slug.json"
CHANGELOG = ROOT / "data" / "seeds" / "genre-branch-changelog.jsonl"
APPLY = "--apply" in sys.argv

# 枝 → 付与するgenre(P≥0.8で検証済のものだけ)
RULES = {
    "001029002": ["romance"],   # P=100%
    "001021002": ["romance"],   # P=90%   ※ bl は P=64% で不採用
}

branch = json.load(io.open(BRANCH, encoding="utf-8"))
st = Counter()
plan = []

for slug, bs in sorted(branch.items()):
    add = set()
    for b in bs:
        add |= set(RULES.get(b, []))
    if not add:
        continue
    fp = MANGA / f"{slug}.yml"
    if not fp.exists():
        st["file_missing"] += 1
        continue
    raw = fp.read_text(encoding="utf-8")
    # ★genres は「ブロック形」と「genres: [] のインライン空配列」の2形がある(後者=ジャンル無し)
    m = re.search(r"^genres:\n((?:- .*\n)*)", raw, re.M)
    cur = [x[2:].strip() for x in (m.group(1).split("\n") if m else []) if x.startswith("- ")]
    provisional = re.search(r"^genres_provisional: true", raw, re.M) is not None
    if not (provisional or not cur):
        st["skip_trusted"] += 1          # ★trusted は触らない
        continue
    new = sorted(set(cur) | add)
    if new == sorted(cur):
        st["already"] += 1
        continue
    plan.append((slug, cur, new, sorted(add - set(cur))))

print(f"候補 {len(plan):,} 作 / trusted skip {st['skip_trusted']:,} / 既付与 {st['already']:,}"
      f" / file無 {st['file_missing']:,}{'' if APPLY else '  [DRY-RUN]'}")
c = Counter()
for _, _, _, added in plan:
    for g in added:
        c[g] += 1
print("  付与内訳:", dict(c))
for slug, cur, new, added in plan[:5]:
    print(f"   例 {slug}: {cur} → {new}")

if not APPLY:
    sys.exit(0)

bak = ROOT / ".cache" / f"manga.v2.bak-genre-branch-{time.strftime('%Y%m%d-%H%M%S')}"
bak.mkdir(parents=True, exist_ok=True)
CHANGELOG.parent.mkdir(parents=True, exist_ok=True)
at = time.strftime("%Y-%m-%d")
n = 0
done_slugs = []   # ★実際に書けた物だけを反映対象にする(失敗が混ざると索引がずれる)
with io.open(CHANGELOG, "a", encoding="utf-8") as log:
    for slug, cur, new, added in plan:
        fp = MANGA / f"{slug}.yml"
        raw = fp.read_text(encoding="utf-8")
        block = "genres:\n" + "".join(f"- {g}\n" for g in new)
        if re.search(r"^genres: \[\]\s*$", raw, re.M):
            raw2, cnt = re.subn(r"^genres: \[\]\n", block, raw, count=1, flags=re.M)
        else:
            raw2, cnt = re.subn(r"^genres:\n(?:- .*\n)*", block, raw, count=1, flags=re.M)
        if cnt != 1:
            st["patch_fail"] += 1
            continue
        shutil.copy2(fp, bak / fp.name)
        fp.write_text(raw2, encoding="utf-8")
        log.write(json.dumps({"op": "genre_add_rakuten_branch", "slug": slug,
                              "before": cur, "after": new, "added": added,
                              "at": at, "via": "_genre-rakuten-branch-apply"},
                             ensure_ascii=False) + "\n")
        n += 1
        done_slugs.append(slug)
print(f"適用 {n:,} 作 / patch失敗 {st['patch_fail']:,} / backup → {bak.name}")
io.open(ROOT / ".cache" / "genre_branch_changed_slugs.txt", "w", encoding="utf-8").write(
    ",".join(done_slugs))
print("変更slug → .cache/genre_branch_changed_slugs.txt")
