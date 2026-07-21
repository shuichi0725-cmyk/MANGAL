"""うる星やつら を NDLデータから 版/刷(versions)構造で生成。
通常版=初版/新装版/復刻box の3刷タブ、+ワイド版 +文庫版。既定=全巻ISBN有りの最古刷。
"""
import os
import json, sys, re
from collections import defaultdict
import yaml
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)

Z2H = str.maketrans("０１２３４５６７８９", "0123456789")
def volnum(s):
    s = (s or "").translate(Z2H)
    m = re.search(r"\d+", s)
    return int(m.group()) if m else None

def isbn13(s):
    s = (s or "").replace("-", "").upper()
    if len(s) == 13 and s.startswith("978"):
        return s
    if len(s) == 10:
        core = "978" + s[:9]
        t = sum((1 if i % 2 == 0 else 3) * int(c) for i, c in enumerate(core))
        return core + str((10 - t % 10) % 10)
    return ""

recs = json.load(open(ROOT + "/.cache/ndl-urusei.json", encoding="utf-8"))
def ismanga(r): return "726" in r["ndc"] or "高橋留美子" in r["creator"]

def collect(filt):
    """filt(r)→True のレコードを vol番号でdedup(13桁ISBN優先)。"""
    by = {}
    for r in recs:
        if not ismanga(r) or not filt(r):
            continue
        n = volnum(r["vol"]) or volnum(r["title"])
        if not n:
            continue
        isbn = isbn13(r["isbn"])
        cur = by.get(n)
        # 13桁ISBN有りを優先、 次に発売日古い
        score = (1 if isbn else 0)
        if cur is None or score > cur[0]:
            by[n] = (score, {"number": n, "isbn13": isbn or None, "asin": None,
                             "cover_url": None, "release_date": (r["date"][:7] if re.match(r"\d{4}-\d{2}", r["date"]) else (r["date"][:4] if re.match(r"\d{4}", r["date"]) else None))})
    return [v[1][1] for v in sorted(by.items())]

def yband(r, lo, hi):
    y = r["date"][:4]
    return y.isdigit() and lo <= int(y) <= hi

# 通常版の3刷
v_shohan = collect(lambda r: r["series"] == "少年サンデーコミックス" and yband(r, 1900, 1995) and "復刻" not in r["title"])
v_shinso = collect(lambda r: r["series"] == "少年サンデーコミックス" and yband(r, 1996, 2010))
v_fukkoku = collect(lambda r: r["series"] == "少年サンデーコミックス" and yband(r, 2011, 2100))
wide = collect(lambda r: "ワイド版" in r["series"] and "カラー" not in r["series"])
bunko = collect(lambda r: r["series"] == "小学館文庫")

def full_isbn(vols):
    return vols and all(v["isbn13"] for v in vols)

# 通常版 versions(古い順) + 既定=全巻ISBN有りの最古
versions = []
for lbl, yr, vs in [("初版", 1980, v_shohan), ("新装版", 2006, v_shinso), ("復刻BOX", 2022, v_fukkoku)]:
    if vs:
        versions.append({"label": lbl, "year_started": yr, "volumes": vs, "_full": full_isbn(vs)})
versions.sort(key=lambda x: x["year_started"])
default = next((v for v in versions if v["_full"]), versions[0]) if versions else None

editions = []
if versions:
    editions.append({
        "type": "standard", "label": "通常版", "publisher": "小学館", "imprint": "少年サンデーコミックス",
        "volumes": default["volumes"],
        "versions": [{"label": v["label"], "year_started": v["year_started"], "volumes": v["volumes"]} for v in versions],
    })
if wide:
    editions.append({"type": "wideban", "label": "ワイド版", "publisher": "小学館", "imprint": "少年サンデーコミックスワイド版", "volumes": wide})
if bunko:
    editions.append({"type": "bunkobon", "label": "文庫版", "publisher": "小学館", "imprint": "小学館文庫", "volumes": bunko})

doc = {
    "slug": "urusei-yatsura", "title": "うる星やつら", "title_kana": "ウルセイヤツラ",
    "title_romaji": "urusei yatsura", "year_started": 1978, "year_ended": 1987, "status": "completed",
    "authors": [{"name": "高橋留美子", "role": "writer_artist"}], "original_authors": [],
    "publisher": "shogakukan", "magazine": None, "demographic": "shounen",
    "genres": ["comedy", "romance"], "synopsis": "", "anime_adapted": True,
    "alternative_titles": {"en": "Urusei Yatsura"}, "editions": editions, "_source": "ndl-versions",
}
open(ROOT + "/data/manga/urusei-yatsura.yml", "w", encoding="utf-8").write(
    "# うる星やつら: NDL版/刷タブ構造\n" + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False))

print("通常版 刷:")
for v in versions:
    print("  %s : %d巻 全ISBN有=%s %s" % (v["label"], len(v["volumes"]), v["_full"], "←既定" if v is default else ""))
print("ワイド版 %d巻 / 文庫版 %d巻" % (len(wide), len(bunko)))
print("既定刷 =", default["label"] if default else "?")
