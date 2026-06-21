#!/usr/bin/env python3
"""
楽天246kから「通常版と同巻数・同内容の別版(新装版/復刻/別社版/別判型)」を持つ作品を検出。
= うる星の刷タブ候補。版ラン = (判型size, 題内マーカー, 出版社) で分け、同巻数の別ランがある作品をflag。
READ-ONLY。出力 data/seeds/same-content-edition-candidates.tsv。
"""
import sys, json, re, unicodedata, collections
sys.stdout.reconfigure(encoding="utf-8")

def to13(s):
    s = str(s or "").replace("-", "").strip(); return s if len(s) == 13 and s.isdigit() else ""
def nz(s): return re.sub(r"[\s　・！!？\?【】「」〜~,，、。:：;；/／\.．’'\"＆&\-]", "", unicodedata.normalize("NFKC", str(s or ""))).lower()

# 版マーカー(題/シリーズ名に出る)。順序=優先
MARKERS = [("完全版","完全版"),("新装版","新装版"),("新装","新装版"),("愛蔵版","愛蔵版"),
           ("復刻","復刻"),("カラー","カラー版"),("ワイド","ワイド版"),("文庫","文庫")]
# 除外(別物/別巻立て)
EXCLUDE = re.compile(r"(特装|限定|ドラマCD|アンソロ|セレクション|画集|原画|ファンブック|公式|ガイド|総集編|傑作|スペシャル|特集|セット|BOX|ノベル|小説)")

def parse(title, series, size):
    t = unicodedata.normalize("NFKC", str(title or ""))
    # 巻番号 抽出(末尾 (N) / N / 第N巻)
    m = re.search(r"[（(]\s*(\d+)\s*[）)]\s*$", t) or re.search(r"第\s*(\d+)\s*巻", t) or re.search(r"\s(\d+)\s*$", t)
    vol = int(m.group(1)) if m else None
    core = t[:m.start()] if m else t
    # マーカー判定(題 or シリーズ名)
    blob = core + "|" + str(series or "")
    marker = "通常"
    for kw, lab in MARKERS:
        if kw in blob: marker = lab; break
    # 判型でも補強(size)
    sz = str(size or "")
    if marker == "通常":
        if "文庫" in sz: marker = "文庫"
        elif "ワイド" in sz: marker = "ワイド版"
    # base = マーカー語・装飾を除いた核題
    base = core
    for kw, _ in MARKERS: base = base.replace(kw, "")
    base = nz(re.sub(r"[〔〕\[\]（）()【】]", "", base))
    return base, vol, marker

# work(base+author) -> marker -> set(vol)
works = collections.defaultdict(lambda: collections.defaultdict(set))
meta = {}
n = 0
for line in open(".cache/rakuten-isbn.jsonl", encoding="utf-8"):
    try: o = json.loads(line)
    except: continue
    it = o.get("item") or {}
    ib = to13(o.get("isbn") or it.get("isbn"))
    title = it.get("title", "")
    if not ib or not title or EXCLUDE.search(title): continue
    n += 1
    au = nz((it.get("author") or "").split("/")[0])
    base, vol, marker = parse(title, it.get("seriesName"), it.get("size"))
    if not base or vol is None or vol > 200: continue
    key = (base, au)
    works[key][marker].add(vol)
    meta.setdefault(key, title)

# 候補 = 2+マーカーが「同巻数(±1)かつ最大巻一致(±1)かつ≥3巻」
cands = []
for key, mk in works.items():
    runs = {m: vols for m, vols in mk.items() if len(vols) >= 3}
    if len(runs) < 2: continue
    items = sorted(runs.items(), key=lambda x: -len(x[1]))
    # 最大ランと同規模の別ランがあるか
    (m0, v0) = items[0]
    matches = [(m, v) for m, v in items if abs(max(v) - max(v0)) <= 1 and abs(len(v) - len(v0)) <= 2]
    if len(matches) >= 2:
        cands.append((key, items, len(v0), max(v0)))

cands.sort(key=lambda x: -x[3])
out = "data/seeds/same-content-edition-candidates.tsv"
with open(out, "w", encoding="utf-8") as f:
    f.write("title\tauthor\tmax_vol\truns(marker:巻数)\n")
    for (key, items, cnt, mx) in cands:
        runs_s = " / ".join(f"{m}:{len(v)}巻(〜{max(v)})" for m, v in items)
        f.write(f"{meta[key][:40]}\t{key[1][:16]}\t{mx}\t{runs_s}\n")
print(f"楽天有効レコード {n}")
print(f"★同内容別版 候補作品: {len(cands)}")
print("\n=== 上位サンプル(最大巻多い順) ===")
for (key, items, cnt, mx) in cands[:30]:
    runs_s = " / ".join(f"{m}:{len(v)}" for m, v in items)
    print(f"  [{meta[key][:30]}] 著{key[1][:12]} 最大{mx}巻 | {runs_s}")
print(f"\n→ {out}")
