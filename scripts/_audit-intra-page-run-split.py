# -*- coding: utf-8 -*-
"""【型・検出器】漫画内分裂 = 1本の刊行runが同じ頁の複数の版タブに割れている(2026-09-07 新設)。

★既存2本の穴を埋める:
  `_audit-canonical-imprint-split.py` = レーベル名の一致で探す → 名前が違うと取れない
  `_audit-edition-run-split.py`       = **巻番号の重複ゼロ**を要求 → 1巻でも重なると取れない
  鉄腕アトムはその両方の網から漏れていた(ユーザ発見):
    版「KCスペシャル(1987)」 v1-7 と 版「講談社コミックス(1993)」 v6,8-15
    = 講談社の1本のrun(全15巻)が名前違いで2タブに割れ、v6 だけ刷違いで重なっていた。

判定(名前に依存しない):
  同一頁の2版が
   ① 出版社が一致(またはISBN出版者記号が共通)
   ② 巻番号を合わせると **min..max が連番**(欠番なし)
   ③ 巻番号ごとに最古の刷を採ると **発売日が巻順に単調増加**
   ④ ★**重なりが小さい**: 重複巻数 <= 2 かつ 重複/合併巻数 <= 20%
      = AKIRA(1984年版[1-6] と 2003新装版[1-6] = 完全重複)のような**正当な別版**を弾く核心。
        別版は「同じ全巻を丸ごともう一度出す」ので重なりが大きい。
        1本のrunの分裂は「前半と後半」なので重なりは0〜数巻に収まる
   ⑤ どちらの版も単独では完結していない(片方だけで min..max が揃っていない)
  を全て満たす = 1本の刊行runが割れている強い疑い。

tier A = imprint を正規化すると一致 / B = 名前は違う(英字↔和名・略称↔正式名・年サフィックス)
出力: docs/production-diagnostics/intra-page-run-split.tsv
★自動統合は禁止。 canonical seed を持つ頁は seed の extra_editions を1本に畳むだけで直せる。

  python scripts/_audit-intra-page-run-split.py
"""
import glob
import io
import os
import re
import sys
import unicodedata
from collections import Counter
from itertools import combinations

import yaml
try:
    from yaml import CSafeLoader as L
except Exception:
    from yaml import SafeLoader as L

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SMALL = str.maketrans("ァィゥェォッャュョヮヵヶ", "アイウエオツヤユヨワカケ")
MAX_OVERLAP = 2
MAX_OVERLAP_RATIO = 0.20


def nk(s):
    s = unicodedata.normalize("NFKC", s or "")
    for ch in " ・<>〔〕[]()（）":
        s = s.replace(ch, "")
    s = re.sub(r"\d{4}(-\d{2,4})?", "", s)      # 年サフィックスは名前の一部と見なさない
    return s.translate(SMALL).upper()


def ym(v):
    return str(v.get("release_date") or "")[:7]


def main():
    rows = []
    canon = {os.path.basename(p)[:-4]
             for p in glob.glob(os.path.join(ROOT, "data", "seeds", "edition-canonical", "*.yml"))}
    for p in sorted(glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml"))):
        try:
            d = yaml.load(io.open(p, encoding="utf-8"), Loader=L) or {}
        except Exception:
            continue
        eds = []
        for i, e in enumerate(d.get("editions") or []):
            vs = [v for v in (e.get("volumes") or [])
                  if isinstance(v.get("number"), int) and v["number"] >= 1]
            if len(vs) >= 2:
                eds.append((i, e, vs))
        if len(eds) < 2:
            continue
        for (ia, a, va), (ib, b, vb) in combinations(eds, 2):
            pa, pb = (a.get("publisher") or ""), (b.get("publisher") or "")
            ra = {(v.get("isbn13") or "")[:6] for v in va if v.get("isbn13")}
            rb = {(v.get("isbn13") or "")[:6] for v in vb if v.get("isbn13")}
            if not ((pa and pa == pb) or (ra and rb and (ra & rb))):
                continue
            na, nb = {v["number"] for v in va}, {v["number"] for v in vb}
            ov = na & nb
            uni = na | nb
            # ④ 重なりが小さいこと(正当な別版=丸ごと重なる を弾く)
            if len(ov) > MAX_OVERLAP or (uni and len(ov) / len(uni) > MAX_OVERLAP_RATIO):
                continue
            # ⑤ 片方だけで完結していない
            if na == uni or nb == uni:
                continue
            # ② 合わせて連番
            if sorted(uni) != list(range(min(uni), max(uni) + 1)):
                continue
            # ③ 巻番号ごとに最古の刷を採って日付が単調
            best = {}
            for v in va + vb:
                n, t = v["number"], ym(v)
                if not t:
                    continue
                if n not in best or t < best[n]:
                    best[n] = t
            if len(best) < len(uni) * 0.8 or len(best) < 4:
                continue
            seq = [best[n] for n in sorted(best)]
            if seq != sorted(seq):
                continue
            tier = "A" if nk(a.get("imprint")) == nk(b.get("imprint")) else "B"
            rows.append({
                "tier": tier, "slug": os.path.basename(p)[:-4], "title": d.get("title") or "",
                "canonical": "有" if os.path.basename(p)[:-4] in canon else "無",
                "eiA": ia, "typeA": a.get("type") or "", "labelA": a.get("label") or "",
                "imprintA": a.get("imprint") or "(空)", "volsA": str(sorted(na)),
                "eiB": ib, "typeB": b.get("type") or "", "labelB": b.get("label") or "",
                "imprintB": b.get("imprint") or "(空)", "volsB": str(sorted(nb)),
                "publisher": pa or pb, "overlap": str(sorted(ov)),
                "merged": "{}-{}".format(min(uni), max(uni)),
                "years": "{}〜{}".format(seq[0], seq[-1]),
            })
    cols = ["tier", "slug", "title", "canonical", "publisher", "merged", "years", "overlap",
            "eiA", "typeA", "labelA", "imprintA", "volsA",
            "eiB", "typeB", "labelB", "imprintB", "volsB"]
    rows.sort(key=lambda r: (r["tier"], r["slug"]))
    dst = os.path.join(ROOT, "docs", "production-diagnostics", "intra-page-run-split.tsv")
    with io.open(dst, "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(r[c]).replace("\t", " ") for c in cols) + "\n")
    print("漫画内分裂(刊行runが同一頁の版タブに割れている疑い): {} ペア / {} 頁 → {}".format(
        len(rows), len({r["slug"] for r in rows}), dst))
    print("  tier:", dict(Counter(r["tier"] for r in rows)))
    print("  canonical seed:", dict(Counter(r["canonical"] for r in rows)))


if __name__ == "__main__":
    main()
