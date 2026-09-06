# -*- coding: utf-8 -*-
"""【巻抜け充填の下ごしらえ】残gap頁 → 「どの版の何巻を埋めるか」の充填ターゲット表を作る。

★gap の定義は **索引(_build-list-index.py の vol_gap)と同じ「版(edition)単位」**に揃える。
  _volgap-virtual.py は type 単位で複数版を合算しており、同type複数版の頁で偽の穴を作る
  (子連れ狼: other が『漫画アクション・コミックス(1971)』[2,3] と『劇画キングシリーズ版』[1,9,10,28]
   の2版。合算すると 4..8 が欠けているように見えるが、版単位で見れば別物)。
  ① 版単位の min..max の穴
  ② 頁全体の最小巻>1 = 先頭欠け(1..min-1) → その最小巻を持つ版に付ける

経路(route)も判定する(= 直す先が版の出どころで変わる):
  seed4     = 種4(volumes-supplement*.yml)で埋まる版
  canon:*   = edition-canonical が作っている版(volumes / compact / extra[i])。
              canonical は promote の最後に editions を置換するので種4は効かない = seed本体に書く
  overrides = edition-overrides が editions を丸ごと置換している頁。同上

出力: docs/production-diagnostics/volgap-fill-targets.tsv
使用: python scripts/_volgap-gap-targets.py [--in TSV]
"""
import os
import sys
import re
import json
from collections import Counter

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "manga.v2")
IN = (sys.argv[sys.argv.index("--in") + 1] if "--in" in sys.argv
      else os.path.join(ROOT, "docs", "production-diagnostics", "vol_gap_virtual_remain.tsv"))


def nisbn(s):
    return re.sub(r"[^0-9X]", "", str(s or "").upper())


def norm_label(s):
    return re.sub(r"[\s　()（）]", "", str(s or ""))


# --- canonical / overrides ---
canon = {}
cdir = os.path.join(ROOT, "data", "seeds", "edition-canonical")
for p in sorted(os.listdir(cdir)):
    if not p.endswith(".yml"):
        continue
    try:
        canon[p[:-4]] = yaml.safe_load(open(os.path.join(cdir, p), encoding="utf-8")) or {}
    except Exception:
        pass
canon_fixed = {k for k, v in canon.items() if not v.get("open_tail")}
edov = json.load(open(os.path.join(ROOT, "data", "seeds", "edition-overrides.json"), encoding="utf-8"))
edov_eds = {k for k, v in edov.items() if (v or {}).get("editions")}
try:
    stem2pub = json.load(open(os.path.join(ROOT, ".cache", "prod-page-slugs.json"), encoding="utf-8"))
except Exception:
    stem2pub = {}


def canon_route(stem, etype, label):
    """canonical seed のどのリストがこの版を作っているか。作っていなければ None(=種4が効く)。"""
    s = canon.get(stem)
    if not s:
        return None
    nl = norm_label(label)
    if etype == "standard" and (not s.get("canonical_label")
                                or nl == norm_label(s.get("canonical_label")) or nl == "通常版"):
        return "canon:volumes"
    if etype == "aizoban" and s.get("compact_edition"):
        return "canon:compact"
    for i, xe in enumerate(s.get("extra_editions") or []):
        if (xe.get("type") or "kanzenban") == etype and norm_label(xe.get("label")) == nl:
            return "canon:extra[{}]".format(i)
    # 型だけ一致する extra が1本しか無ければそれ(ラベルはpromoteで加工されうる)
    same = [i for i, xe in enumerate(s.get("extra_editions") or [])
            if (xe.get("type") or "kanzenban") == etype]
    if len(same) == 1:
        return "canon:extra[{}]".format(same[0])
    if etype == "standard":
        return "canon:volumes"
    return None


rows = [l.rstrip("\n").split("\t") for l in open(IN, encoding="utf-8")][1:]
out = []
routec, typec, pagec = Counter(), Counter(), set()
for stem, _title, _g in rows:
    p = os.path.join(SRC, stem + ".yml")
    if not os.path.exists(p):
        continue
    d = yaml.safe_load(open(p, encoding="utf-8")) or {}
    pub_slug = stem2pub.get(stem, stem)
    ov = (pub_slug in edov_eds or stem in edov_eds)
    eds = d.get("editions") or []
    # 版ごとの巻(versionsは同一版の別刷=同じ巻集合なので合算する)
    einfo = []
    for ei, e in enumerate(eds):
        have = {}
        vlists = [e.get("volumes") or []] + [vv.get("volumes") or [] for vv in (e.get("versions") or [])]
        for vs in vlists:
            for v in vs:
                n = v.get("number")
                if n is None:
                    continue
                have.setdefault(n, (str(v.get("release_date") or ""), nisbn(v.get("isbn13"))))
        einfo.append({"ei": ei, "type": e.get("type") or "standard", "label": e.get("label") or "",
                      "imprint": e.get("imprint") or "", "publisher": e.get("publisher") or "",
                      "have": have})
    targets = []  # (ei, number, kind)
    for e in einfo:
        ints = sorted(n for n in e["have"] if float(n).is_integer())
        if len(ints) >= 2:
            for n in range(int(ints[0]), int(ints[-1]) + 1):
                if n not in e["have"]:
                    targets.append((e["ei"], n, "MID"))
    alln = [n for e in einfo for n in e["have"] if float(n).is_integer()]
    if alln and min(alln) > 1:
        mn = int(min(alln))
        host = next((e["ei"] for e in einfo if mn in e["have"]), einfo[0]["ei"] if einfo else None)
        if host is not None:
            for n in range(1, mn):
                targets.append((host, n, "LEAD"))
    if not targets:
        continue
    pagec.add(stem)
    for ei, n, kind in sorted(set(targets)):
        e = einfo[ei]
        route = ("overrides" if ov else
                 (canon_route(stem, e["type"], e["label"]) or "seed4") if stem in canon_fixed else "seed4")
        routec[route] += 1
        typec[e["type"]] += 1
        have = e["have"]
        ints = sorted(x for x in have if float(x).is_integer())
        pubpre = Counter(have[x][1][:7] for x in have if have[x][1])
        prev = max((x for x in ints if x < n), default=None)
        nxt = min((x for x in ints if x > n), default=None)
        out.append(dict(stem=stem, title=d.get("title", ""), route=route, ei=ei, etype=e["type"],
                        label=e["label"], imprint=e["imprint"], number=n, kind=kind,
                        main_prefix=(pubpre.most_common(1)[0][0] if pubpre else ""),
                        publisher=e["publisher"],
                        prev_num=prev if prev is not None else "",
                        prev_date=(have[prev][0] if prev is not None else ""),
                        prev_isbn=(have[prev][1] if prev is not None else ""),
                        next_num=nxt if nxt is not None else "",
                        next_date=(have[nxt][0] if nxt is not None else ""),
                        next_isbn=(have[nxt][1] if nxt is not None else ""),
                        ed_isbn_min=min([have[x][1] for x in have if have[x][1]], default=""),
                        ed_isbn_max=max([have[x][1] for x in have if have[x][1]], default=""),
                        have_n=len(have), have_min=(ints[0] if ints else ""),
                        have_max=(ints[-1] if ints else "")))

cols = ["stem", "title", "route", "ei", "etype", "label", "imprint", "number", "kind", "main_prefix",
        "publisher", "prev_num", "prev_date", "prev_isbn", "next_num", "next_date", "next_isbn",
        "ed_isbn_min", "ed_isbn_max", "have_n", "have_min", "have_max"]
outp = os.path.join(ROOT, "docs", "production-diagnostics", "volgap-fill-targets.tsv")
with open(outp, "w", encoding="utf-8", newline="") as f:
    f.write("\t".join(cols) + "\n")
    for r in out:
        f.write("\t".join(str(r[c]).replace("\t", " ") for c in cols) + "\n")
print("充填ターゲット {:,} 巻 / {} 頁".format(len(out), len(pagec)))
print("経路(巻数):", dict(routec.most_common()))
print("kind:", dict(Counter(r["kind"] for r in out)))
print("版type(巻数):", dict(typec.most_common()))
print("→ " + outp)
