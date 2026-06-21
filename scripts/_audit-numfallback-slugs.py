#!/usr/bin/env python3
"""
数字fallback衝突slug 検出(READ-ONLY): slug末尾が「題に含まれない数字」= 姓化失敗の衝突disambig。
title_romaji を slug 化した base に対し、 slug = base + '-' + 数字(題に無い・非年) のものを抽出。
author-yomi で姓化可能か(=今なら題-姓-年に直せるか)も判定。出力 data/seeds/slug-numfallback.tsv。
"""
import sys, os, glob, re, unicodedata
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L
except ImportError: from yaml import SafeLoader as L
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def slugify(s):
    s = unicodedata.normalize("NFKC", str(s or "")).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s

# author-yomi (姓化可能性)
yomi = {}
yp = os.path.join(ROOT, "data", "seeds", "author-yomi.yml")
if os.path.exists(yp):
    yomi = yaml.load(open(yp, encoding="utf-8"), Loader=L) or {}

rows = []
n = 0
for fp in glob.glob(os.path.join(ROOT, "data", "manga.v2", "*.yml")):
    try: d = yaml.load(open(fp, encoding="utf-8"), Loader=L)
    except: continue
    if not isinstance(d, dict): continue
    n += 1
    slug = d.get("slug") or os.path.basename(fp)[:-4]
    m = re.match(r"^(.+)-(\d{3,6})$", slug)
    if not m: continue
    base, num = m.group(1), m.group(2)
    if 1900 <= int(num) <= 2030: continue  # 年は正当
    tr = slugify(d.get("title_romaji") or d.get("title"))
    # 数字が題ローマ字に含まれる = title由来 → 除外
    if num in re.sub(r"[^0-9]", "", tr): continue
    # base が title_romaji と概ね一致 = 純粋な衝突suffix
    if base != tr and not (tr and (base.startswith(tr[:6]) or tr.startswith(base[:6]))): continue
    au = (d.get("authors") or [{}])[0]
    name = au.get("name") or ""
    kana = au.get("kana") or yomi.get(name) or ""
    rows.append((slug, str(d.get("title"))[:24], num, name, kana, "姓化可" if kana else "読み無"))

out = os.path.join(ROOT, "data", "seeds", "slug-numfallback.tsv")
with open(out, "w", encoding="utf-8") as f:
    f.write("slug\ttitle\tnum_suffix\tauthor\tkana\tfixable\n")
    for r in rows: f.write("\t".join(str(x) for x in r) + "\n")
fixable = sum(1 for r in rows if r[5] == "姓化可")
print(f"走査 {n}ページ")
print(f"★数字fallback衝突slug: {len(rows)}件 (うち今なら姓化可 {fixable} / 読み無 {len(rows)-fixable})")
print(f"→ {out}")
for r in rows[:20]: print("  ", r[0], "| 著", r[3], "| kana", r[4][:12] or "(無)", "|", r[5])
