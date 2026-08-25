# -*- coding: utf-8 -*-
"""number=0 の1巻不可視化型の検出+安全スライス是正 (= 泣かせたくてどうしよう型 2026-08-26 型化)。

型: promote は「edition 内に numbered 巻が1つでもあれば number=0 巻を skip」する
(偽#1 dedup 弊害除去)。無番号で登録された**真の1巻**(0巻扱い)を持つ作品に後から
番号付き続巻が届くと、その瞬間 1巻が本番から消える(泣かせたくて=巻2到着で1巻消失)。

★機械信号は「0巻の release_date が同 edition の全 numbered 巻より古い」だけ
(is_extra は 99.95% が 1 で番外編と真の1巻を区別できない=実測)。

分類:
  ONPAGE        0巻ISBNが本番頁に載っている(既に見えている=対応不要)
  HIDDEN_FIX    頁在・0巻ISBN不在・頁にvol1無し = 是正候補(--applyの対象)
  HIDDEN_HASV1  頁在・0巻ISBN不在・頁にvol1有り = 別版/番外の可能性(報告のみ)
  NOISBN        0巻にISBNが無い(戦前〜80年代等。是正不能=報告のみ)
  NOPAGE        シリーズ自体が本番頁に無い(孤児series領域)

--apply: HIDDEN_FIX のうち**楽天題ゲート**(0巻ISBNの楽天題≒シリーズ題。副題付き=番外疑いはHOLD)
  を通った巻だけ、種4-auto(volumes-supplement-auto.yml)へ number=1 で純粋追加
  (source: vol0-first。nakasetakute-doushiyou で実証済みの型=種2の0巻はskipされたまま、
   種4の巻1が枠を埋める=二重表示なし)。適用後は表示された promote コマンドで頁再生成。

出力: docs/production-diagnostics/vol0-hidden-first.tsv
月次: 新規増加分(特に HIDDEN_FIX)を見る。

  python scripts/_audit-vol0-hidden-first.py            # 検出のみ
  python scripts/_audit-vol0-hidden-first.py --apply    # 安全スライスを種4-autoへ(楽天ゲート・~1.3s/req)
  python scripts/_audit-vol0-hidden-first.py --apply --limit 20
"""
import argparse
import datetime
import io
import json
import os
import re
import sqlite3
import sys

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, ".cache", "db-v2.sqlite")
PAGE_IDX = os.path.join(ROOT, ".cache", "isbn-page-index.json")
TITLE_MAP = os.path.join(ROOT, ".cache", "isbn-title-map.json")
SEED = os.path.join(ROOT, "data", "seeds", "volumes-supplement-auto.yml")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "vol0-hidden-first.tsv")
CHANGELOG = os.path.join(ROOT, "data", "seeds", "vol0-first-changelog.jsonl")

RE_STRIP = re.compile(r"[\s　・:：!！?？~〜\-‐−()（）\[\]【】「」『』<>《》.。,、&＆'’\"]+")
RE_VOLMARK = re.compile(r"([(（]?\s*[0-9０-９]+\s*[)）]?|第[0-9０-９]+巻|上|下)$")


def norm_title(s: str) -> str:
    s = str(s or "")
    s = RE_VOLMARK.sub("", s.strip())
    return RE_STRIP.sub("", s).lower()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    if not os.path.exists(PAGE_IDX):
        print(f"ABORT: {PAGE_IDX} が無い → python scripts/_exists.py --build")
        sys.exit(2)
    page_idx = json.load(io.open(PAGE_IDX, encoding="utf-8"))
    title_map = json.load(io.open(TITLE_MAP, encoding="utf-8")) if os.path.exists(TITLE_MAP) else {}

    def page_of(isbn):
        v = page_idx.get(isbn)
        if isinstance(v, list):
            return str(v[0]) if v else None
        return str(v) if v else None

    con = sqlite3.connect(DB)
    c = con.cursor()
    # 0巻+numbered同居 edition → 0巻が全numbered巻より古いもの
    rows = []
    cand_editions = c.execute(
            """SELECT DISTINCT e.id, e.series_id, e.type, e.imprint FROM editions e
               JOIN volumes v0 ON v0.edition_id=e.id AND v0.number=0
               JOIN volumes vn ON vn.edition_id=e.id AND vn.number>0""").fetchall()
    for eid, sid, etype, imp in cand_editions:
        vols = list(c.execute("SELECT number, isbn13, release_date FROM volumes WHERE edition_id=?", (eid,)))
        num_dates = [str(d) for n, i, d in vols if n and d]
        if not num_dates:
            continue
        dmin = min(num_dates)
        nums = sorted({n for n, i, d in vols if n})
        for n, ib, d in vols:
            if n == 0 and d and str(d) < dmin:
                rows.append((sid, eid, etype, imp or "", str(ib or ""), str(d), dmin, nums))

    # series題 + 頁照合
    s_title = {sid: t for sid, t in c.execute("SELECT id, title FROM series")}
    s_key = {sid: k for sid, k in c.execute("SELECT id, series_key FROM series")}

    page_vols_cache: dict = {}

    def page_volnums(slug):
        if slug not in page_vols_cache:
            p = os.path.join(ROOT, "data", "manga.v2", slug + ".yml")
            nums = set()
            if os.path.exists(p):
                try:
                    y = yaml.safe_load(io.open(p, encoding="utf-8"))
                    for ed in y.get("editions") or []:
                        for v in ed.get("volumes") or []:
                            nums.add(v.get("number"))
                except Exception:
                    pass
            page_vols_cache[slug] = nums
        return page_vols_cache[slug]

    out_rows = []
    fix_candidates = []
    for sid, eid, etype, imp, ib, d0, dmin, nums in rows:
        title = s_title.get(sid, "")
        # シリーズの他ISBNから頁を引く
        slug = page_of(ib) if ib else None
        cls = None
        if slug:
            cls = "ONPAGE"
        else:
            other = [r[0] for r in c.execute(
                "SELECT isbn13 FROM volumes v JOIN editions e ON v.edition_id=e.id "
                "WHERE e.series_id=? AND v.isbn13 IS NOT NULL", (sid,))]
            slug = next((page_of(str(x)) for x in other if page_of(str(x))), None)
            if not ib:
                cls = "NOISBN"
            elif not slug:
                cls = "NOPAGE"
            elif 1 in page_volnums(slug):
                cls = "HIDDEN_HASV1"
            else:
                cls = "HIDDEN_FIX"
                fix_candidates.append((sid, eid, title, ib, d0, slug, imp))
        out_rows.append((cls, title, str(sid), etype, imp, ib, d0, dmin,
                         ",".join(map(str, nums[:8])), slug or ""))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    order = {"HIDDEN_FIX": 0, "HIDDEN_HASV1": 1, "NOISBN": 2, "NOPAGE": 3, "ONPAGE": 4}
    with io.open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write("class\ttitle\tsid\tedition\timprint\tisbn0\tdate0\tmin_numbered\tnumbered\t頁\n")
        for r in sorted(out_rows, key=lambda r: (order.get(r[0], 9), r[1])):
            f.write("\t".join(r) + "\n")
    from collections import Counter
    cnt = Counter(r[0] for r in out_rows)
    print(f"0巻不可視化候補(0巻が最古): {len(out_rows)} 件 / " +
          " ".join(f"{k}={v}" for k, v in sorted(cnt.items(), key=lambda x: order.get(x[0], 9))))
    print(f"→ {os.path.relpath(OUT, ROOT)}")

    if not a.apply:
        if cnt.get("HIDDEN_FIX"):
            print(f"(--apply で HIDDEN_FIX {cnt['HIDDEN_FIX']} 件を楽天題ゲート→種4-auto純粋追加)")
        return

    # ===== --apply: 楽天題ゲート → 種4-auto 純粋追加 =====
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import importlib
    _LK = importlib.import_module("_lookup")
    env = {}
    for name in (".env.local", ".env"):
        p = os.path.join(ROOT, name)
        if os.path.exists(p):
            for ln in io.open(p, encoding="utf-8"):
                if "=" in ln and not ln.startswith("#"):
                    k, v = ln.split("=", 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")

    seed = yaml.safe_load(io.open(SEED, encoding="utf-8")) or {}
    seed_vols = seed.get("volumes") or []
    seed_isbns = {re.sub(r"[^0-9X]", "", str(v.get("isbn13") or "").upper()) for v in seed_vols}
    today = datetime.date.today().isoformat()
    applied, hold = [], []
    todo = fix_candidates[: a.limit] if a.limit else fix_candidates
    import time
    for i, (sid, eid, title, ib, d0, slug, imp) in enumerate(todo):
        if ib in seed_isbns:
            continue
        # 楽天題: cache → live
        rt = title_map.get(ib)
        if not rt:
            try:
                items = _LK.rakuten_live_retry(env, isbn=ib)
                time.sleep(1.3)
            except Exception:
                items = None
            for it in items or []:
                dd = it.get("Item") or it
                rt = dd.get("title")
                if rt:
                    break
        if not rt:
            hold.append((title, ib, "楽天題なし(NDL/人手裁定へ)"))
            continue
        nt, ns = norm_title(rt), norm_title(title)
        if not (nt and ns and (nt == ns or nt.startswith(ns) and len(nt) - len(ns) <= 2)):
            hold.append((title, ib, f"題不一致(番外疑い): 楽天『{rt[:40]}』"))
            continue
        entry = {
            "series_keys": [s_key.get(sid)],
            "number": 1,
            "isbn13": ib,
            "release_date": str(d0),
            "publisher": "",
            "edition_type": "standard",
            "title_display": str(rt)[:80],
            "source": "vol0-first",
            "added_at": today,
            "note": f"number=0の1巻が続巻到着で不可視化(泣かせたくて型)。0巻{d0}<最古numbered。楽天題一致ゲート通過→巻1として復元",
        }
        seed_vols.append(entry)
        seed_isbns.add(ib)
        applied.append((slug, title, ib))
        with io.open(CHANGELOG, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"slug": slug, "op": "vol0-first-restore", "isbn13": ib,
                                "title": title, "at": today}, ensure_ascii=False) + "\n")
        if (i + 1) % 25 == 0:
            print(f"  {i + 1}/{len(todo)} 適用{len(applied)} hold{len(hold)}", flush=True)

    if applied:
        seed["volumes"] = seed_vols
        txt = yaml.safe_dump(seed, allow_unicode=True, sort_keys=False, width=1000)
        assert len((yaml.safe_load(txt) or {}).get("volumes") or []) == len(seed_vols)
        io.open(SEED, "w", encoding="utf-8", newline="\n").write(txt)
    print(f"\n適用 {len(applied)} / HOLD {len(hold)} (overwrites 0 = 純粋追加のみ)")
    for t, ib, why in hold[:20]:
        print(f"  HOLD {ib} {t[:30]}: {why}")
    if applied:
        slugs = sorted({s for s, _, _ in applied})
        lp = os.path.join(ROOT, ".cache", "vol0-first-pages.txt")
        io.open(lp, "w", encoding="utf-8", newline="\n").write("\n".join(slugs))
        print(f"→ 再生成: python scripts/_promote-bulk-v2.py --only-file {lp}  ({len(slugs)} 頁)")


if __name__ == "__main__":
    main()
