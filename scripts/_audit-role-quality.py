#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""役割(肩書き)の質監査 (= ②。API不使用: 本番頁 × AniList dump v3 staff 突合。2026-07-04)

分類(自動fixしない=worklist):
 - ROLE_FLIP    : 頁=単独writer_artistだが、AniListはStory(原作)とArt(作画)が別人 → 分離漏れ疑い
 - POLLUTION_SUP: 頁著者がAniListではSupervisor/Assistant等のみ → 監修/アシの著者化疑い
 - MISSING_STORY: AniListのStory担当が頁のauthors/original_authorsに居ない → 原作者欠け疑い
注意: AniListリンク自体の誤り(bardock型~10%)による偽陽性を含む。適用前に個別確認必須。
出力: docs/production-diagnostics/role-conflicts.tsv
"""
import glob, gzip, json, os, re, sys
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try:
    from yaml import CSafeLoader as L
except ImportError:
    from yaml import SafeLoader as L
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def norm(n):
    return re.sub(r"[\s　・]", "", str(n or ""))

# 1) 頁側: anilist_id → クレジット
pages = {}
n = 0
for p in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
    n += 1
    try:
        d = yaml.load(open(p, encoding="utf-8"), Loader=L)
    except Exception:
        continue
    if not d or not d.get("anilist_id"):
        continue
    aid = int(d["anilist_id"])
    pages.setdefault(aid, []).append({
        "stem": os.path.basename(p)[:-4],
        "title": str(d.get("title") or "")[:30],
        "authors": [(norm(a.get("name")), a.get("role") or "") for a in (d.get("authors") or [])],
        "originals": [norm(a.get("name")) for a in (d.get("original_authors") or [])],
    })
print(f"頁走査{n} → anilist_id付き {sum(len(v) for v in pages.values()):,}頁 / {len(pages):,} id")

# 2) dump側: 該当aidのstaffだけ回収
STORY = ("story",)
ART = ("art",)
def role_class(r):
    r = str(r or "").lower()
    if "story" in r and "art" in r:
        return "storyart"
    if r.startswith("story") or "original story" in r or "original creator" in r:
        return "story"
    if r.startswith("art") or "illustration" in r:
        return "art"
    if "supervis" in r or "assist" in r:
        return "sup"
    return "other"

staff = {}
dump = os.path.join(ROOT, ".cache", "anilist-manga-dump-v3.jsonl.gz")
with gzip.open(dump, "rt", encoding="utf-8") as f:
    for ln in f:
        d = json.loads(ln)
        aid = d.get("id")
        if aid not in pages:
            continue
        rec = {"storyart": set(), "story": set(), "art": set(), "sup": set()}
        for e in ((d.get("staff") or {}).get("edges") or []):
            node = (e.get("node") or {}).get("name") or {}
            nm = norm(node.get("native") or node.get("full"))
            if not nm:
                continue
            c = role_class(e.get("role"))
            if c in rec:
                rec[c].add(nm)
        staff[aid] = rec
print(f"dump staff回収 {len(staff):,} id")

rows = []
c = Counter()
for aid, plist in pages.items():
    st = staff.get(aid)
    if not st:
        continue
    story_only = st["story"] - st["storyart"]
    art_only = st["art"] - st["storyart"]
    for pg in plist:
        anames = {a for a, _ in pg["authors"]}
        allnames = anames | set(pg["originals"])
        # ROLE_FLIP
        if (len(pg["authors"]) == 1 and pg["authors"][0][1] == "writer_artist"
                and not pg["originals"] and story_only and art_only
                and pg["authors"][0][0] in (story_only | art_only)):
            rows.append(("ROLE_FLIP", pg["stem"], pg["title"], pg["authors"][0][0],
                         "story=" + "/".join(sorted(story_only)) + " art=" + "/".join(sorted(art_only))))
            c["ROLE_FLIP"] += 1
        # POLLUTION_SUP
        for a, _ in pg["authors"]:
            if a in st["sup"] and a not in (st["storyart"] | st["story"] | st["art"]):
                rows.append(("POLLUTION_SUP", pg["stem"], pg["title"], a, "AniList=Supervisor/Assistのみ"))
                c["POLLUTION_SUP"] += 1
        # MISSING_STORY
        miss = {s for s in story_only if s not in allnames}
        if miss and (st["storyart"] & anames or art_only & anames):
            rows.append(("MISSING_STORY", pg["stem"], pg["title"], "/".join(sorted(miss)), "頁に原作者不在"))
            c["MISSING_STORY"] += 1

out = os.path.join(ROOT, "docs", "production-diagnostics", "role-conflicts.tsv")
with open(out, "w", encoding="utf-8") as f:
    f.write("class\tslug\ttitle\tname\tdetail\n")
    for r in sorted(rows):
        f.write("\t".join(r) + "\n")
print("分類:", dict(c), "→", out)
