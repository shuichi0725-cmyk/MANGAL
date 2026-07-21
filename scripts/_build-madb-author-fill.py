"""著者ゼロ series を MADB生記録から resolve_authors で再導出(役割付き)。

★key回収(原作/作画区別不可で原作者を主著者にする恐れ)を避け、 MADBの
dcterms:creator(安定C-id)+schema:creatorタグで役割付き解決(_madb_authors.resolve_authors)。
著者ゼロseriesの volume madb_book_id → cm101記録 → resolve → union。
出力: .cache/madb-author-fill-map.json = {series_key: {authors:[{name,role}], original_authors:[name]}}
※新形式(虚構推理vol23+)はタグ無→both writer_artist(名前は正しい、 役割はAniList補完が優先)。
"""
import sys, json, csv, sqlite3, importlib.util
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]  # 旧PCパス→動的導出(2026-07-21一括是正)
spec = importlib.util.spec_from_file_location("ma", ROOT / "scripts/_madb_authors.py")
ma = importlib.util.module_from_spec(spec); spec.loader.exec_module(ma)

# 解決器
agent = ma.load_agent_master(ROOT / ".cache/madb/metadata504.json")
mk = {}
for row in csv.DictReader((ROOT / "data/seed/mangaka.csv").open(encoding="utf-8")):
    mk[row["name"]] = row["qid"]
mk_norm = {}
for nm, q in mk.items():
    k = ma._norm_name(nm)
    if k and k not in mk_norm:
        mk_norm[k] = q
def n2q(nm):
    return mk.get(nm, "") if isinstance(nm, str) else "" or mk_norm.get(ma._norm_name(nm), "")

# 著者ゼロ series + その volume madb_book_id
con = sqlite3.connect(ROOT / ".cache/db-v2.sqlite"); con.text_factory = lambda b: b.decode("utf-8", "replace")
noauth_sids = [r[0] for r in con.execute(
    "SELECT s.id FROM series s LEFT JOIN series_authors sa ON sa.series_id=s.id WHERE sa.series_id IS NULL")]
key_of = {sid: k for sid, k in con.execute("SELECT id, series_key FROM series")}
sid_mids = defaultdict(set)
need = set()
for sid in noauth_sids:
    for (mb,) in con.execute("""SELECT v.madb_book_id FROM volumes v JOIN editions e ON e.id=v.edition_id
                                WHERE e.series_id=? AND v.madb_book_id IS NOT NULL""", (sid,)):
        sid_mids[sid].add(mb); need.add(mb)
con.close()
print(f"著者ゼロ series: {len(noauth_sids):,} / 必要な madb_book_id: {len(need):,}", file=sys.stderr)

# metadata101 から必要記録のみ抽出(M-id)
print("metadata101.json 読込中(660MB)...", file=sys.stderr)
rec_by_mid = {}
for r in json.load((ROOT / ".cache/madb/metadata101.json").open(encoding="utf-8")).get("@graph", []):
    mid = r.get("schema:identifier")
    if mid in need:
        rec_by_mid[mid] = r
print(f"  該当記録: {len(rec_by_mid):,}", file=sys.stderr)

out = {}; filled = 0
for sid, mids in sid_mids.items():
    all_au = []
    for mid in mids:
        rec = rec_by_mid.get(mid)
        if rec:
            all_au.extend(ma.resolve_authors(rec, agent, n2q))
    if not all_au:
        continue
    uni = ma.union_authors(all_au)
    authors = [{"name": a["name"], "role": a["role"]} for a in uni if a["role"] != "original_author"]
    originals = [a["name"] for a in uni if a["role"] == "original_author"]
    if authors or originals:
        out[key_of[sid]] = {"authors": authors, "original_authors": originals}
        filled += 1
OUT = ROOT / ".cache/madb-author-fill-map.json"
OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
print(f"★MADB再導出で著者回復: {filled:,} series / wrote {OUT}")
# 検証
print("\n=== 検証 ===")
con = sqlite3.connect(ROOT / ".cache/db-v2.sqlite"); con.text_factory = lambda b: b.decode("utf-8", "replace")
for t in ["虚構推理", "左ききのエレン", "六道の悪女(おんな)たち", "地雷震", "爆音列島"]:
    for (k,) in con.execute("SELECT series_key FROM series WHERE title=?", (t,)):
        if k in out:
            e = out[k]; au = "/".join(f"{a['name']}({a['role']})" for a in e["authors"])
            print(f"  {t}: 作画[{au}] 原作{e['original_authors']}")
            break
con.close()
