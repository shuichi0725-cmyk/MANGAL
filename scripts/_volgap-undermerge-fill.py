# -*- coding: utf-8 -*-
"""【巻抜け充填 第3段】A層(欠番巻が種2に在るのに本番のどの頁にも出ていない)を種4で結線する。

_volgap-exists-split.py が分けた層のうち **A_種2のみ(本番未描画)** だけを扱う。
= 楽天/NDLでその巻の実在は確認済み、種2にも入っている、なのに本番に出ていない
  (誤配属+番号衝突でdedupに負ける型 = [[volgap_diagnosis_order]] ②)。
種4で正しい series_key に結線すれば頁に出る。 二重化はしない(どこにも出ていないので)。

A2(自頁に別番号で在る) / B1(別頁・同題=頁分裂) / B2(別頁・別題) は**扱わない**
= 統合/番号付け直しの判断が要るため報告のみ。

ゲートは第1段と同じ5層を当て直す(EXISTS で打ち切っていたため):
  G2版元prefix / G3発売日 / G4著者 / G5 ISBN連番。
出力: docs/production-diagnostics/volgap-undermerge-fill.tsv + .cache/volgap-undermerge-rows.json
使用: python scripts/_volgap-undermerge-fill.py
"""
import os
import sys
import re
import json
import unicodedata
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPLIT = os.path.join(ROOT, "docs", "production-diagnostics", "volgap-exists-split.tsv")

_AUTHNORM = re.compile(r"[\s　,、/／・:：;；\.。\-−ー]")
_PD = re.compile(r"(\d{4})-?(\d{2})?-?(\d{2})?")


def anorm(s):
    return _AUTHNORM.sub("", unicodedata.normalize("NFKC", str(s or ""))).lower()


def pdate(s):
    m = _PD.match(str(s or ""))
    return (int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0)) if m else None


def main():
    import yaml
    L = open(SPLIT, encoding="utf-8").read().splitlines()
    cols = L[0].split("\t")
    rows = [dict(zip(cols, l.split("\t"))) for l in L[1:] if l.strip()]
    a = [r for r in rows if r["layer"] == "A_種2のみ(本番未描画)"]
    print("A層 {} 巻 / {} 頁".format(len(a), len({r["stem"] for r in a})))

    # ターゲット表から prev/next(ISBN・日付)・main_prefix・route を引き直す
    T = open(os.path.join(ROOT, "docs", "production-diagnostics", "volgap-fill-targets.tsv"),
             encoding="utf-8").read().splitlines()
    tc = T[0].split("\t")
    tg = {(r["stem"], r["ei"], r["number"]): r
          for r in (dict(zip(tc, l.split("\t"))) for l in T[1:] if l.strip())}

    pages = {}
    out = []
    for r in a:
        k = (r["stem"], r["ei"], r["number"])
        t = tg.get(k)
        if not t:
            continue
        if r["stem"] not in pages:
            d = yaml.safe_load(open(os.path.join(ROOT, "data", "manga.v2", r["stem"] + ".yml"),
                                    encoding="utf-8")) or {}
            auth = set()
            for key in ("authors", "original_authors"):
                for x in (d.get(key) or []):
                    nm = anorm(x.get("name"))
                    if nm and nm != "unknown":
                        auth.add(nm)
            pages[r["stem"]] = auth
        authors = pages[r["stem"]]
        ib = r["isbn"]
        mp, pi, ni = t["main_prefix"], t.get("prev_isbn") or "", t.get("next_isbn") or ""
        lo = pdate(t["prev_date"]) if t["prev_date"] else None
        hi = pdate(t["next_date"]) if t["next_date"] else None
        dt = pdate(r["date"]) if r["date"] else None
        P = None if not mp else (ib[:7] == mp)
        if pi and ni:
            I = pi < ib < ni
        elif pi:
            I = ib > pi
        elif ni:
            I = ib < ni
        else:
            I = None
        if not dt:
            D = None
        elif (lo and dt < lo) or (hi and dt > hi):
            D = False
        else:
            D = True
        ca = anorm(r["rak_author"])
        A = None if (not authors or not ca) else any(x and (x in ca or ca in x) for x in authors)

        def mk(x):
            return "o" if x is True else ("x" if x is False else "?")

        if P is False or I is False:
            tier, why = "REJECT_EDITION", ("版元prefix不一致" if P is False else "ISBN連番の外")
        elif P is True and I is True and (D is True or A is True):
            tier, why = "ACCEPT", "版元o+ISBN連番o+" + ("日付o" if D is True else "著者o")
        elif P is True and D is True and A is True:
            tier, why = "ACCEPT", "版元o+日付o+著者o"
        elif I is True and A is True and P is None:
            tier, why = "ACCEPT", "ISBN連番o+著者o"
        else:
            tier, why = "REVIEW", "証拠不足"
        out.append({**t, "tier": tier, "isbn": ib, "date": r["date"],
                    "rak_title": r["rak_title"], "rak_author": r["rak_author"],
                    "rak_publisher": r["rak_publisher"], "cover": "", "n_cands": 1,
                    "g_pub": mk(P), "g_isbn": mk(I), "g_date": mk(D), "g_author": mk(A),
                    "g_token": "o",
                    "why": why + " ※種2に在るのに本番未描画=結線もれ"})

    out.sort(key=lambda r: (r["tier"], r["stem"], int(r["number"])))
    cols_o = ["tier", "stem", "title", "route", "ei", "etype", "label", "imprint", "number", "kind",
              "isbn", "date", "rak_title", "rak_author", "rak_publisher",
              "g_pub", "g_isbn", "g_date", "g_author", "g_token",
              "main_prefix", "prev_num", "prev_isbn", "prev_date", "next_num", "next_isbn",
              "next_date", "publisher", "n_cands", "why", "cover"]
    outp = os.path.join(ROOT, "docs", "production-diagnostics", "volgap-undermerge-fill.tsv")
    with open(outp, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(cols_o) + "\n")
        for r in out:
            f.write("\t".join(str(r.get(c, "")).replace("\t", " ") for c in cols_o) + "\n")
    json.dump(out, open(os.path.join(ROOT, ".cache", "volgap-undermerge-rows.json"), "w",
                        encoding="utf-8"), ensure_ascii=False)
    c = Counter(r["tier"] for r in out)
    print("=== 裁定前 ===")
    for k, v in c.most_common():
        print("  {:16} {:4} 巻 / {} 頁".format(k, v, len({r["stem"] for r in out if r["tier"] == k})))
    print("→ " + outp)


if __name__ == "__main__":
    main()
