#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""種2→本番の未掲載監査 (= 「除外理由が無いのに載っていない漫画はあるか」2026-07-04 ユーザ問)

種2全seriesを「ISBNが本番のどこかの頁に描画されているか」で二分し、未描画側を既知理由で仕分け:
 ADULT / NO_ISBN / DROP_TITLE(関連書等) / NON_MANGA_SEED / ANTHOLOGY_SEED / EDITION_DROP(コンビニ等) /
 FOREIGN(非9784) / SAME_TITLE_RENDERED(同題の頁あり=merge/版統合に吸収された可能性大) / ★UNEXPLAINED
出力: docs/production-diagnostics/shu2-unrendered.tsv (UNEXPLAINED全件+各クラス件数)
"""
import json, os, re, sys, sqlite3
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try:
    from yaml import CSafeLoader as L
except ImportError:
    from yaml import SafeLoader as L
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from _promote_drop_patterns import is_droppable  # 漫画性/関連書フィルタ(共有)

KEEP_TYPES = {"standard", "bunkobon", "wideban", "kanzenban", "shinsoban", "aizoban"}
DROP_IMPRINT = ("My first big", "コンビニ", "増刊", "同人", "remix", "REMIX", "bilingual", "novel", "Novel")

iidx = json.load(open(os.path.join(ROOT, ".cache", "isbn-page-index.json"), encoding="utf-8"))
nm = yaml.load(open(os.path.join(ROOT, "data", "seeds", "non-manga-drop.yml"), encoding="utf-8"), Loader=L) or {}
nm_keys = {e.get("series_key") for e in (nm.get("drops") or nm.get("entries") or []) if isinstance(e, dict)} | \
          {e for e in (nm.get("drops") or []) if isinstance(e, str)}
an_p = os.path.join(ROOT, "data", "seeds", "anthology-merge.yml")
an = yaml.load(open(an_p, encoding="utf-8"), Loader=L) if os.path.exists(an_p) else {}
an_keys = set()
for v in (an.get("groups") or an.get("entries") or []):
    if isinstance(v, dict):
        an_keys.update(v.get("series_keys") or [])

def norm_t(t):
    return re.sub(r"[\s　・!！?？:：〜~\-]", "", str(t or "")).lower()

# 描画済み頁題(同題吸収の判定用)
rendered_titles = set()
idxj = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
f = idxj["f"]; ti = f.index("title")
for r in idxj["d"]:
    rendered_titles.add(norm_t(r[ti]))

con = sqlite3.connect(os.path.join(ROOT, ".cache", "db-v2.sqlite"))
cur = con.cursor()
c = Counter()
unexplained = []
for sid, skey, title, kana, adult in cur.execute(
        "SELECT id, series_key, title, title_kana, adult_score FROM series"):
    rows = list(con.execute(
        "SELECT v.isbn13, e.type, e.imprint FROM volumes v JOIN editions e ON v.edition_id=e.id "
        "WHERE e.series_id=?", (sid,)))
    c["total"] += 1
    isbns = [re.sub(r"[^0-9X]", "", str(r[0])) for r in rows if r[0]]
    if any(i in iidx for i in isbns):
        c["RENDERED"] += 1
        continue
    # --- 未描画の仕分け ---
    if adult is not None and adult >= 3:
        c["ADULT"] += 1; continue
    if not isbns:
        c["NO_ISBN"] += 1; continue
    if skey in nm_keys:
        c["NON_MANGA_SEED"] += 1; continue
    if skey in an_keys:
        c["ANTHOLOGY_SEED"] += 1; continue
    if is_droppable(title or "", "", []):
        c["DROP_TITLE"] += 1; continue
    ktypes = [r[1] for r in rows]
    imprints = [str(r[2] or "") for r in rows]
    if ktypes and not any(t in KEEP_TYPES for t in ktypes):
        c["EDITION_TYPE_DROP"] += 1; continue
    if imprints and all(any(p in im for p in DROP_IMPRINT) for im in imprints if im) and any(imprints):
        c["EDITION_IMPRINT_DROP"] += 1; continue
    if isbns and not any(i.startswith("9784") for i in isbns):
        c["FOREIGN"] += 1; continue
    if norm_t(title) in rendered_titles:
        c["SAME_TITLE_RENDERED"] += 1; continue
    c["UNEXPLAINED"] += 1
    unexplained.append((str(sid), skey or "", str(title or "")[:40], str(kana or "")[:24],
                        str(len(isbns)), isbns[0] if isbns else ""))

out = os.path.join(ROOT, "docs", "production-diagnostics", "shu2-unrendered.tsv")
with open(out, "w", encoding="utf-8") as fo:
    fo.write("sid\tseries_key\ttitle\tkana\tn_isbn\tisbn1\n")
    for r in unexplained:
        fo.write("\t".join(r) + "\n")
print("仕分け:", dict(c))
print("→", out)
