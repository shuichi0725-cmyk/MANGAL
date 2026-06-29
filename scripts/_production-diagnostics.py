"""本番データ診断 = テスト専用パネル(HomeClient isPreview)の全判定を本番全量に適用し、
問題作の件数+実リストを出力。 私(Claude)が「ボタンを押す」代わりにこれを走らせて潰す。
索引(data/manga-list-index.json)由来=高速。 出力 docs/production-diagnostics/*.tsv。"""
import json, os, re

ROOT = "C:/Users/shuic/code/MANGAL"
OUT = f"{ROOT}/docs/production-diagnostics"
os.makedirs(OUT, exist_ok=True)
d = json.load(open(f"{ROOT}/data/manga-list-index.json", encoding="utf-8"))
fi = {k: i for i, k in enumerate(d["f"])}
rows = d["d"]

def g(r, k):
    return r[fi[k]] if k in fi else None

def au_names(r):
    return [a.get("name") for a in (g(r, "authors") or [])]

# 各診断: (キー, 説明, 述語)
DIAGS = [
    ("no_cover", "画像なし(cover無)", lambda r: not g(r, "cover")),
    ("solo_nonfirst", "1冊≠1巻(統合失敗signal)", lambda r: bool(g(r, "solo_nonfirst"))),
    ("vol_gap", "巻抜け(欠番)", lambda r: bool(g(r, "vol_gap"))),
    ("no_author", "著者なし/(unknown)", lambda r: not au_names(r) or all((not n or n == "(unknown)") for n in au_names(r))),
    ("anthology", "アンソロジー", lambda r: bool(g(r, "_anthology"))),
    ("pub_unknown", "出版社(unknown)", lambda r: g(r, "publisher") == "(unknown)"),
    ("no_date", "発売日(first_volume_date)無", lambda r: not g(r, "first_volume_date")),
    ("future_year", "発売年が未来/異常(>2027 or <1900)", lambda r: (g(r, "year_started") or 0) > 2027 or 0 < (g(r, "year_started") or 0) < 1900),
    ("title_pua", "title にPUA/制御文字", lambda r: bool(re.search(r"[-\x00-\x1f]", g(r, "title") or ""))),
    ("kana_missing", "title_kana 欠落", lambda r: not (g(r, "title_kana") or "").strip()),
]

print(f"=== 本番診断 (全 {len(rows)} 作) ===")
summary = []
for key, desc, pred in DIAGS:
    hit = [r for r in rows if pred(r)]
    summary.append((key, desc, len(hit)))
    with open(f"{OUT}/{key}.tsv", "w", encoding="utf-8", newline="") as f:
        f.write("slug\ttitle\tauthors\tyear\tpublisher\ttotal_volumes\n")
        for r in hit:
            f.write("\t".join([str(g(r, "slug") or ""), str(g(r, "title") or ""),
                               "・".join(n for n in au_names(r) if n),
                               str(g(r, "year_started") or ""), str(g(r, "publisher") or ""),
                               str(g(r, "total_volumes") or "")]) + "\n")
for key, desc, n in summary:
    print(f"  {desc:28} {n:>6}  → docs/production-diagnostics/{key}.tsv")
