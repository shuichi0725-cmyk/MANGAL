#!/usr/bin/env python3
"""
楽天246kから「版バリアント(愛蔵版/完全版/新装版/復刻/ワイド版/カラー版)」を持つ作品を抽出。
通常版はDB(MADB)にある前提 → 楽天で見つかる別版を「追加候補」として作品単位で集計。
READ-ONLY。出力 data/seeds/edition-variant-candidates.tsv。
"""
import sys, json, re, unicodedata, collections
sys.stdout.reconfigure(encoding="utf-8")

def to13(s):
    s = str(s or "").replace("-", "").strip(); return s if len(s) == 13 and s.isdigit() else ""
def nz(s): return re.sub(r"[\s　・！!？\?【】「」〜~,，、。:：;；/／\.．’'\"＆&\-]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()

# 版マーカー(長い順=完全版優先)。フルカラー→カラー版に正規化
MARK = [("フルカラー版","カラー版"),("オールカラー","カラー版"),("カラー版","カラー版"),
        ("完全版","完全版"),("愛蔵版","愛蔵版"),("新装版","新装版"),("復刻版","復刻"),("復刻","復刻"),("ワイド版","ワイド版")]
EXCLUDE = re.compile(r"(特装|限定|ドラマCD|アンソロ|セレクション|画集|原画|ファンブック|公式|ガイド|総集編|傑作|ノベル|小説|設定|資料)")

def parse(title, series):
    t = unicodedata.normalize("NFKC", str(title or ""))
    blob = t + "|" + unicodedata.normalize("NFKC", str(series or ""))
    marker = None
    for kw, lab in MARK:
        if kw in blob: marker = lab; break
    if not marker: return None
    # 巻番号
    m = re.search(r"[（(]\s*(\d+)\s*[）)]\s*$", t) or re.search(r"第\s*(\d+)\s*巻", t) or re.search(r"\s(\d+)\s*$", t)
    vol = int(m.group(1)) if m else 1
    core = t[:m.start()] if m else t
    for kw, _ in MARK: core = core.replace(kw, "")
    base = nz(re.sub(r"[〔〕\[\]（）()【】]", "", core))
    return base, vol, marker

# (base, author, marker) -> {vols}
runs = collections.defaultdict(set); ttl = {}
n = 0
for line in open(".cache/rakuten-isbn.jsonl", encoding="utf-8"):
    try: o = json.loads(line)
    except: continue
    it = o.get("item") or {}
    if not to13(o.get("isbn") or it.get("isbn")): continue
    title = it.get("title", "")
    if not title or EXCLUDE.search(title): continue
    p = parse(title, it.get("seriesName"))
    if not p: continue
    base, vol, marker = p
    if not base or vol > 200: continue
    au = nz((it.get("author") or "").split("/")[0])
    key = (base, au, marker)
    runs[key].add(vol); ttl.setdefault(key, title); n += 1

# 作品(base,au)単位に版を集約
works = collections.defaultdict(dict)
for (base, au, marker), vols in runs.items():
    if len(vols) >= 1: works[(base, au)][marker] = (len(vols), max(vols), ttl[(base, au, marker)])

rows = []
for (base, au), eds in works.items():
    total = sum(v[0] for v in eds.values())
    rows.append((base, au, eds, total))
rows.sort(key=lambda x: -x[3])

out = "data/seeds/edition-variant-candidates.tsv"
mkcount = collections.Counter()
with open(out, "w", encoding="utf-8") as f:
    f.write("title\tauthor\teditions(marker:巻数)\n")
    for base, au, eds, total in rows:
        for m in eds: mkcount[m] += 1
        eds_s = " / ".join(f"{m}:{v[0]}巻(〜{v[1]})" for m, v in sorted(eds.items(), key=lambda x: -x[1][0]))
        f.write(f"{ttl.get((base,au,list(eds)[0]),base)[:40]}\t{au[:16]}\t{eds_s}\n")
print(f"版マーカー付き楽天巻 {n}")
print(f"★版バリアントを持つ作品: {len(rows)}")
print("版別の作品数:")
for m, c in mkcount.most_common(): print(f"  {m}: {c}作")
print("\n=== 巻数多い順 上位30 ===")
for base, au, eds, total in rows[:30]:
    eds_s = " / ".join(f"{m}:{v[0]}" for m, v in sorted(eds.items(), key=lambda x: -x[1][0]))
    t = ttl.get((base, au, list(eds)[0]), base)
    print(f"  [{t[:32]}] 著{au[:10]} | {eds_s}")
print(f"\n→ {out}")
