# -*- coding: utf-8 -*-
"""【型・検出器】版タブの先頭欠け = 版が途中の巻番号から始まり、頁が「分裂して見える」(2026-09-07 新設)。

★鉄腕アトムでユーザ発見。 版「講談社コミックス(1993)」が **v6,8-15** から始まっていて、
  同じ頁の別タブ(KCスペシャル1987 v1-7)と並ぶため「1本の作品が割れている」ように見えた。
  実際は別ラインで、**その版の v1-5,7 が丸ごと落ちていた**だけ(種2には在るのに canonical が
  上書きして消していた)。 = 統合案件ではなく **充填案件**。

判定:
  版タブが ①巻を2冊以上持つ ②ISBNを1冊以上持つ ③最小巻 > 1
  ④同じ頁の**別のタブ**がその下の巻番号を持っている(= 並べると割れて見える)
  ⑤最小巻 <= LIMIT(既定20。 選集/部分復刻の巨大な穴を拾わない)

★これだけでは「新装版が5巻から復刻された」等の**正当な途中開始**を拾う。
  充填器(_volgap-local-fill-v2.py / _volgap-ndl-match.py)の5ゲート
  (題完全一致・版元prefix・ISBN連番・発売日・著者)で、実在する本が見つかった時だけ埋める
  = 見つからなければ提案されない自己限定型。

出力: docs/production-diagnostics/edition-lead-gap.tsv
  --emit-targets を付けると volgap-fill-targets.tsv と同じ形の充填ターゲットも出す
使用: python scripts/_audit-edition-lead-gap.py [--limit 20] [--emit-targets]
"""
import glob
import io
import json
import os
import re
import sys
from collections import Counter

import yaml
try:
    from yaml import CSafeLoader as L
except Exception:
    from yaml import SafeLoader as L

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMIT = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 20
EMIT = "--emit-targets" in sys.argv


def nisbn(s):
    return re.sub(r"[^0-9X]", "", str(s or "").upper())


def norm_label(s):
    return re.sub(r"[\s　()（）]", "", str(s or ""))


def main():
    canon = {}
    cdir = os.path.join(ROOT, "data", "seeds", "edition-canonical")
    for p in sorted(glob.glob(os.path.join(cdir, "*.yml"))):
        try:
            canon[os.path.basename(p)[:-4]] = yaml.load(io.open(p, encoding="utf-8"), Loader=L) or {}
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
        same = [i for i, xe in enumerate(s.get("extra_editions") or [])
                if (xe.get("type") or "kanzenban") == etype]
        if len(same) == 1:
            return "canon:extra[{}]".format(same[0])
        if etype == "standard":
            return "canon:volumes"
        return None

    rows, targets = [], []
    for p in sorted(glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml"))):
        try:
            d = yaml.load(io.open(p, encoding="utf-8"), Loader=L) or {}
        except Exception:
            continue
        stem = os.path.basename(p)[:-4]
        eds = d.get("editions") or []
        if len(eds) < 2:
            continue
        info = []
        for i, e in enumerate(eds):
            have = {}
            for vs in [e.get("volumes") or []] + [vv.get("volumes") or [] for vv in (e.get("versions") or [])]:
                for v in vs:
                    n = v.get("number")
                    if isinstance(n, int) and n >= 1:
                        have.setdefault(n, (str(v.get("release_date") or ""), nisbn(v.get("isbn13"))))
            info.append({"i": i, "type": e.get("type") or "standard", "label": e.get("label") or "",
                         "imprint": e.get("imprint") or "", "publisher": e.get("publisher") or "",
                         "have": have,
                         "isbns": {x[1] for x in have.values() if x[1]}})
        for e in info:
            if len(e["have"]) < 2 or not e["isbns"]:
                continue
            mn = min(e["have"])
            if mn <= 1 or mn > LIMIT:
                continue
            lower = [o["i"] for o in info if o["i"] != e["i"] and any(k < mn for k in o["have"])]
            if not lower:
                continue
            pub_slug = stem2pub.get(stem, stem)
            route = ("overrides" if (pub_slug in edov_eds or stem in edov_eds) else
                     (canon_route(stem, e["type"], e["label"]) or "seed4") if stem in canon_fixed
                     else "seed4")
            ints = sorted(e["have"])
            pubpre = Counter(e["have"][x][1][:7] for x in e["have"] if e["have"][x][1])
            rows.append({"slug": stem, "title": d.get("title") or "", "route": route,
                         "ei": e["i"], "etype": e["type"], "label": e["label"],
                         "imprint": e["imprint"], "publisher": e["publisher"],
                         "min": mn, "missing": str(list(range(1, mn))),
                         "have": str(ints[:20]),
                         "min_isbn": e["have"][mn][1], "min_date": e["have"][mn][0],
                         "lower_in": str(lower)})
            if EMIT:
                for n in range(1, mn):
                    targets.append({
                        "stem": stem, "title": d.get("title") or "", "route": route, "ei": e["i"],
                        "etype": e["type"], "label": e["label"], "imprint": e["imprint"],
                        "number": n, "kind": "ELEAD",
                        "main_prefix": (pubpre.most_common(1)[0][0] if pubpre else ""),
                        "publisher": e["publisher"],
                        "prev_num": "", "prev_date": "", "prev_isbn": "",
                        "next_num": mn, "next_date": e["have"][mn][0], "next_isbn": e["have"][mn][1],
                        "ed_isbn_min": min(e["isbns"]), "ed_isbn_max": max(e["isbns"]),
                        "have_n": len(e["have"]), "have_min": ints[0], "have_max": ints[-1]})

    cols = ["slug", "title", "route", "ei", "etype", "label", "imprint", "publisher",
            "min", "missing", "have", "min_isbn", "min_date", "lower_in"]
    dst = os.path.join(ROOT, "docs", "production-diagnostics", "edition-lead-gap.tsv")
    with io.open(dst, "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(r[c]).replace("\t", " ") for c in cols) + "\n")
    print("版タブの先頭欠け(頁が分裂して見える): {} 版 / {} 頁 → {}".format(
        len(rows), len({r["slug"] for r in rows}), dst))
    print("  経路:", dict(Counter(r["route"] for r in rows).most_common()))
    print("  欠け巻数:", dict(Counter(min(r["min"] - 1, 10) for r in rows).most_common()))
    if EMIT:
        tc = ["stem", "title", "route", "ei", "etype", "label", "imprint", "number", "kind",
              "main_prefix", "publisher", "prev_num", "prev_date", "prev_isbn",
              "next_num", "next_date", "next_isbn", "ed_isbn_min", "ed_isbn_max",
              "have_n", "have_min", "have_max"]
        dst2 = os.path.join(ROOT, "docs", "production-diagnostics", "edition-lead-targets.tsv")
        with io.open(dst2, "w", encoding="utf-8") as f:
            f.write("\t".join(tc) + "\n")
            for r in targets:
                f.write("\t".join(str(r[c]).replace("\t", " ") for c in tc) + "\n")
        print("  充填ターゲット {} 巻 → {}".format(len(targets), dst2))


if __name__ == "__main__":
    main()
