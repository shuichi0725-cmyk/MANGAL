"""巻抜け(647) 是正: 欠番巻を楽天candidateから種4(volumes-supplement.yml)へ補完。

★安全な紐付け (= 慎重):
- ページの series_key は **既存巻ISBN → db-v2(volumes→editions→series)** で逆引き(題でなくISBN実体)。
  → 同名異作への誤紐付けを封鎖。anchorできない(全ISBN null)ページはskip。
- candidate = 楽天index((bases×vol))。版整合: ページ標準版の主publisher(ISBN登録者prefix)に
  一致する candidate を優先(文庫巻を標準列に混ぜない)。最古printing採用。
- ★既存検証: candidate ISBN が db-v2 / manga.v2 に既存なら skip。 巻番号が db-v2標準版に既存なら skip
  (= 真の欠番のみ)。promote側も種2優先で二重防止(self-retire)。
- 純粋追加・可逆(changelog)。種2不変。

usage:
  python _apply-volume-gaps.py            # dry-run
  python _apply-volume-gaps.py --apply
"""
import sys, os, csv, pickle, json, sqlite3, yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _rakuten_match_lib as L
ROOT = L.ROOT
APPLY = "--apply" in sys.argv
AT = "2026-06-27"
DB = f"{ROOT}/.cache/db-v2.sqlite"
SUPP = f"{ROOT}/data/seeds/volumes-supplement.yml"
CHANGELOG = f"{ROOT}/data/seeds/volume-gaps-changelog.jsonl"


def norm_isbn(s):
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def main():
    bundle = pickle.load(open(f"{ROOT}/.cache/rakuten-focus-index.pkl", "rb"))
    index = bundle["index"]; s2b = bundle["slug_to_bases"]
    con = sqlite3.connect(DB)
    cur = con.cursor()

    # isbn13 -> (series_id, series_key) 逆引き
    print("db-v2 isbn→series 逆引き構築中...", flush=True)
    isbn_to_series = {}
    for isbn, skey in cur.execute(
        "SELECT v.isbn13, s.series_key FROM volumes v "
        "JOIN editions e ON e.id=v.edition_id JOIN series s ON s.id=e.series_id "
        "WHERE v.isbn13 IS NOT NULL"):
        isbn_to_series[norm_isbn(isbn)] = skey
    # series_key -> set(既存 標準版 巻番号) と 全ISBN(prefix用)
    print(f"  {len(isbn_to_series):,} ISBN", flush=True)

    def std_numbers(skeys):
        nums = set()
        for sk in skeys:
            for (n,) in cur.execute(
                "SELECT v.number FROM volumes v JOIN editions e ON e.id=v.edition_id "
                "JOIN series s ON s.id=e.series_id WHERE s.series_key=? AND e.type='standard' AND v.number IS NOT NULL", (sk,)):
                if n: nums.add(int(n))
        return nums

    gaps = list(csv.DictReader(open(f"{ROOT}/docs/volume-gaps.tsv", encoding="utf-8"), delimiter="\t"))
    entries = []          # 種4 entry dicts
    changelog = []
    st = {"slug_anchored": 0, "slug_no_anchor": 0, "vol_added": 0, "vol_no_cand": 0,
          "vol_already_db": 0, "vol_isbn_dup": 0, "vol_date_conflict": 0}

    for g in gaps:
        sl = g["slug"]
        miss = [int(x) for x in g["missing"].split(",") if x.strip().isdigit()]
        p = f"{ROOT}/data/manga.v2/{sl}.yml"
        if not os.path.exists(p):
            continue
        d = yaml.safe_load(open(p, encoding="utf-8"))
        if not d:
            continue
        ed = next((e for e in (d.get("editions") or []) if e.get("type") == "standard"), None)
        if not ed:
            continue
        # anchor: 既存標準版ISBN → series_key 集合
        page_isbns = set()
        for v in (ed.get("volumes") or []):
            if v.get("isbn13"):
                page_isbns.add(norm_isbn(v["isbn13"]))
        skeys = set()
        for ib in page_isbns:
            sk = isbn_to_series.get(ib)
            if sk: skeys.add(sk)
        if not skeys:
            st["slug_no_anchor"] += 1
            continue
        st["slug_anchored"] += 1
        # ページ標準版の publisher prefix 多数派 (ISBN先頭7桁)
        pref_freq = {}
        for ib in page_isbns:
            pref_freq[ib[:7]] = pref_freq.get(ib[:7], 0) + 1
        db_nums = std_numbers(skeys)
        all_page_isbns = set()
        for e in (d.get("editions") or []):
            for v in (e.get("volumes") or []):
                if v.get("isbn13"): all_page_isbns.add(norm_isbn(v["isbn13"]))
        bases = s2b.get(sl, {L.norm(d.get("title"))})
        # 既存標準版 number -> date(present neighbors の整合性guard用)
        present_dates = {}
        for v in (ed.get("volumes") or []):
            if v.get("number") and v.get("release_date"):
                t = L.parse_prod_date(v["release_date"])
                if t: present_dates[int(v["number"])] = t

        def neighbor_ok(vnum, cand_t):
            if cand_t is None:
                return True  # 日付不明は番号のみ補完(順序判定不可→許容)
            # 直近の present 前巻・後巻と矛盾しないか
            prev = max((n for n in present_dates if n < vnum), default=None)
            nxt = min((n for n in present_dates if n > vnum), default=None)
            if prev is not None and cand_t < present_dates[prev]:
                return False
            if nxt is not None and cand_t > present_dates[nxt]:
                return False
            return True

        for vnum in miss:
            if vnum in db_nums:
                st["vol_already_db"] += 1
                continue  # db-v2標準版に既存=真の欠番でない
            cands = []
            for b in bases:
                cands += index.get((b, vnum), [])
            cands = [c for c in cands if c["isbn"]]
            # 既存ISBN(db/page)除外
            cands = [c for c in cands if norm_isbn(c["isbn"]) not in isbn_to_series and norm_isbn(c["isbn"]) not in all_page_isbns]
            if not cands:
                if not [c for b in bases for c in index.get((b, vnum), [])]:
                    st["vol_no_cand"] += 1
                else:
                    st["vol_isbn_dup"] += 1
                continue
            # 版整合: ページ主prefix一致を優先、その中で最古
            def rank(c):
                pref_match = 0 if c["isbn"][:7] in pref_freq else 1
                return (pref_match, c["date"] or (9999, 0, 0))
            best = min(cands, key=rank)
            if not neighbor_ok(vnum, best["date"]):
                st["vol_date_conflict"] += 1
                continue  # 前後present巻と日付矛盾=版混在/再版疑い→skip(慎重)
            st["vol_added"] += 1
            entries.append({
                "series_keys": sorted(skeys), "number": vnum,
                "isbn13": best["isbn"], "release_date": L.date_str(best["date"], day=True) or None,
                "publisher": best["publisher"] or None, "edition_type": "standard",
                "title_display": best["raw"], "source": "rakuten",
                "added_at": AT,
                "note": f"楽天harvest照合(slug={sl}・残差題完全一致・主版整合)。MADB欠番補完。",
            })
            changelog.append({"slug": sl, "vol": vnum, "op": "seed4_gap_fill",
                              "isbn13": best["isbn"], "series_keys": sorted(skeys),
                              "release_date": L.date_str(best["date"], day=True), "at": AT, "reversible": True})

    print(f"\n{'APPLY' if APPLY else 'DRY-RUN'}:")
    print(f"  anchor成功slug {st['slug_anchored']} / anchor不可(全ISBN null)skip {st['slug_no_anchor']}")
    print(f"  種4追加巻 {st['vol_added']}")
    print(f"  skip: db既存{st['vol_already_db']} / cand無{st['vol_no_cand']} / ISBN重複{st['vol_isbn_dup']} / 日付矛盾{st['vol_date_conflict']}")
    print("\n=== 追加サンプル(先頭15) ===")
    for e in entries[:15]:
        print(f"  v{e['number']:>3} {e['isbn13']} {e['release_date'] or '----':>10} keys={e['series_keys'][:1]} | {e['title_display'][:28]}")

    if not APPLY:
        print("\n(dry-run。 --apply で volumes-supplement.yml へ純粋追加)")
        return

    # 純粋追加(textual append): 既存entryは触らず、新entryブロックを末尾の volumes list に追記。
    import shutil
    before = len((yaml.safe_load(open(SUPP, encoding="utf-8")) or {}).get("volumes") or [])
    shutil.copy2(SUPP, f"{ROOT}/.cache/volumes-supplement-bak-{AT}.yml")
    # yaml.safe_dump(list) は既存と同じ「- series_keys:\n  - key\n  number: ...」形式を出力
    block = yaml.safe_dump(entries, allow_unicode=True, sort_keys=False, default_flow_style=False, width=100000)
    raw = open(SUPP, "rb").read()
    nl = b"\r\n" if b"\r\n" in raw[-200:] else b"\n"
    text = raw.decode("utf-8")
    if not text.endswith("\n"):
        text += "\n"
    # CRLF統一で追記
    append = block.replace("\r\n", "\n")
    text = text.replace("\r\n", "\n") + append
    if nl == b"\r\n":
        text = text.replace("\n", "\r\n")
    with open(SUPP, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    # 検証: yaml再ロードできるか + 件数
    chk = yaml.safe_load(open(SUPP, encoding="utf-8"))
    after = len(chk.get("volumes") or [])
    with open(CHANGELOG, "a", encoding="utf-8") as f:
        for ln in changelog:
            f.write(json.dumps(ln, ensure_ascii=False) + "\n")
    print(f"\n適用: 種4 {before} -> {after} (+{after-before}) / changelog +{len(changelog)} / backup .cache/volumes-supplement-bak-{AT}.yml")
    if after - before != len(entries):
        print(f"  ⚠ 追加数不一致 expected +{len(entries)} got +{after-before} (要確認)")


if __name__ == "__main__":
    main()
