"""新 series-v2.json (= 104ベースのクリーンな role) を series_key で既存 db に map し、
series_authors.role を in-place upgrade する。

★ かなり慎重:
- role の **writer_artist → specific (artist/original_author) 昇格のみ** 適用 (退行ゼロ)。
- 既存著者の role 更新のみ。 **新規著者の追加はしない**(= 著者集合不変 → merge json 無影響、 sid 不変)。
- 104ベースなので volumes 由来のスピンオフ汚染がない (= 進撃 諫山 が writer_artist のまま正しい)。
- series_authors PK=(sid,mid,role) 対応 (既存なら冗長行 DELETE、 無ければ old 行 UPDATE)。
- default dry-run。 --apply で UPDATE。 db backup 前提。

使い方:
  python scripts/_apply-roles-from-build.py          # dry-run
  python scripts/_apply-roles-from-build.py --apply  # UPDATE
"""
from __future__ import annotations
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
SERIES_JSON = ROOT / ".cache" / "series-v2.json"
APPLY = "--apply" in sys.argv


def main():
    con = sqlite3.connect(DB)
    c = con.cursor()

    # --- 1. 新 json: series_key → {qid: role, normname: role} ---
    print("loading series-v2.json ...", file=sys.stderr)
    data = json.load(open(SERIES_JSON, encoding="utf-8"))
    clusters = data["clusters"]
    key_qid_role: dict[str, dict] = {}     # series_key → {qid: role}
    key_name_role: dict[str, dict] = {}    # series_key → {name: role}
    for cl in clusters:
        sk = cl["series_key"]
        qr = key_qid_role.setdefault(sk, {})
        nr = key_name_role.setdefault(sk, {})
        for a in cl.get("authors", []) or []:
            role = a.get("role")
            if a.get("qid"):
                qr[a["qid"]] = role
            if a.get("name"):
                nr[a["name"]] = role
    print(f"  clusters: {len(clusters):,}", file=sys.stderr)

    # --- 2. db: series_key→sid, mangaka id→(qid,name), series_authors ---
    sid_key = {sid: sk for sid, sk in c.execute("SELECT id, series_key FROM series")}
    mk = {mid: (q, nm) for mid, q, nm in c.execute("SELECT id, qid, name FROM mangaka")}
    sa = c.execute("SELECT series_id, mangaka_id, role FROM series_authors").fetchall()

    updates = []
    trans = defaultdict(int)
    n_nokey = n_noauthor = 0
    for sid, mid, old in sa:
        if old != "writer_artist":
            continue  # 昇格のみ = 既存 specific は触らない
        sk = sid_key.get(sid)
        if sk is None or sk not in key_qid_role:
            n_nokey += 1
            continue
        q, nm = mk.get(mid, (None, None))
        new = None
        if q and q in key_qid_role[sk]:
            new = key_qid_role[sk][q]
        elif nm and nm in key_name_role[sk]:
            new = key_name_role[sk][nm]
        if new is None:
            n_noauthor += 1
            continue
        if new in ("artist", "original_author") and new != old:
            updates.append((sid, mid, old, new))
            trans[(old, new)] += 1

    print(f"\n=== role upgrade (104ベース, dry-run) ===")
    print(f"  series_authors writer_artist 行で照合: 対象")
    print(f"  upgrade 件数: {len(updates):,}")
    for (o, n), cnt in sorted(trans.items(), key=lambda x: -x[1]):
        print(f"    {cnt:>7,}  {o} → {n}")

    # 検証: 半妖(直る) + 進撃/berserk/urusei(壊れない)
    print(f"\n  --- 検証 ---")
    checks = {"半妖の夜叉姫": None, "進撃の巨人": None, "ベルセルク_berserk": "Berserk", "うる星やつら": None}
    up_set = {(s, m): n for s, m, o, n in updates}
    for title in ["半妖の夜叉姫", "進撃の巨人", "うる星やつら"]:
        rows = c.execute("SELECT id FROM series WHERE title=? ORDER BY id LIMIT 1", (title,)).fetchall()
        if not rows:
            continue
        sid = rows[0][0]
        out = []
        for s2, mid, old in [r for r in sa if r[0] == sid]:
            nm = mk.get(mid, (None, None))[1]
            newr = up_set.get((sid, mid), old)
            out.append(f"{nm}:{old}→{newr}")
        print(f"    {title} (sid={sid}): {out}")

    if not APPLY:
        print(f"\n(--apply で UPDATE。 nokey={n_nokey:,} noauthor={n_noauthor:,})", file=sys.stderr)
        return

    print(f"\n[APPLY] {len(updates):,} 行処理 ...", file=sys.stderr)
    cur = con.cursor()
    n_upd = n_del = 0
    for sid, mid, old, new in updates:
        ex = cur.execute("SELECT 1 FROM series_authors WHERE series_id=? AND mangaka_id=? AND role=?",
                         (sid, mid, new)).fetchone()
        if ex:
            cur.execute("DELETE FROM series_authors WHERE series_id=? AND mangaka_id=? AND role=?",
                        (sid, mid, old)); n_del += 1
        else:
            cur.execute("UPDATE series_authors SET role=? WHERE series_id=? AND mangaka_id=? AND role=?",
                        (new, sid, mid, old)); n_upd += 1
    con.commit()
    print(f"[APPLY] done. updated={n_upd:,} / deleted_redundant={n_del:,}", file=sys.stderr)


if __name__ == "__main__":
    main()
