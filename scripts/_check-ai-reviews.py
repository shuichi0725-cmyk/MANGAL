#!/usr/bin/env python3
"""AI書評家リーグ seed (data/seeds/ai-reviews.yml) の健全性チェック。

 skill `ai-review-add` の格納後に必ず回す番人。
 見るもの: 節番号の連番/重複 / 必須フィールド / slug の本番存在 /
          本文の重複paste事故 / markdown残骸 / prompt の題名一致 / 課題図書の既出。
 使い方: python scripts/_check-ai-reviews.py   (NG があれば exit 1)
"""
import json, re, sys, unicodedata
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "data" / "seeds" / "ai-reviews.yml"
MD_RESIDUE = re.compile(r"(^#{1,6} )|(^---\s*$)|(\*\*)|[\u200b-\u200f\ufeff]", re.M)

ng: list[str] = []
warn: list[str] = []

doc = yaml.safe_load(SEED.read_text(encoding="utf-8")) or {}
sections = doc.get("sections") or []
if not sections:
    print("NG: sections が空")
    sys.exit(1)

# 本番ページの存在確認 (manga.v2 の公開slug索引を使わず、頁ファイル名で引く)
pages = {p.stem for p in (ROOT / "data" / "manga.v2").glob("*.yml")}

setsus: list[int] = []
seen_slug: dict[str, int] = {}
seen_text: dict[str, str] = {}

for s in sections:
    n = s.get("setsu")
    setsus.append(n)
    where = f"節{n}"
    for k in ("setsu", "slug", "title", "author", "prompt", "reviews"):
        if not s.get(k):
            ng.append(f"{where}: {k} が無い")
    slug, title, author = s.get("slug", ""), s.get("title", ""), s.get("author", "")
    if slug in seen_slug:
        ng.append(f"{where}: 課題図書が既出 (節{seen_slug[slug]} と同じ {slug})")
    seen_slug[slug] = n
    if slug and slug not in pages:
        warn.append(f"{where}: slug '{slug}' が data/manga.v2 に無い (公開slug override 頁なら可)")
    p = s.get("prompt", "")
    if title and title not in p:
        ng.append(f"{where}: prompt に作品名『{title}』が入っていない")
    if author and author.split("・")[0] not in p:
        ng.append(f"{where}: prompt に作者名 {author} が入っていない")

    revs = s.get("reviews") or []
    if len(revs) < 2:
        ng.append(f"{where}: 書評が {len(revs)} 本 (2本以上必要)")
    pair = set()
    for r in revs:
        v, m, t = r.get("vendor"), r.get("model"), r.get("text") or ""
        tag = f"{where}/{v} {m}"
        if not v or not m or not t.strip():
            ng.append(f"{tag}: vendor/model/text のどれかが空")
            continue
        if (v, m) in pair:
            ng.append(f"{where}: {v} {m} が節内で重複")
        pair.add((v, m))
        key = unicodedata.normalize("NFKC", re.sub(r"\s+", "", t))[:400]
        if key in seen_text:
            ng.append(f"{tag}: 本文が {seen_text[key]} と同一 (重複paste事故)")
        seen_text[key] = tag
        if MD_RESIDUE.search(t):
            ng.append(f"{tag}: markdown残骸 (#/---/**/ゼロ幅) が残っている")
        if len(t) < 300:
            warn.append(f"{tag}: 本文が短い ({len(t)}字)")

if sorted(setsus) != list(range(1, len(setsus) + 1)):
    ng.append(f"節番号が 1..N の連番でない: {sorted(setsus)}")

print(f"sections={len(sections)}  reviews={sum(len(s.get('reviews') or []) for s in sections)}  ユニーク本文={len(seen_text)}")
for w in warn:
    print("WARN:", w)
for g in ng:
    print("NG:", g)
print("OK" if not ng else f"NG {len(ng)}件")
sys.exit(1 if ng else 0)
