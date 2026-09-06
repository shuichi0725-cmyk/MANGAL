# -*- coding: utf-8 -*-
"""【巻抜け充填 第3段の下ごしらえ】EXISTS(欠番巻のISBNが既に自前DBに在る)を層別する。

EXISTS = 楽天/NDLで欠番巻は見つかったが、そのISBNが 本番索引 か 種2 に既に在る。
= 「取込もれ」ではなく under-merge([[volgap_mostly_undermerge]])。 処方が違うので分ける:

  A) 種2にあるが **本番のどの頁にも出ていない** → 種4で正しい series_key に結線すれば出せる
     (誤配属+番号衝突でdedupに負けている型 = [[volgap_diagnosis_order]] ②)
  B) **別の本番頁に描画されている**   → その頁との統合/移設の判断が要る(自動でやらない)
     B1: 相手が同じ題(表記ゆれ含む) = 同一作の分裂の疑い → merge候補
     B2: 相手が別の題               = 別作/スピンオフの疑い → 触らない

出力: docs/production-diagnostics/volgap-exists-split.tsv
使用: python scripts/_volgap-exists-split.py
"""
import os
import sys
import re
import json
import sqlite3
import unicodedata
from collections import Counter

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
import _rakuten_match_lib as R

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "manga.v2")


def nisbn(s):
    return re.sub(r"[^0-9X]", "", str(s or "").upper())


def main():
    _rk = (sys.argv[sys.argv.index("--in") + 1] if "--in" in sys.argv
           else os.path.join(ROOT, ".cache", "volgap-local-fill-v2.json"))
    _nd = (sys.argv[sys.argv.index("--ndl") + 1] if "--ndl" in sys.argv
           else os.path.join(ROOT, ".cache", "volgap-ndl-fill-rows.json"))
    rk = json.load(open(_rk, encoding="utf-8"))
    nd = json.load(open(_nd, encoding="utf-8")) if os.path.exists(_nd) else []
    ndk = {(r["stem"], r["ei"], r["number"]): r for r in nd}
    final = {}
    for r in rk:
        k = (r["stem"], r["ei"], r["number"])
        final[k] = ndk.get(k, r) if r["tier"] in ("NOHIT", "DROPPED") else r
    ex = [r for r in final.values() if r["tier"] == "EXISTS"]
    print("EXISTS {} 巻 / {} 頁".format(len(ex), len({r["stem"] for r in ex})))

    page_index = json.load(open(os.path.join(ROOT, ".cache", "isbn-page-index.json"), encoding="utf-8"))
    con = sqlite3.connect(os.path.join(ROOT, ".cache", "db-v2.sqlite"))
    cur = con.cursor()

    # 公開slug → 題(索引から)
    ix = json.load(open(os.path.join(ROOT, "data", "manga-list-index.json"), encoding="utf-8"))
    f = ix["f"]
    si, ti = f.index("slug"), f.index("title")
    slug2title = {row[si]: row[ti] for row in ix["d"]}

    rows = []
    for r in ex:
        ib = r["isbn"]
        _o = page_index.get(ib)
        others = ([x for x in _o if x] if isinstance(_o, list) else ([_o] if _o else []))
        own = None
        d = yaml.safe_load(open(os.path.join(SRC, r["stem"] + ".yml"), encoding="utf-8")) or {}
        own = d.get("slug") or r["stem"]
        in_db = bool(list(cur.execute("SELECT 1 FROM volumes WHERE isbn13=? LIMIT 1", (ib,))))
        other = next((x for x in others if x != own), others[0] if others else "")
        if not others:
            layer = "A_種2のみ(本番未描画)"
            note = "種2に在るが本番のどの頁にも出ていない = 種4結線で出せる可能性"
            othertitle = ""
        elif all(x == own for x in others):
            layer = "A2_自頁に別巻番号で在る"
            note = "同じ頁の中に既に在る(番号違い/版違い) = 番号の付け直し領域"
            othertitle = slug2title.get(own, "")
        else:
            othertitle = slug2title.get(other, "")
            same = R.norm(R.nfkc(othertitle)) == R.norm(R.nfkc(d.get("title", "")))
            layer = "B1_別頁(同題)" if same else "B2_別頁(別題)"
            note = "描画先=" + ",".join(others)
        rows.append({**r, "layer": layer, "other_slug": other or "", "other_title": othertitle,
                     "in_db": "o" if in_db else "x", "layer_note": note})

    order = ["A_種2のみ(本番未描画)", "A2_自頁に別巻番号で在る", "B1_別頁(同題)", "B2_別頁(別題)"]
    rows.sort(key=lambda r: (order.index(r["layer"]), r["stem"], int(r["number"])))
    cols = ["layer", "stem", "title", "ei", "etype", "label", "number", "kind", "isbn", "date",
            "rak_title", "rak_author", "rak_publisher", "other_slug", "other_title", "in_db",
            "route", "layer_note"]
    outp = (sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv
            else os.path.join(ROOT, "docs", "production-diagnostics", "volgap-exists-split.tsv"))
    with open(outp, "w", encoding="utf-8", newline="") as fo:
        fo.write("\t".join(cols) + "\n")
        for r in rows:
            fo.write("\t".join(str(r.get(c, "")).replace("\t", " ") for c in cols) + "\n")
    c = Counter(r["layer"] for r in rows)
    print("=== 層別 ===")
    for k in order:
        print("  {:22} {:4} 巻 / {:3} 頁".format(
            k, c.get(k, 0), len({r["stem"] for r in rows if r["layer"] == k})))
    print("→ " + outp)
    for k in order:
        sub = [r for r in rows if r["layer"] == k]
        if not sub:
            continue
        print("\n--- {} 例 ---".format(k))
        for r in sub[:12]:
            print("   {:30s} v{:<4} {} {:10s} | {} | 相手={} {}".format(
                r["stem"][:30], r["number"], r["isbn"], r["date"][:10],
                r["rak_title"][:26], r["other_slug"][:24], r["other_title"][:18]))


if __name__ == "__main__":
    main()
