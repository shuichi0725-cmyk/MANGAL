"""全DB公開可否 + 被覆監査(read-only)。 全DB promote 前の地雷洗い出し。

①真の公開数(巻数0=no_editions drop 後)②★有名作取りこぼし(高巻数なのにAniList未紐付け)
③ジャンク(文字化けPUA/外国書誌/著者ゼロ)④被覆を巻数帯別に。
"""
import sys, json, csv, sqlite3, importlib.util, re
from collections import defaultdict
from pathlib import Path
import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path("C:/Users/shuic/code/mangal"); csv.field_size_limit(10**7)
spec = importlib.util.spec_from_file_location("promote", ROOT / "scripts/_promote-bulk-v2.py")
pm = importlib.util.module_from_spec(spec); sys.argv = ["x"]; spec.loader.exec_module(pm)
PRE, CON, SUBP = pm.DROP_TITLE_PREFIX_PATTERNS, pm.DROP_TITLE_CONTAINS_PATTERNS, pm.DROP_SUBTITLE_PATTERNS

# merge(auto+hand)
key2page = {}
for g in json.load((ROOT / "data/seeds/series-merge-auto.json").open(encoding="utf-8"))["merges"]:
    mk = g.get("merge_keys") or []
    for k in mk: key2page[k] = mk[0]
for e in (yaml.safe_load((ROOT / "data/seeds/series-merge.yml").read_text(encoding="utf-8")) or []):
    mk = e.get("merge_keys") or []
    if len(mk) >= 2:
        for k in mk: key2page[k] = mk[0]

pages = defaultdict(lambda: {"members": [], "title": None, "repvols": 0})
with (ROOT / ".cache/slug-final.tsv").open(encoding="utf-8") as f:
    for row in csv.DictReader(f, delimiter="\t"):
        pid = key2page.get(row["key"], row["rep"]); p = pages[pid]; p["members"].append(row["key"])
        try: v = int(row["vols"] or 0)
        except: v = 0
        if p["title"] is None or v > p["repvols"]: p["title"] = row["title"]; p["repvols"] = v

con = sqlite3.connect(ROOT / ".cache/db-v2.sqlite"); con.text_factory = lambda b: b.decode("utf-8", "replace")
s_sub = {k: (sub or "") for k, sub in con.execute("SELECT series_key, subtitle FROM series")}
# series_key → 最大巻番号(=シリーズ長の代理)
maxvol = defaultdict(int)
for k, mx in con.execute("""SELECT s.series_key, MAX(v.number) FROM series s
    JOIN editions e ON e.series_id=s.id JOIN volumes v ON v.edition_id=e.id GROUP BY s.series_key"""):
    maxvol[k] = mx or 0
# series_key → 著者数
nauth = defaultdict(int)
for k, c in con.execute("""SELECT s.series_key, COUNT(DISTINCT sa.mangaka_id) FROM series s
    JOIN series_authors sa ON sa.series_id=s.id GROUP BY s.series_key"""):
    nauth[k] = c
con.close()
mag = set()
for e in (yaml.safe_load((ROOT / "data/seeds/magazines-drop.yml").read_text(encoding="utf-8")) or {}).get("magazines", []):
    if e.get("series_key"): mag.add(e["series_key"])
enrich = json.load((ROOT / ".cache/anilist-enrich-map.json").open(encoding="utf-8"))
key2aid = {k: str(v["anilist_id"]) for k, v in enrich.items() if isinstance(v, dict) and v.get("anilist_id")}
syn = set(json.load((ROOT / ".cache/synopsis-ja-map.json").open(encoding="utf-8")).keys())

def garbled(t):
    return bool(re.search(r"「.」|�", t))  # PUA代替 「A」 や replacement char
def foreign_desc(t):
    # 長い ASCII主体(外国図書館書誌: "Akira Katsuhiro Otomo ; [traduction...]")
    ascii_ratio = sum(c.isascii() for c in t) / max(len(t), 1)
    return len(t) > 45 and ascii_ratio > 0.85

# 集計
pub = 0; novol = 0
tiers = {"1": 0, "2-4": 0, "5-9": 0, "10-19": 0, "20+": 0}
cov_by_tier = defaultdict(lambda: {"n": 0, "ani": 0, "syn": 0})
flags = {"garbled": 0, "foreign_desc": 0, "no_author": 0}
famous_no_ani = []  # 高巻数なのにAniList無
for pid, p in pages.items():
    t = p["title"] or ""; m = p["members"]
    if any(t.startswith(x) for x in PRE): continue
    if any(x in t for x in CON): continue
    if any(x in mag for x in m): continue
    if any(x in s_sub.get(k, "") for k in m for x in SUBP): continue
    mv = max((maxvol.get(k, 0) for k in m), default=0)
    if mv == 0:
        novol += 1; continue  # promote の no_editions 相当(真の公開外)
    pub += 1
    tier = "1" if mv == 1 else "2-4" if mv <= 4 else "5-9" if mv <= 9 else "10-19" if mv <= 19 else "20+"
    tiers[tier] += 1
    has_ani = any(k in key2aid for k in m)
    has_syn = any(key2aid[k] in syn for k in m if k in key2aid)
    c = cov_by_tier[tier]; c["n"] += 1; c["ani"] += has_ani; c["syn"] += has_syn
    if garbled(t): flags["garbled"] += 1
    if foreign_desc(t): flags["foreign_desc"] += 1
    if max((nauth.get(k, 0) for k in m), default=0) == 0: flags["no_author"] += 1
    if not has_ani and mv >= 10:
        famous_no_ani.append((mv, t, max(m, key=lambda k: maxvol.get(k, 0))))

print(f"=== ① 真の公開数 ===")
print(f"  巻数≥1の公開ページ: {pub:,}")
print(f"  ★巻数0で除外(no_editions相当): {novol:,}(dryrun推計に混入していた分)")
print(f"\n=== ② 巻数帯分布 + 被覆 ===")
for tier in ["1", "2-4", "5-9", "10-19", "20+"]:
    c = cov_by_tier[tier]; n = c["n"] or 1
    print(f"  {tier:>6}巻: {c['n']:>6,}ページ  AniList {c['ani']*100//n}%  紹介文 {c['syn']*100//n}%")
print(f"\n=== ③ ★有名作取りこぼし候補(巻数≥10だがAniList未紐付け){len(famous_no_ani):,}件 ===")
for mv, t, k in sorted(famous_no_ani, reverse=True)[:25]:
    print(f"  {mv:>3}巻 「{t[:34]}」")
print(f"\n=== ④ ジャンク flag ===")
for k, v in flags.items(): print(f"  {k}: {v:,}")
