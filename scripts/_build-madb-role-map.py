"""生 metadata101.json から M-id -> [(name, role_tag, role_class)] を抽出。
clean が剥がした [著]/[編]/[解説] タグを生データから復元。 本番反映なし(= mapキャッシュのみ)。
出力: .cache/madb-mid-roles.json  {Mid: [[name, tag, cls], ...]}
  cls = 'author' | 'nonauthor' | 'unknown'
"""
import os
import sys, re, json, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
RAW = ROOT + "/.cache/madb/metadata101.json"
OUT = ROOT + "/.cache/madb-mid-roles.json"

# 役割分類
AUTHOR = {"著", "著者", "作", "漫画", "まんが", "劇画", "作画", "画", "絵", "comic", "COMIC",
          "原作", "原案", "原作・監修", "シナリオ", "脚本", "脚色", "構成", "文", "ストーリー",
          "案", "キャラクター原案", "キャラクターデザイン", "ほか著", "他著", "共著", "作・画",
          "原画", "コミック", "企画・原作", "原作・作画"}
NONAUTHOR = {"編", "編集", "解説", "共解説", "監修", "訳", "翻訳", "発売", "頒布",
             "カバーデザイン", "装丁", "装幀", "デザイン", "共同刊行・発売", "刊行",
             "原案協力", "協力", "企画", "編・著"}  # 企画/編・著は borderline→nonauthor 寄せ
# 地名/出版地は純ゴミ(role tagに紛れ込み)
JUNK_PREFIX = ("東京", "出版地不明", "大阪", "京都")

def classify(tag):
    if tag in AUTHOR:
        return "author"
    if tag in NONAUTHOR:
        return "nonauthor"
    # 複合 "原作・監修" 等は author 優先で既に上に。 未知タグは unknown
    return "unknown"

def parse_creator(schema_creator):
    """schema:creator (str or list) -> [(name, tag, cls)]。 yomi dict は skip。"""
    items = schema_creator if isinstance(schema_creator, list) else [schema_creator]
    out = []
    for it in items:
        if isinstance(it, dict):  # {@value: ヨミ} = 直前 name の読み → 役割判定には不要
            continue
        if not isinstance(it, str) or not it.strip():
            continue
        s = it.strip()
        m = re.match(r"^\[\[?([^\]]{1,16})\]\s*(.+)$", s)  # [[著] 二重bracket も許容
        if m:
            tag, body = m.group(1).strip(), m.group(2).strip()
        else:
            tag, body = "", s
        # 地名ゴミ除去
        if any(body.startswith(j) or tag.startswith(j) for j in JUNK_PREFIX) and not tag:
            continue
        cls = classify(tag) if tag else "unknown"
        # 同タグ内 カンマ複数名 を分割(= [編]ルーム,新企画社)
        for nm in re.split(r"\s*[,，∥]\s*", body):
            nm = nm.strip().rstrip("　 ")
            if nm and not any(nm.startswith(j) for j in JUNK_PREFIX):
                out.append([nm, tag, cls])
    return out

print("json.load 中 (541MB, 数分)...", flush=True)
t0 = time.time()
with open(RAW, encoding="utf-8", errors="replace") as f:
    doc = json.load(f)
graph = doc.get("@graph", doc if isinstance(doc, list) else [])
print("load完了 %.0fs, records=%d。 解析..." % (time.time() - t0, len(graph)), flush=True)
out = {}
n = 0
for rec in graph:
    n += 1
    if not isinstance(rec, dict):
        continue
    mid = rec.get("schema:identifier") or (rec.get("@id", "").split("/")[-1])
    sc = rec.get("schema:creator")
    if mid and sc:
        cr = parse_creator(sc)
        if cr:
            out[mid] = cr
    if n % 100000 == 0:
        print("  %d/%d map=%d" % (n, len(graph), len(out)), flush=True)

json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
# 統計
from collections import Counter
cc = Counter()
for mid, cr in out.items():
    for nm, tag, cls in cr:
        cc[cls] += 1
print("完了: %d records / map=%d" % (n, len(out)), flush=True)
print("role class 分布:", dict(cc), flush=True)
print("出力:", OUT, flush=True)
