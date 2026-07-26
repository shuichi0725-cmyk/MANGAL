"""★種1→種2 の脱落監査: MADB(metadata101)に在るのに **種2に入らなかった** 巻を検出。

背景(2026-07-26 ユーザ指摘「本番ではなく種と比べて出てないっていってるのが含まれてない?」):
  既存の取りこぼし監査(`_audit-orphan-new-series.py`)は **種2→本番** しか見ておらず、
  **種2に入る前に消えた**レコードは構造的に検出できなかった。 実測 **9,797巻**。

★脱落理由は全件 `no_creator`(著者名が空)だった:
    schema:creator = ['', {'@value': '', '@language': 'ja-hrkt'}]
  `_build-series-v2.py` Phase2 は クラスタキーが「著者+題」なので **著者が取れない本を捨てる**
  ([[series_fragmentation_rootcause]] の弱点that)。 アンソロジー/成年誌/小規模出版に多い。

この監査は **read-only**(種1も種2も本番も触らない)。 直すかどうかの判断材料を出すのが目的:
  ①脱落の実数と理由内訳
  ②★**纏められるか** = (題, レーベル) で束ねた時に何巻のシリーズになるか
    (単巻ばらばらなら頁化の価値は低い / 複数巻で揃うなら独立作品として成立する)
  ③成年 contentRating の有無(= 掲載対象外の切り分け)

出力: docs/production-diagnostics/seed1-lost.tsv  (1行=1巻)
      docs/production-diagnostics/seed1-lost-groups.tsv (1行=纏めた候補シリーズ)

usage: python scripts/_audit-seed1-lost.py
"""
import collections
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
META = ROOT / ".cache" / "madb" / "metadata101-clean.json"
DB = ROOT / ".cache" / "db-v2.sqlite"
OUT = ROOT / "docs" / "production-diagnostics" / "seed1-lost.tsv"
OUT_G = ROOT / "docs" / "production-diagnostics" / "seed1-lost-groups.tsv"


def to13(s):
    d = re.sub(r"[^0-9Xx]", "", str(s or ""))
    if len(d) == 13:
        return d
    if len(d) == 10:
        core = "978" + d[:9]
        c = (10 - sum(int(x) * (1 if i % 2 == 0 else 3) for i, x in enumerate(core)) % 10) % 10
        return core + str(c)
    return None


def _build_funcs():
    """★判定は `_build-series-v2.py` 本体の関数をそのまま使う(条件の二重管理を避ける)。"""
    src = (ROOT / "scripts" / "_build-series-v2.py").read_text(encoding="utf-8").split("def main(")[0]
    ns = {"__name__": "notmain", "__file__": str(ROOT / "scripts" / "_build-series-v2.py")}
    exec(compile(src, "build_v2", "exec"), ns)
    return ns


def main():
    import ijson
    ns = _build_funcs()
    gpl, gna, pl, ecn = ns["get_primary_label"], ns["get_name_array"], ns["parse_label"], ns["extract_creator_names"]

    print("[1/3] 種2のISBNを読む ...", flush=True)
    con = sqlite3.connect(DB)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    have = {r[0] for r in con.execute("SELECT isbn13 FROM volumes WHERE isbn13 IS NOT NULL")}
    print(f"  種2 ISBN {len(have):,}", flush=True)

    print("[2/3] metadata101-clean を走査 ...", flush=True)
    rows, n, tot = [], 0, 0
    why = collections.Counter()
    with META.open("rb") as f:
        for b in ijson.items(f, "@graph.item"):
            n += 1
            if n % 100000 == 0:
                print(f"    ...{n:,}", flush=True)
            i = to13(b.get("schema:isbn"))
            if not i:
                continue
            tot += 1
            if i in have:
                continue
            lab = gpl(gna(b.get("schema:name")))
            base = pl(lab)[0] if lab else ""
            names = ecn(b.get("schema:creator", "")) if base else []
            r = ("no_label" if not lab else "no_base" if not base else
                 "no_creator" if not names else "other")
            why[r] += 1
            brand = b.get("schema:brand")
            if isinstance(brand, list):
                brand = next((x for x in brand if isinstance(x, str)), "")
            rating = b.get("schema:contentRating") or ""
            rows.append({
                "isbn": i, "reason": r, "title": (lab or "")[:80], "base": (base or "")[:60],
                "brand": str(brand or "")[:40], "date": str(b.get("schema:datePublished") or "")[:10],
                "pub": str((b.get("schema:publisher") if isinstance(b.get("schema:publisher"), str)
                            else (b.get("schema:publisher") or [""])[0]))[:30],
                "adult": "1" if re.match(r"成[年人]", str(rating)) else "",
                "vol": str(b.get("schema:volumeNumber") or "")[:8],
            })
    print(f"  種1 ISBN付き {tot:,} / ★種2に無い {len(rows):,} → 理由 {dict(why)}", flush=True)

    print("[3/3] ★纏められるか(題×レーベルで束ねる) ...", flush=True)
    g = collections.defaultdict(list)
    for r in rows:
        if r["adult"]:
            continue                      # 成年は掲載対象外なので束ね対象から外す
        g[(r["base"], r["brand"])].append(r)
    groups = sorted(g.items(), key=lambda kv: -len(kv[1]))
    multi = [x for x in groups if len(x[1]) >= 2]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        f.write("isbn\treason\tadult\ttitle\tbase\tvol\tbrand\tpub\tdate\n")
        for r in rows:
            f.write("\t".join([r["isbn"], r["reason"], r["adult"], r["title"], r["base"],
                               r["vol"], r["brand"], r["pub"], r["date"]]) + "\n")
    with OUT_G.open("w", encoding="utf-8", newline="") as f:
        f.write("vols\tbase\tbrand\tpub\tfirst_date\tlast_date\tisbns\n")
        for (base, brand), vs in groups:
            ds = sorted(x["date"] for x in vs if x["date"])
            f.write("\t".join([str(len(vs)), base, brand, vs[0]["pub"],
                               ds[0] if ds else "", ds[-1] if ds else "",
                               ",".join(x["isbn"] for x in vs[:8])]) + "\n")

    print(f"\n=== 種1→種2 脱落監査 ===")
    print(f"  ★脱落 {len(rows):,} 巻 / 理由 {dict(why)}")
    print(f"  成年 {sum(1 for r in rows if r['adult']):,} / 非成年 {sum(1 for r in rows if not r['adult']):,}")
    print(f"  ★纏まる候補(題×レーベルで2巻以上): {len(multi):,} シリーズ "
          f"({sum(len(v) for _, v in multi):,} 巻)")
    print(f"  単巻のまま: {len(groups) - len(multi):,}")
    print(f"  → {OUT}\n  → {OUT_G}")
    for (base, brand), vs in multi[:12]:
        ds = sorted(x["date"] for x in vs if x["date"])
        print(f"     {len(vs):3d}巻 「{base[:26]:28s}」 {brand[:18]:20s} {ds[0][:7] if ds else ''}")


if __name__ == "__main__":
    main()
