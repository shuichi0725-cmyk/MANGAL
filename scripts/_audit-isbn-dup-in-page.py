#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【監査】同じ頁の中で同じISBNが複数の巻に付いている巻を検出する(2026-09-06 ユーザ発見
「1と2のisbnが一緒」= 保健室の僕ら型)。同じ本が2巻に化けるので巻数も水増しになる。

原因は複数あり、初回23頁の実測内訳:
 ①特装版パスの置換(12頁)= 種2が通常版と特装版を別々の無番号巻で持ち、promoteが連番を振った後に
   special_isbn→normal_isbn へ置換して双子になる。→ promote側に衝突つぶしを結線済(恒久)。
 ②edition-canonical の作り物/誤記ISBN(3頁)= 銀牙伝説Weedに 9789784537100(978二重)が17巻分、
   ゴルゴ13 129巻に127巻のISBN、将太の寿司18巻に17巻のISBN。→ _check-edition-canonical.py の
   検査8/9(ISBN妥当性・同一ISBNの複数巻付与)で今後は入口で止まる。
 ③種4/offsetシードの誤補完(8頁)= 隣の巻のISBNを別番号に貼った。→ isbn-fill.json の
   replaces / drop_if_isbn(現在値を名指しした時だけ効く)で是正。

使い方: python scripts/_audit-isbn-dup-in-page.py
出力  : docs/production-diagnostics/isbn-dup-in-page.tsv(0行=健全)
高速化: まず生テキストでISBN重複のある頁だけを絞り、その頁だけYAMLで精査する。
"""
import glob, os, re, sys, collections, json
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try:
    from yaml import CSafeLoader as L
except ImportError:
    from yaml import SafeLoader as L

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISBN = re.compile(rb"isbn13:\s*'?(\d{13})'?")
cands = []
n = 0
for p in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
    n += 1
    b = open(p, "rb").read()
    isbns = ISBN.findall(b)
    if len(isbns) != len(set(isbns)):
        cands.append(p)
print(f"走査 {n:,}頁 → ISBNが頁内で重複 {len(cands):,}頁\n")

rows = []
for p in cands:
    d = yaml.load(open(p, encoding="utf-8"), Loader=L)
    if not d:
        continue
    slug = d.get("slug") or os.path.basename(p)[:-4]
    # 巻レベル(variantは除く)で同ISBNが2つ以上ある版を拾う
    for e in d.get("editions") or []:
        seen = collections.defaultdict(list)
        for v in e.get("volumes") or []:
            if v.get("isbn13"):
                seen[str(v["isbn13"])].append(v)
        for isbn, vs in seen.items():
            if len(vs) < 2:
                continue
            nums = [v.get("number") for v in vs]
            same_date = len({str(v.get("release_date")) for v in vs}) == 1
            has_var = all(v.get("variants") for v in vs)
            rows.append({
                "slug": slug, "file": os.path.basename(p), "type": e.get("type"),
                "isbn": isbn, "numbers": nums, "n": len(vs),
                "same_date": same_date, "all_have_variant": has_var,
                "total_vols": len(e.get("volumes") or []),
                "title": d.get("title") or "",
            })

print(f"★ 巻レベルで同ISBN重複 = {len(rows)}件 / {len({r['slug'] for r in rows})}頁\n")
c = collections.Counter((r["n"], r["all_have_variant"], r["same_date"]) for r in rows)
print("(重複数, 全部にvariant, 同一発売日) の内訳:")
for k, v in sorted(c.items(), key=lambda x: -x[1]):
    print(f"   {k}: {v}件")
print("\n巻数の内訳(その版の総巻数):", collections.Counter(r["total_vols"] for r in rows).most_common(8))
out = os.path.join(ROOT, "docs", "production-diagnostics", "isbn-dup-in-page.tsv")
with open(out, "w", encoding="utf-8", newline="") as f:
    f.write("slug\tfile\ttitle\tedition_type\tisbn\tnumbers\tdup_n\ttotal_vols\tsame_date\tall_have_variant\n")
    for r in sorted(rows, key=lambda r: (-r["n"], r["slug"])):
        f.write(f"{r['slug']}\t{r['file']}\t{r['title']}\t{r['type']}\t{r['isbn']}\t"
                f"{','.join(str(x) for x in r['numbers'])}\t{r['n']}\t{r['total_vols']}\t"
                f"{r['same_date']}\t{r['all_have_variant']}\n")
print(f"\n一覧 → {out}")
for r in rows[:12]:
    print(f"   {r['title'][:26]:<26} {r['type']:<9} 巻{r['numbers']} 総{r['total_vols']}巻 {r['isbn']}")
