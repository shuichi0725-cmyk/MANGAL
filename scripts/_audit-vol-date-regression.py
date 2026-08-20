"""★巻番号×発売日の大逆行監査(= ギャラ型 2026-08-17 ユーザ発見「三巻以降別物」)。

署名: 同一edition内で巻番号が進むのに発売日が**年単位で逆行**する。正体は
「同一クラスタに別作品/別時代の版が同居し、番号衝突で接ぎ木された頁」
(ギャラ=リメイク1-2巻2019-20 + 原作3-8巻1980-81。原作1-2巻はdedup負けで不可視)。

判定: edition(versionsは対象外=ミラー既知)内で number昇順に並べ、
  number_i < number_j かつ year_i - year_j >= THRESHOLD(既定5年) の最悪ペアを flag。
軽微な逆行(数日〜数年=重版/帯混入)は既存queue(date-disorder)の領域なので拾わない。

出力: docs/production-diagnostics/vol-date-regression.tsv(逆行年数の降順)
  列: slug / title / authors / edition / vols / worst(巻(日付)→巻(日付)) / 逆行年 / ISBNパターン
ISBNパターン: 逆行境界の前後でISBN有無が反転していれば接ぎ木の傍証(ギャラ=有→無)。

月次: 新規増加分を見る。是正はギャラ式(edition-overridesで2頁分離+anilist:false)。

★帯絞り込み(2026-08-20 新設。既定の挙動は不変=無指定なら従来どおり全件):
  --min-years N       逆行N年以上だけを表示(例: 10 = 5-9年帯[正史が混じる]を外す)
  --isbn-pattern 有→無  ISBNパターンで絞る(有→無=接ぎ木の強シグナル)
  ※絞り込みは**stdout表示のみ**。TSV台帳は常に全件で書く(台帳の連続性を壊さない)。
"""
import argparse
import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THRESHOLD = 5  # 年

ap = argparse.ArgumentParser()
ap.add_argument("--min-years", type=int, default=0,
                help="逆行N年以上だけをstdout表示(TSVは常に全件)")
ap.add_argument("--isbn-pattern", default="",
                help="ISBNパターン(有→無 等)でstdout表示を絞る(TSVは常に全件)")
ARGS = ap.parse_args()

try:
    import yaml
    try:
        from yaml import CSafeLoader as _Loader
    except ImportError:
        from yaml import SafeLoader as _Loader
except ImportError:
    sys.exit("PyYAML required")

rows = []
files = sorted(glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")))
for i, p in enumerate(files):
    if i % 10000 == 0:
        print(f"  scan {i}/{len(files)}", file=sys.stderr)
    try:
        d = yaml.load(open(p, encoding="utf-8"), Loader=_Loader)
    except Exception:
        continue
    if not isinstance(d, dict):
        continue
    slug = d.get("slug") or os.path.splitext(os.path.basename(p))[0]
    title = d.get("title") or ""
    authors = "・".join(a.get("name", "") for a in (d.get("authors") or []))
    for ed in d.get("editions") or []:
        vols = [(v.get("number"), str(v.get("release_date") or ""), bool(v.get("isbn13")))
                for v in (ed.get("volumes") or [])
                if v.get("number") is not None and v.get("release_date")]
        vols = [(n, rd, has) for n, rd, has in vols if re.match(r"^\d{4}", rd)]
        if len(vols) < 2:
            continue
        vols.sort(key=lambda t: t[0])
        # 最悪ペア: 前方(小番号)の年 - 後方(大番号)の年 の最大
        worst = None  # (regress_years, (n_i, rd_i, isbn_i), (n_j, rd_j, isbn_j))
        max_prev = None  # (year, n, rd, has) 走査済みの最大年(前方)
        for n, rd, has in vols:
            y = int(rd[:4])
            if max_prev and max_prev[0] - y >= THRESHOLD:
                reg = max_prev[0] - y
                if not worst or reg > worst[0]:
                    worst = (reg, (max_prev[1], max_prev[2], max_prev[3]), (n, rd, has))
            if not max_prev or y > max_prev[0]:
                max_prev = (y, n, rd, has)
        if worst:
            reg, a, b = worst
            isbn_pat = f"{'有' if a[2] else '無'}→{'有' if b[2] else '無'}"
            rows.append((reg, slug, title, authors, ed.get("type") or "", len(vols),
                         f"{a[0]}巻({a[1]})→{b[0]}巻({b[1]})", isbn_pat))

rows.sort(key=lambda r: -r[0])
out = os.path.join(ROOT, "docs", "production-diagnostics", "vol-date-regression.tsv")

# ★reason列(2026-08-20 gyara-anomalies方式の横展開): 「なぜ自動で触らない/残すのか」を
#   台帳自身が持つ。再実行しても消えない(旧TSVから slug+edition キーで引き継ぐ)。
#   空 = 新規・未裁定。書式は docs/production-diagnostics/README.md を参照。
old_reason = {}
if os.path.exists(out):
    with open(out, encoding="utf-8") as f:
        head = f.readline().rstrip("\n").split("\t")
        if "reason" in head:
            i_sl, i_ed, i_rs = head.index("slug"), head.index("edition"), head.index("reason")
            for line in f:
                c = line.rstrip("\n").split("\t")
                if len(c) > i_rs and c[i_rs]:
                    old_reason[(c[i_sl], c[i_ed])] = c[i_rs]
with open(out, "w", encoding="utf-8", newline="\n") as f:
    f.write("regress_years\tslug\ttitle\tauthors\tedition\tn_vols\tworst_pair\tisbn_pattern\treason\n")
    for r in rows:
        f.write("\t".join(str(x) for x in r) + "\t" + old_reason.get((r[1], r[4]), "") + "\n")
print(f"\nflag {len(rows)} 件(edition単位) → {out}")
from collections import Counter
print("逆行年数分布:", dict(sorted(Counter(min(r[0] // 10 * 10, 40) for r in rows).items())))
print("ISBNパターン:", dict(Counter(r[7] for r in rows)))

# ★帯絞り込み表示(TSVは上で全件書き済み=台帳不変。ここはstdoutのビューだけ)
if ARGS.min_years or ARGS.isbn_pattern:
    sel = [r for r in rows
           if r[0] >= ARGS.min_years and (not ARGS.isbn_pattern or r[7] == ARGS.isbn_pattern)]
    lbl = []
    if ARGS.min_years:
        lbl.append(f"逆行{ARGS.min_years}年以上")
    if ARGS.isbn_pattern:
        lbl.append(f"ISBN {ARGS.isbn_pattern}")
    print(f"\n絞り込み({' × '.join(lbl)}): {len(sel)} 件")
    for r in sel:
        print("  " + "\t".join(str(x) for x in r))
