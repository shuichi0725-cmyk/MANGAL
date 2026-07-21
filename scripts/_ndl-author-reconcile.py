"""NDL by-ISBN キャッシュ vs MADB(種2)著者 を汚染シリーズで突合 → 提案レビューCSV。
本番反映なし。 人間レビュー用。
  KEEP        = MADB著者がNDL creator(著/漫画/作画/原作/画/原案)に一致
  ROLE        = NDLで役割が判明(writer_artist → 原作/作画等)
  DEMOTE/DROP = NDLが編集/解説/監修 or NDL不在(=MADBノイズ疑い)
  ADD         = NDL creatorだがMADBに無い(=取りこぼし。 読み/典拠ID付きで追加候補)
"""
import sqlite3, sys, re, json, os, csv
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
db = sqlite3.connect(ROOT + "/.cache/db-v2.sqlite"); c = db.cursor()
ndl = json.load(open(ROOT + "/.cache/ndl-by-isbn.json", encoding="utf-8"))
sids = json.load(open(ROOT + "/.cache/polluted-sids.json"))
VAR = str.maketrans({"髙": "高", "﨑": "崎", "德": "徳", "廣": "広", "濵": "浜", "桒": "桑"})
AUTHOR_ROLES = {"著", "著者", "漫画", "作画", "画", "絵", "イラスト", "原作", "原案",
                "キャラクター原案", "構成", "脚本", "作", "案", "原著"}
NONAUTHOR_ROLES = {"編", "編集", "監修", "解説", "訳", "翻訳"}

def norm(s):
    return re.sub(r"[\s・･,、.\-‐―ー]", "", s).translate(VAR).lower()

# series_id -> NDL creators (aggregated over its ISBNs)
def series_isbns(sid):
    return [r[0] for r in c.execute(
        "SELECT v.isbn13 FROM volumes v JOIN editions e ON v.edition_id=e.id "
        "WHERE e.series_id=? AND v.isbn13 IS NOT NULL", (sid,)).fetchall()]

rows = []
for sid in sids:
    info = c.execute("SELECT series_key,title FROM series WHERE id=?", (sid,)).fetchone()
    if not info:
        continue
    skey, title = info
    madb = [r[0] for r in c.execute(
        "SELECT m.name FROM series_authors sa JOIN mangaka m ON sa.mangaka_id=m.id "
        "WHERE sa.series_id=?", (sid,)).fetchall()]
    # NDL creators across volumes
    ndl_map = {}  # norm -> {name, roles:set, yomi, authid}
    n_isbn = n_ndl = 0
    for isbn in series_isbns(sid):
        n_isbn += 1
        rec = ndl.get(isbn)
        if not rec or "_err" in rec or not rec.get("creators"):
            continue
        n_ndl += 1
        for cr in rec["creators"]:
            k = norm(cr["name"])
            if not k:
                continue
            e = ndl_map.setdefault(k, {"name": cr["name"], "roles": set(), "yomi": cr.get("yomi", ""), "authid": cr.get("authid", "")})
            if cr.get("role"):
                e["roles"].add(cr["role"])
            if cr.get("yomi") and not e["yomi"]:
                e["yomi"] = cr["yomi"]
            if cr.get("authid") and not e["authid"]:
                e["authid"] = cr["authid"]
    if n_ndl == 0:
        continue  # NDLデータ無し → 判断不能、 skip
    madb_norm = {norm(m): m for m in madb}
    # MADB側の判定
    for k, mname in madb_norm.items():
        if k in ndl_map:
            roles = ndl_map[k]["roles"]
            if roles & AUTHOR_ROLES:
                verdict = "KEEP/ROLE:" + ",".join(sorted(roles & AUTHOR_ROLES))
            elif roles & NONAUTHOR_ROLES:
                verdict = "DEMOTE:" + ",".join(sorted(roles & NONAUTHOR_ROLES))
            else:
                verdict = "KEEP(role不明)"
        else:
            verdict = "DROP?(NDL不在)"
        rows.append([skey, title, mname, verdict, "", n_ndl, n_isbn])
    # NDLにあってMADBに無い = ADD候補
    for k, e in ndl_map.items():
        if k not in madb_norm and (e["roles"] & AUTHOR_ROLES or not e["roles"]):
            rows.append([skey, title, "", "ADD:" + (",".join(sorted(e["roles"])) or "?"),
                         e["name"] + ("|読:" + e["yomi"] if e["yomi"] else "") + ("|NDL:" + e["authid"] if e["authid"] else ""),
                         n_ndl, n_isbn])

out = ROOT + "/.cache/ndl-author-reconcile.csv"
with open(out, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["series_key", "title", "MADB著者", "判定", "NDL追加候補(読み/典拠)", "NDL一致巻数", "総ISBN数"])
    w.writerows(rows)
from collections import Counter
cnt = Counter(r[3].split(":")[0].split("(")[0] for r in rows)
print("レビュー行:", len(rows))
for k, v in cnt.most_common():
    print(f"  {k}: {v}")
print("出力:", out)
