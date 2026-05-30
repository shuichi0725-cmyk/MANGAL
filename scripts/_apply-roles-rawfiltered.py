"""著者ロール忠実化 (raw101 + 汚染フィルタ版) = 半妖クラス(orphan/104無し)も救済。

★ さらに慎重:
- 生 metadata101.json (= 役割タグ有り) を使うが、 **スピンオフ汚染を除去**:
  各 series の volume record のうち、 **登場著者が全員その series の確定著者集合
  (series_authors の mangaka 名) に収まる record のみ採用**。
  → 進撃 sid に紛れた `[原作]諫山+[漫画]士貴(別作品)` は 士貴 が確定集合外 → 除外。
     半妖は全 record が {高橋,椎名} → 採用 → 役割タグ取得。
- role の writer_artist → specific 昇格のみ。 既存 specific は不変 (退行ゼロ)。
- 著者の追加/削除なし (著者集合不変 → merge json 無影響、 sid 不変)。
- _MERGE_PRI で specific 優先 (= 巻間タグムラで writer_artist に潰さない)。
- default dry-run。 --apply で UPDATE。 db backup 前提。
"""
from __future__ import annotations
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _madb_authors import parse_role_text, original_work_names, _classify_tag, _norm_name

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
META101 = ROOT / ".cache" / "madb" / "metadata101.json"   # 生 (タグ有り)
APPLY = "--apply" in sys.argv


def main():
    con = sqlite3.connect(DB)
    c = con.cursor()

    print("loading raw metadata101 ...", file=sys.stderr)
    bookrec = {}
    for b in json.load(open(META101, encoding="utf-8"))["@graph"]:
        mid = b.get("schema:identifier", "")
        if mid:
            bookrec[mid] = (b.get("schema:creator", ""), b.get("ma:originalWorkCreator"))
    print(f"  books: {len(bookrec):,}", file=sys.stderr)

    sid_books = defaultdict(list)
    for sid, mb in c.execute(
        "SELECT e.series_id, v.madb_book_id FROM volumes v JOIN editions e ON e.id=v.edition_id "
        "WHERE v.madb_book_id IS NOT NULL"
    ):
        sid_books[sid].append(mb)
    mname = {mid: nm for mid, nm in c.execute("SELECT id, name FROM mangaka")}
    sa = c.execute("SELECT series_id, mangaka_id, role FROM series_authors").fetchall()
    sa_by_sid = defaultdict(list)
    for sid, mid, role in sa:
        sa_by_sid[sid].append((mid, role))

    def derive_for_series(sid):
        """確定著者集合に収まる record のみから {established_norm_name: 役割class集合} 等を作る。"""
        established = {_norm_name(mname.get(mid, "")) for mid, _ in sa_by_sid[sid]}
        established.discard("")
        name_classes: dict[str, set] = defaultdict(set)
        owc: set = set()
        used = 0
        for mb in sid_books.get(sid, []):
            rec = bookrec.get(mb)
            if not rec:
                continue
            cr, owc_field = rec
            nr = parse_role_text(cr)  # {norm_name: tag}
            names = set(nr.keys())
            if not names:
                continue
            # ★ 汚染フィルタ: record の著者が全員 確定集合に収まる場合のみ採用
            if not names <= established:
                continue
            used += 1
            owc |= (original_work_names(owc_field) & established)
            for nm, tag in nr.items():
                name_classes[nm].add(_classify_tag(tag))
        has_artist = any("artist" in cs for cs in name_classes.values())
        return name_classes, owc, has_artist, used

    def role_of(classes, is_owc, has_artist):
        if "artist" in classes:
            return "artist"
        if is_owc or "story" in classes:
            return "original_author" if has_artist else "writer_artist"
        if "plain" in classes:
            return "original_author" if has_artist else "writer_artist"
        return None  # editorial のみ等 = 据え置き

    cache = {}
    updates = []
    trans = defaultdict(int)
    for sid, mid, old in sa:
        if old != "writer_artist":
            continue
        if sid not in cache:
            cache[sid] = derive_for_series(sid)
        name_classes, owc, has_artist, used = cache[sid]
        nm = _norm_name(mname.get(mid, ""))
        if nm not in name_classes:
            continue
        new = role_of(name_classes[nm], nm in owc, has_artist)
        if new in ("artist", "original_author"):
            updates.append((sid, mid, old, new))
            trans[(old, new)] += 1

    print(f"\n=== raw101+汚染フィルタ role upgrade (dry-run) ===")
    print(f"  upgrade 件数: {len(updates):,}")
    for (o, n), cnt in sorted(trans.items(), key=lambda x: -x[1]):
        print(f"    {cnt:>7,}  {o} → {n}")

    print(f"\n  --- 検証 ---")
    up = {(s, m): n for s, m, o, n in updates}
    for title in ["半妖の夜叉姫", "進撃の巨人", "うる星やつら", "ベルセルク"]:
        r = c.execute("SELECT id FROM series WHERE title=? ORDER BY id LIMIT 1", (title,)).fetchone()
        if not r:
            continue
        sid = r[0]
        out = [f"{mname.get(mid)}:{old}→{up.get((sid, mid), old)}" for mid, old in sa_by_sid[sid]]
        print(f"    {title}(sid={sid}): {out}")

    # 既知 原作付き / 単独 の検証
    print(f"\n  --- 既知作品 検証 ---")
    for title in ["DEATH NOTE", "美味しんぼ", "ゼロ", "鋼の錬金術師", "名探偵コナン", "ドラゴンボール"]:
        r = c.execute("SELECT id FROM series WHERE title=? ORDER BY id LIMIT 1", (title,)).fetchone()
        if not r:
            continue
        sid = r[0]
        out = [f"{mname.get(mid)}:{old}→{up.get((sid, mid), old)}" for mid, old in sa_by_sid[sid]]
        print(f"    {title}: {out}")

    if not APPLY:
        print(f"\n  --- → original_author サンプル 15 ---")
        for sid, mid, old, new in [u for u in updates if u[3] == "original_author"][:15]:
            print(f"    sid={sid} {mname.get(mid)} → original_author")
        print(f"\n(--apply で UPDATE)", file=sys.stderr)
        return

    print(f"\n[APPLY] {len(updates):,} 行 ...", file=sys.stderr)
    cur = con.cursor()
    nu = nd = 0
    for sid, mid, old, new in updates:
        ex = cur.execute("SELECT 1 FROM series_authors WHERE series_id=? AND mangaka_id=? AND role=?",
                         (sid, mid, new)).fetchone()
        if ex:
            cur.execute("DELETE FROM series_authors WHERE series_id=? AND mangaka_id=? AND role=?",
                        (sid, mid, old)); nd += 1
        else:
            cur.execute("UPDATE series_authors SET role=? WHERE series_id=? AND mangaka_id=? AND role=?",
                        (new, sid, mid, old)); nu += 1
    con.commit()
    print(f"[APPLY] done. updated={nu:,} / deleted_redundant={nd:,}", file=sys.stderr)


if __name__ == "__main__":
    main()
