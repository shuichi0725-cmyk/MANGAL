"""アンソロジー検出(慎重版): 巻レベルアンソロを複数signal+作者多様性で精密抽出。
signal: ①NDL編(metadata101 [編]/編集部 creator) ②題名アンソロ ③巻内多作家(M-ID)
filter: 作者が多様(単一consistent作者でない=大全集/単著編集を除外) かつ アニメコミック/大全集除外。
種2 read-only。出力: data/seeds/anthology-candidates.tsv"""
import json, re, collections, sqlite3
ROOT = "C:/Users/shuic/code/MANGAL"
con = sqlite3.connect(f"file:{ROOT}/.cache/db-v2.sqlite?mode=ro", uri=True); con.text_factory = lambda b: b.decode("utf-8","replace")
roles = json.load(open(f"{ROOT}/.cache/madb-mid-roles.json", encoding="utf-8"))

# signal①: metadata101 [編] creator の ISBN集合
ed_isbn = set()
ED = re.compile(r"\[編\]|\[編集\]|編集部|編集委員")
md = json.load(open(f"{ROOT}/.cache/madb/metadata101.json", encoding="utf-8"))["@graph"]
for r in md:
    c = r.get("schema:creator") or []
    crs = [c] if isinstance(c, str) else [x for x in c if isinstance(x, str)]
    if any(ED.search(x) for x in crs):
        i = r.get("schema:isbn")
        for ib in ([i] if isinstance(i, str) else (i if isinstance(i, list) else [])):
            if isinstance(ib, str): ed_isbn.add(ib)
del md

sid_title = {r[0]: r[1] for r in con.execute("SELECT id,title FROM series")}
EXC = re.compile(r"アニメコミック|アニメーションコミック|フィルムコミック|大全集|傑作選|画集|作品集$")

# bulk: sid → 巻[(isbn, mid)]
sid_vols = collections.defaultdict(list)
for sid, isbn, mid in con.execute("SELECT e.series_id, v.isbn13, v.madb_book_id FROM volumes v JOIN editions e ON e.id=v.edition_id"):
    sid_vols[sid].append((isbn, mid))
COMP = re.compile(r"出版|編集|社$|局$|\[編\]")

rows = []
for sid, title in sid_title.items():
    vols = sid_vols.get(sid, [])
    has_ed = any(ib in ed_isbn for ib, _ in vols if ib)
    has_title = bool(re.search(r"アンソロジー|アンソロ", title or ""))
    volsets = [set(c[0] for c in roles[mid] if not COMP.search(c[0])) for _, mid in vols if mid in roles]
    allau = set().union(*volsets) if volsets else set()
    common = set.intersection(*volsets) if len(volsets) >= 2 else (volsets[0] if volsets else set())
    maxper = max((len(v) for v in volsets), default=0)
    has_multi = maxper >= 4
    # 作者多様性: 全巻共通作者なし かつ 総作家3+ (=単著編集でない)
    varied = len(allau) >= 3 and len(common) == 0
    # 分類
    signals = []
    if has_ed: signals.append("編")
    if has_title: signals.append("題名")
    if has_multi: signals.append("巻内多作家")
    if not signals: continue
    excluded = bool(EXC.search(title or ""))
    # アンソロ確度: 題名=高 / (編 or 多作家) かつ varied=中 / それ以外=低(要確認)
    if has_title and not excluded: conf = "高"
    elif (has_ed or has_multi) and varied and not excluded: conf = "中"
    elif excluded: conf = "除外(編集版/アニメ)"
    else: conf = "低(要確認)"
    rows.append((sid, title or "", "+".join(signals), len(allau), conf))

rows.sort(key=lambda x: (x[4], -x[3]))
with open(f"{ROOT}/data/seeds/anthology-candidates.tsv", "w", encoding="utf-8") as fo:
    fo.write("sid\ttitle\tsignals\tn_authors\tconfidence\n")
    for sid, t, sg, na, cf in rows: fo.write(f"{sid}\t{t[:40]}\t{sg}\t{na}\t{cf}\n")
cnt = collections.Counter(r[4] for r in rows)
print(f"アンソロ候補 総数: {len(rows)}")
for k in ["高", "中", "低(要確認)", "除外(編集版/アニメ)"]:
    print(f"  {k}: {cnt.get(k,0)}")
print(f"出力: data/seeds/anthology-candidates.tsv")
