"""見直しの一括 apply の「前と後」(頁の要素の表示)を頁ごとに並べる。 ★読むだけ・何も書かない(出力は .cache)。

前 = 今の本番頁(data/manga.v2)の要素の表示。 後 = その頁に tags-enrich-2425.json の語を足し、tags-hide.json の語を外した表示。
表示の決まりは _build-list-index.themes_of(= 頁の elemItems と同じ)をそのまま使う。
★promote 前に見るための近似(promote の他の seed 由来の変化は入らない)。 反映後の正確な数は索引で確かめる。

  python scripts/_element-review-compare.py            # → .cache/element-review-compare.tsv / .json(変わる頁だけ)
"""
import collections, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import yaml

L = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def _themes_of():
    # ★_build-list-index は import すると索引作りまで走る = 表示の決まりの節(要素タグ〜cover_of の前)だけを読み込む
    src = open(os.path.join(ROOT, "scripts", "_build-list-index.py"), encoding="utf-8").read()
    a = src.index("# ── 要素タグ(themes)算出"); b = src.index("def cover_of")
    g = {"os": os, "yaml": yaml, "L": L, "DATA": os.environ.get("MANGAL_DATA_DIR", "data")}
    exec(compile(src[a:b], "_build-list-index.py(themes)", "exec"), g)
    return g["themes_of"]


themes_of = _themes_of()
LEDGER = os.path.join("data", "element-harvest", "review-ledger.jsonl")
OUT = os.path.join(".cache", "element-review-compare")


def load(p):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def main():
    enrich = load(os.path.join("data", "seeds", "tags-enrich-2425.json"))
    hide = load(os.path.join("data", "seeds", "tags-hide.json"))
    last = {}
    for l in open(LEDGER, encoding="utf-8"):
        r = json.loads(l)
        last[r["stem"]] = r
    rows = []
    n = b_all = a_all = z_b = z_a = 0
    plus = collections.Counter(); minus = collections.Counter()
    for stem, r in last.items():
        if r.get("route") not in ("L", "A", "後"):
            continue
        pg = os.path.join("data", "manga.v2", stem + ".yml")
        if not os.path.exists(pg):
            continue
        doc = yaml.load(open(pg, encoding="utf-8"), Loader=L) or {}
        n += 1
        tags = [t for t in (doc.get("tags") or []) if isinstance(t, dict)]
        bef = themes_of(doc)
        keys = dict.fromkeys((stem, doc.get("slug") or stem))
        th = {x for k in keys for x in (hide.get(k) or [])}
        have = {t.get("name") for t in tags}
        add = [x for k in keys for x in (enrich.get(k) or []) if x not in have]
        new = [t for t in tags if not (t.get("category") != "Demographic" and t.get("name") in th)]
        new += [{"name": x} for x in dict.fromkeys(add) if x not in th]  # promote も足してから外す(両方に在る語は出ない)
        aft = themes_of(dict(doc, tags=new))
        b_all += len(bef); a_all += len(aft); z_b += not bef; z_a += not aft
        p = [x for x in aft if x not in bef]; m = [x for x in bef if x not in aft]
        plus.update(p); minus.update(m)
        if not p and not m:
            continue
        # 外した語の理由(付与案の隠しの行から)
        why = {}
        pj = os.path.join(".cache", "element-harvest", stem, "assign", "assign-proposal.json")
        if m and os.path.exists(pj):
            for e in load(pj).get("rows") or []:
                if e.get("cls") == "隠し" and e.get("word") in m:
                    why[e["word"]] = e.get("hid") or ""
        rows.append({"s": doc.get("slug") or stem, "t": doc.get("title") or stem, "r": r.get("route"),
                     "b": bef, "a": aft, "p": p, "m": m, "w": why})
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "compare.tsv"), "w", encoding="utf-8", newline="") as f:
        f.write("slug\t題\t経路\t前\t後\t増える\t減る(理由)\n")
        for x in rows:
            mm = "・".join(f"{w}({x['w'].get(w, '?')})" for w in x["m"])
            f.write("\t".join([x["s"], x["t"], x["r"], "・".join(x["b"]), "・".join(x["a"]), "・".join(x["p"]), mm]) + "\n")
    stat = {"頁": n, "変わる頁": len(rows), "前": b_all, "後": a_all, "前0": z_b, "後0": z_a,
            "増える頁": sum(1 for x in rows if x["p"]), "増える語": sum(plus.values()),
            "減る頁": sum(1 for x in rows if x["m"]), "減る語": sum(minus.values()),
            "増える多い": plus.most_common(30), "減る多い": minus.most_common(30)}
    json.dump({"stat": stat, "rows": rows}, open(os.path.join(OUT, "compare.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"頁 {n:,} / 変わる頁 {len(rows):,} / 要素 のべ {b_all:,} → {a_all:,} / 増える {stat['増える頁']:,}頁 {stat['増える語']:,}語"
          f" / 減る {stat['減る頁']:,}頁 {stat['減る語']:,}語 / 要素0の頁 {z_b:,} → {z_a:,}")
    print("増える:", "・".join(f"{w}{c}" for w, c in plus.most_common(15)))
    print("減る:", "・".join(f"{w}{c}" for w, c in minus.most_common(15)))
    print("→", os.path.join(OUT, "compare.tsv"))


if __name__ == "__main__":
    main()
