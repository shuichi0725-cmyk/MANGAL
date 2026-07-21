"""日本の歴史 各ページの巻を詳細展開(番号/ISBN/prefix/年/実題名)し混入を調査。"""
import json, yaml, re, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
tmap = json.load(open(f"{ROOT}/.cache/isbn-title-map.json", encoding="utf-8"))
amap = json.load(open(f"{ROOT}/.cache/isbn-author-map.json", encoding="utf-8"))

def reg(i):
    i = re.sub(r"\D", "", str(i or ""))
    if not i.startswith("9784") or len(i) != 13:
        return "無"
    b = i[4:12]; n = int(b[:2])
    return b[:2] if n <= 19 else b[:3] if n <= 69 else b[:4] if n <= 84 else b[:5] if n <= 89 else b[:6] if n <= 94 else b[:7]

slugs = ["nihonnorekishi", "nippon-no-rekishi-2007-2", "nippon-no-rekishi-2013", "nippon-no-rekishi-2015-9"]
for sl in slugs:
    p = f"{ROOT}/data/manga.v2/{sl}.yml"
    if not os.path.exists(p):
        print(sl, "無"); continue
    d = yaml.safe_load(open(p, encoding="utf-8"))
    print(f"\n■■■ {sl} | {d['title']} | 著{[a['name'] for a in d.get('authors',[])]}")
    for e in d.get("editions", []):
        print(f"  -- edition: type={e.get('type')} pub={e.get('publisher')}")
        for v in sorted(e.get("volumes", []), key=lambda x: (x.get("number") or 0, str(x.get("isbn13")))):
            ib = re.sub(r"\D", "", str(v.get("isbn13") or ""))
            rt = tmap.get(ib, "")[:30]
            ra = amap.get(ib, "")[:14]
            print(f"    vol{str(v.get('number')):>3} [{reg(ib)}] {ib or '(無)':14} {str(v.get('release_date') or ''):10} 実題[{rt}] 著[{ra}]")
