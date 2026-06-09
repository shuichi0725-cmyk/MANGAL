"""役割map(生MADBタグ)から 著者補正seed を生成。 series_key キー(安定)。
  drop = その作品の全volで「非著者roleのみ」だった現著者(編/解説/発売/頒布/訳/装丁/協力/企画bare)
  add  = 生[著]系タグで居るのに現著者に欠落 かつ 漫画家マスターに実在(qid/読み有) の著者
  ★ガード: drop後にkeep(現著者-drop)もaddも空 → drop撤回(現状維持)
出力: data/seeds/author-role-corrections.yml (純粋追加的overlay。 種2不変)
promote が series_key→sid 解決で適用予定。 本scriptは本番DBを書かない。
"""
import sqlite3, json, sys, re, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = "C:/Users/shuic/code/MANGAL"
db = sqlite3.connect(ROOT + "/.cache/db-v2.sqlite"); c = db.cursor()
roles = json.load(open(ROOT + "/.cache/madb-mid-roles.json", encoding="utf-8"))
sids = json.load(open(ROOT + "/.cache/polluted-sids.json"))

DROP_TAGS = {"編", "編集", "編纂", "解説", "共解説", "訳", "翻訳", "監訳", "発売", "頒布",
             "カバーデザイン", "装丁", "装幀", "デザイン", "ブックデザイン", "共同刊行・発売",
             "刊行", "協力", "企画", "校訂", "写真", "写真撮影", "資料提供", "取材", "構成協力"}

def cls_of(tag):
    if not tag:
        return "author"
    return "nonauthor" if tag in DROP_TAGS else "author"

def norm(s):
    return re.sub(r"[・･\s　,，.\-‐―]", "", s).lower()

# 漫画家マスター(name/normalized → qid)
master = {}; master_norm = {}
for name, qid in c.execute("SELECT name, qid FROM mangaka"):
    master[name] = qid
    master_norm.setdefault(norm(name), (name, qid))

def resolve(nm):
    if nm in master:
        return nm
    r = master_norm.get(norm(nm))
    return r[0] if r else None

entries = []
st = {"drop_series": 0, "add_series": 0, "drops": 0, "adds": 0, "guarded": 0}
for sid in sids:
    info = c.execute("SELECT series_key FROM series WHERE id=?", (sid,)).fetchone()
    if not info:
        continue
    skey = info[0]
    madb = [r[0] for r in c.execute(
        "SELECT m.name FROM series_authors sa JOIN mangaka m ON sa.mangaka_id=m.id WHERE sa.series_id=?", (sid,)).fetchall()]
    if not madb:
        continue
    mids = [r[0] for r in c.execute(
        "SELECT v.madb_book_id FROM volumes v JOIN editions e ON v.edition_id=e.id WHERE e.series_id=?", (sid,)).fetchall()]
    name_cls = {}; raw_names = {}
    for mid in mids:
        for nm, tag, _ in roles.get(mid, []):
            k = norm(nm)
            name_cls.setdefault(k, set()).add(cls_of(tag))
            raw_names.setdefault(k, nm)
    if not name_cls:
        continue
    madb_norm = {norm(m): m for m in madb}
    # drop = 現著者で「nonauthorのみ」
    drop = [m for m in madb if name_cls.get(norm(m)) == {"nonauthor"}]
    keep = [m for m in madb if m not in drop]
    # ★ADDは「救済のみ」: drop後に 実在の人物著者が0 の作品だけ復活
    # (= 永井豪作品は永井豪が残る→add無し。 変種重複ノイズを根絶)
    ENTITY = re.compile(r"企画|プロ$|プロダクション|スタジオ|製作委員会|委員会|編集部|ルーム|新企画社|開発室"
                        r"|プロジェクト|PROJECT|社$|室$|出版部|出版局|出版社|編集局|刊行会|刊行委員会"
                        r"|基金|財団|協会|学会|研究所|研究会|事務局|連盟|機構|センター|資料館|博物館"
                        r"|新聞社|放送局|出版$|書籍部|事業部|制作部|製作部")
    real_keep = [m for m in keep if not ENTITY.search(m)]
    add = []
    if not real_keep:
        # 変種重複dedup用の強norm(プロ系suffix除去)
        def vnorm(s):
            return re.sub(r"(プロダクション|プロジェクト|プロ)$", "", norm(s))
        seen = {vnorm(m) for m in keep}
        for k, cls in name_cls.items():
            if "author" in cls and k not in madb_norm:
                canon = resolve(raw_names[k])
                if not canon or canon in add or canon in madb:
                    continue
                if ENTITY.search(canon):
                    continue  # 救済はentityでなく人物のみ
                if vnorm(canon) in seen:
                    continue  # 既存の変種重複
                add.append(canon); seen.add(vnorm(canon))
    # ガード: 実在著者0 かつ 救済add 0 → drop撤回
    if not real_keep and not add and drop:
        st["guarded"] += 1
        drop = []
    if not drop and not add:
        continue
    e = {"series_key": skey}
    if drop:
        e["drop"] = drop; st["drop_series"] += 1; st["drops"] += len(drop)
    if add:
        e["add"] = add; st["add_series"] += 1; st["adds"] += len(add)
    entries.append(e)

import yaml
OUT = ROOT + "/data/seeds/author-role-corrections.yml"
with open(OUT, "w", encoding="utf-8") as f:
    f.write("schema_version: 1\n")
    f.write("generator: _gen-author-role-corrections.py (raw MADB role tags)\n")
    f.write("note: 種2不変。 promoteが series_key->sid 解決で適用。 drop=非著者role除去 / add=マスター実在の取りこぼし著者\n")
    f.write("corrections:\n")
    for e in entries:
        f.write("  - series_key: %s\n" % json.dumps(e["series_key"], ensure_ascii=False))
        if "drop" in e:
            f.write("    drop: [%s]\n" % ", ".join(json.dumps(x, ensure_ascii=False) for x in e["drop"]))
        if "add" in e:
            f.write("    add: [%s]\n" % ", ".join(json.dumps(x, ensure_ascii=False) for x in e["add"]))
print("補正entry:", len(entries), st)
print("出力:", OUT)
