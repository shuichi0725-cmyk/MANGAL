"""月次蒸留: 増分マージ (= 安全な純粋追加。 全再構築でなく「新規分だけ」db-v2へ)。

設計 (= [[feedback_dont_repeat_regrouping_error]] 厳守):
- 入力 = temp db (= 新tagのcm101を _build-series-v2 + _populate-v2 で 権威的にclusterした完全版)。
  ★clustering は既存と同一スクリプトなので series_key は決定論的に一致 (= 私の再解釈ゼロ)。
- 現db-v2 と temp を series_key で突合:
  A. temp に在り db-v2 に無い series_key = 新作 → series/editions/volumes/series_authors を copy。
  B. 既存 series_key = 新ISBN巻のみ append (継続刊)。 既存行は一切触らない。
- ★guard: ISBN または madb_book_id が既に db-v2 在 → skip (二重防止)。
- temp は db-v2 の copy 由来なので mangaka_id 一致 → series_authors はそのまま copy 可。
- 既存の cover_url / release_date override / enrichment は db-v2 側を保持 (temp から上書きしない)。
- backup + dry-run + reversible (= 挿入 series_id を manifest 記録)。

usage:
  python _distill-incremental-merge.py <temp_db> [--apply]
"""
import sys, os, sqlite3, shutil, json, importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 旧PCパス→動的導出(2026-07-21一括是正)
APPLY = "--apply" in sys.argv
AT = "2026-07-24"
args = [a for a in sys.argv[1:] if not a.startswith("--")]
TEMP_DB = args[0] if args else f"{ROOT}/.cache/db-v2-1217-temp.sqlite"
REAL_DB = f"{ROOT}/.cache/db-v2.sqlite"
MANIFEST = f"{ROOT}/.cache/madb-distill/merge-manifest-1.2.18.json"


def _load(modname, path):
    spec = importlib.util.spec_from_file_location(modname, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


pop = _load("pop_v2", f"{ROOT}/scripts/_populate-v2.py")
norm_imprint = pop.normalize_imprint


def edition_key(typ, imprint):
    return (typ, norm_imprint(imprint or "") or "")


def main():
    if not os.path.exists(TEMP_DB):
        print(f"✗ temp db 無: {TEMP_DB}"); sys.exit(1)
    if APPLY:
        bak = f"{REAL_DB}.bak-distill-{AT}"
        shutil.copy2(REAL_DB, bak)
        print(f"backup: {bak}", flush=True)
    real = sqlite3.connect(REAL_DB); real.row_factory = sqlite3.Row
    temp = sqlite3.connect(TEMP_DB); temp.row_factory = sqlite3.Row
    rc = real.cursor()

    # --- 現db-v2 の既存indexを構築 ---
    existing_keys = {r["series_key"]: r["id"] for r in real.execute("SELECT id, series_key FROM series")}
    existing_isbns = {r[0] for r in real.execute("SELECT isbn13 FROM volumes WHERE isbn13 IS NOT NULL")}
    existing_madb = {r[0] for r in real.execute("SELECT madb_book_id FROM volumes WHERE madb_book_id IS NOT NULL")}
    # 既存series の edition map: series_id -> {(type,norm_imprint): edition_id}
    real_eds = {}
    for r in real.execute("SELECT id, series_id, type, imprint FROM editions"):
        real_eds.setdefault(r["series_id"], {})[edition_key(r["type"], r["imprint"])] = r["id"]
    print(f"現db-v2: series {len(existing_keys):,} / ISBN {len(existing_isbns):,} / madb_book {len(existing_madb):,}", flush=True)

    st = {"new_series": 0, "append_series": 0, "ed_new": 0, "vol_new_series": 0,
          "vol_append": 0, "skip_isbn_dup": 0, "skip_madb_dup": 0, "skip_no_change_series": 0}
    new_series_ids = []     # reversibility manifest
    appended_vol_ids = []

    # temp の series を 走査
    temp_series = list(temp.execute("SELECT * FROM series"))
    for ts in temp_series:
        sk = ts["series_key"]
        tsid = ts["id"]
        # temp 側 volumes(該当series) を edition付きで取得し、新規ISBN/madbのみ抽出
        tvols = list(temp.execute(
            "SELECT v.*, e.type AS etype, e.label AS elabel, e.imprint AS eimprint "
            "FROM volumes v JOIN editions e ON e.id=v.edition_id WHERE e.series_id=?", (tsid,)))
        # 新規候補 = ISBN/madb_book が現db-v2に無いもの
        fresh = []
        for v in tvols:
            ib = v["isbn13"]
            mb = v["madb_book_id"]
            if ib and ib in existing_isbns:
                st["skip_isbn_dup"] += 1; continue
            if mb and mb in existing_madb:
                st["skip_madb_dup"] += 1; continue
            fresh.append(v)

        if sk in existing_keys:
            # B. 既存series = 新ISBN巻のみ append
            if not fresh:
                st["skip_no_change_series"] += 1; continue
            real_sid = existing_keys[sk]
            st["append_series"] += 1
            edmap = real_eds.setdefault(real_sid, {})
            for v in fresh:
                ek = edition_key(v["etype"], v["eimprint"])
                eid = edmap.get(ek)
                if eid is None:
                    if APPLY:
                        rc.execute("INSERT INTO editions (series_id,type,label,imprint) VALUES (?,?,?,?)",
                                   (real_sid, v["etype"], v["elabel"], v["eimprint"]))
                        eid = rc.lastrowid
                    else:
                        eid = -1
                    edmap[ek] = eid; st["ed_new"] += 1
                if APPLY:
                    rc.execute(
                        "INSERT INTO volumes (edition_id,madb_book_id,isbn13,number,volume_label,is_extra,release_date) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (eid, v["madb_book_id"], v["isbn13"], v["number"], v["volume_label"], v["is_extra"], v["release_date"]))
                    appended_vol_ids.append(rc.lastrowid)
                if v["isbn13"]: existing_isbns.add(v["isbn13"])
                if v["madb_book_id"]: existing_madb.add(v["madb_book_id"])
                st["vol_append"] += 1
        else:
            # A. 新series = series + series_authors + editions + volumes を copy
            if not fresh:
                # ISBN全部既存(別cluster在)=実質新規でない → skip(過剰新規回避)
                st["skip_no_change_series"] += 1; continue
            st["new_series"] += 1
            if APPLY:
                rc.execute(
                    "INSERT INTO series (series_key,qid,source,title,subtitle,title_kana,subtitle_kana,"
                    "title_official_en,adult_score) VALUES (?,?,?,?,?,?,?,?,?)",
                    (ts["series_key"], ts["qid"], ts["source"], ts["title"], ts["subtitle"],
                     ts["title_kana"], ts["subtitle_kana"], ts["title_official_en"], ts["adult_score"]))
                real_sid = rc.lastrowid
                new_series_ids.append(real_sid)
                # series_authors (temp=realのcopy由来でmangaka_id一致)
                for sa in temp.execute("SELECT mangaka_id, role FROM series_authors WHERE series_id=?", (tsid,)):
                    rc.execute("INSERT OR IGNORE INTO series_authors (series_id,mangaka_id,role) VALUES (?,?,?)",
                               (real_sid, sa["mangaka_id"], sa["role"]))
            else:
                real_sid = -1
            existing_keys[sk] = real_sid
            edmap = {}
            for v in fresh:
                ek = edition_key(v["etype"], v["eimprint"])
                eid = edmap.get(ek)
                if eid is None:
                    if APPLY:
                        rc.execute("INSERT INTO editions (series_id,type,label,imprint) VALUES (?,?,?,?)",
                                   (real_sid, v["etype"], v["elabel"], v["eimprint"]))
                        eid = rc.lastrowid
                    else:
                        eid = -1
                    edmap[ek] = eid; st["ed_new"] += 1
                if APPLY:
                    rc.execute(
                        "INSERT INTO volumes (edition_id,madb_book_id,isbn13,number,volume_label,is_extra,release_date) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (eid, v["madb_book_id"], v["isbn13"], v["number"], v["volume_label"], v["is_extra"], v["release_date"]))
                if v["isbn13"]: existing_isbns.add(v["isbn13"])
                if v["madb_book_id"]: existing_madb.add(v["madb_book_id"])
                st["vol_new_series"] += 1

    print(f"\n{'APPLY' if APPLY else 'DRY-RUN'} 結果:")
    print(f"  新series {st['new_series']:,} / 既存series追記 {st['append_series']:,}")
    print(f"  新volume(新series) {st['vol_new_series']:,} / 追記volume(既存series) {st['vol_append']:,}")
    print(f"  新edition {st['ed_new']:,}")
    print(f"  skip: ISBN既存 {st['skip_isbn_dup']:,} / madb既存 {st['skip_madb_dup']:,} / 変化なしseries {st['skip_no_change_series']:,}")
    total_new_vol = st["vol_new_series"] + st["vol_append"]
    print(f"  ★純増volume合計: {total_new_vol:,}")

    if APPLY:
        real.commit()
        json.dump({"new_series_ids": new_series_ids, "appended_vol_ids": appended_vol_ids,
                   "at": AT, "tag": "1.2.18", "stats": st},
                  open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"\n適用commit済 / manifest: {MANIFEST}")
    else:
        print("\n(dry-run。 --apply で db-v2 へ純粋追加 = backup後に実行)")
    real.close(); temp.close()


if __name__ == "__main__":
    main()
