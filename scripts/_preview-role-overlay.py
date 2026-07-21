"""役割mapを使い、 汚染seriesの著者 before/after を可視化(本番反映なし)。
判定: 作品(series)内で その人が
  - 一度でも author role  -> KEEP
  - 全て nonauthor role   -> DROP
  - unknown のみ          -> KEEP(保守的=誤落とし防止)
出力: .cache/role-overlay-preview.csv + 統計
"""
import os
import sqlite3, json, sys, re
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
db = sqlite3.connect(ROOT + "/.cache/db-v2.sqlite"); c = db.cursor()
roles = json.load(open(ROOT + "/.cache/madb-mid-roles.json", encoding="utf-8"))
sids = json.load(open(ROOT + "/.cache/polluted-sids.json"))

# 純粋非著者タグ(= これ「のみ」なら落とす)。 監修/原案協力 等 borderline は KEEP(偽keep>偽drop)
DROP_TAGS = {"編", "編集", "編纂", "解説", "共解説", "訳", "翻訳", "監訳", "発売", "頒布",
             "カバーデザイン", "装丁", "装幀", "デザイン", "ブックデザイン", "共同刊行・発売",
             "刊行", "協力", "企画", "校訂", "写真", "写真撮影", "資料提供", "取材", "構成協力"}

def cls_of(tag):
    if not tag:
        return "author"      # 無タグ = 単独著者 → keep
    if tag in DROP_TAGS:
        return "nonauthor"
    return "author"          # 監修/原案協力/未知 含め keep 寄せ

def norm(s):
    return re.sub(r"[・･\s　,，.\-‐―]", "", s).lower()

rows = []
flag_rows = []
stat = {"series": 0, "drop_total": 0, "keep_total": 0, "series_with_drop": 0,
        "author_restored": 0, "guarded_empty": 0}
import csv
for sid in sids:
    info = c.execute("SELECT series_key,title FROM series WHERE id=?", (sid,)).fetchone()
    if not info:
        continue
    skey, title = info
    madb = [r[0] for r in c.execute(
        "SELECT m.name FROM series_authors sa JOIN mangaka m ON sa.mangaka_id=m.id WHERE sa.series_id=?", (sid,)).fetchall()]
    if not madb:
        continue
    # series の volume madb_book_id
    mids = [r[0] for r in c.execute(
        "SELECT v.madb_book_id FROM volumes v JOIN editions e ON v.edition_id=e.id WHERE e.series_id=?", (sid,)).fetchall()]
    # name(norm) -> set(cls)
    name_cls = {}
    raw_names = {}  # norm -> 生name(最初に出たrole map表記)
    for mid in mids:
        for nm, tag, _cls in roles.get(mid, []):
            k = norm(nm)
            name_cls.setdefault(k, set()).add(cls_of(tag))
            raw_names.setdefault(k, nm)
    if not name_cls:
        continue  # 生role情報なし → 判定不能 skip
    stat["series"] += 1
    drops, keeps = [], []
    for m in madb:
        k = norm(m)
        cls = name_cls.get(k)
        if cls is None:
            keeps.append(m + "(role無)")  # roleマップに居ない → 保守keep
        elif "author" in cls:
            keeps.append(m)
        elif cls == {"nonauthor"}:
            drops.append(m)
        else:  # unknown のみ
            keeps.append(m + "(unk)")
    # role mapに author が居るのに madbに無い名(=取りこぼし著者の復活候補)
    restored = []
    madb_norm = {norm(m) for m in madb}
    for k, cls in name_cls.items():
        if "author" in cls and k not in madb_norm:
            restored.append(raw_names[k])
    # ★ゼロ著者ガード: 落とした結果 keep も restore も無いなら drop 撤回 + flag
    kept_real = [m for m in madb if m not in drops]
    guarded = False
    if not kept_real and not restored and drops:
        guarded = True
        stat["guarded_empty"] += 1
        flag_rows.append([skey, title, " | ".join(madb)])
        drops = []  # 撤回(現状維持)
    if restored:
        stat["author_restored"] += 1
    if drops:
        stat["series_with_drop"] += 1
    stat["drop_total"] += len(drops)
    stat["keep_total"] += len(keeps)
    if drops or restored:
        rows.append([skey, title, " | ".join(madb), " | ".join(drops),
                     " | ".join(keeps), " | ".join(restored), "GUARD" if guarded else ""])

with open(ROOT + "/.cache/role-overlay-preview.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["series_key", "title", "現著者(全)", "落とす(非著者)", "残す", "復活候補(著者だがmadb欠落)", "guard"])
    w.writerows(rows)
with open(ROOT + "/.cache/role-overlay-empty-flag.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["series_key", "title", "現著者(全員非著者=要手動)"])
    w.writerows(flag_rows)
print("統計:", stat)
print("出力: .cache/role-overlay-preview.csv  (drop/restoreある", len(rows), "件)")
print("ゼロ著者ガードでflagした作品:", stat["guarded_empty"], "→ role-overlay-empty-flag.csv")
