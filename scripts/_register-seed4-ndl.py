"""NDL 確認済ドラフト (.cache/seed4-drafts.yml) を 種4 auto ファイルに登録 + 未確認分を追跡。

★ 慎重設計:
- 手動キュレーションの data/seeds/volumes-supplement.yml は **不変**。
  自動分は別ファイル data/seeds/volumes-supplement-auto.yml に書く (= promote/audit が両方 load)。
- 登録前に validate: series_keys が db に bind するか / 巻番号が既存でないか。
  bind不可 or 重複 は skip して pending に回す。
- ISBN-10 → ISBN-13 変換、 発売日を YYYY-MM 正規化。
- 「取り込めなかった物」= NDL未確認(progress の miss) + validate失敗 を
  data/seeds/volumes-pending.yml に追跡記録 (将来 NDL更新/別ソースで再訪用)。

★★ merge書き込み (2026-08-26 全消し事故の恒久修正):
  volumes-supplement-auto.yml は 2026-07 以降、日次蒸留(zokkan)/巻抜けfill が純粋追加する
  **蓄積台帳**に転用された(source: rakuten-preorder/rakuten-local/rakuten-live 等)。
  旧実装は自分の出力だけで全文上書きし、2026-08-21 の月次蒸留(intake.py --run の seed4 stage)で
  staleドラフト0件 → volumes: [] を書き 916巻を全消し(種2未収録883巻が本番から消失)。
  現実装: 既存を読み source != 'ndl-auto' の entry を全部保存 + ndl-auto 分だけ差し替え。
  既存が読めない時は abort(壊れたparseで全消ししない)。書込前に .cache へバックアップ。

入力: .cache/seed4-drafts.yml (hit) + .cache/seed4-progress.jsonl (miss)
出力: data/seeds/volumes-supplement-auto.yml (merge) / data/seeds/volumes-pending.yml
"""
from __future__ import annotations
import json
import re
import sqlite3
import sys
from pathlib import Path
import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"
DRAFTS = ROOT / ".cache" / "seed4-drafts.yml"
PROGRESS = ROOT / ".cache" / "seed4-progress.jsonl"
OUT_AUTO = ROOT / "data" / "seeds" / "volumes-supplement-auto.yml"
OUT_PENDING = ROOT / "data" / "seeds" / "volumes-pending.yml"
APPLY = "--apply" in sys.argv
ADDED = "2026-05-30"


def isbn13(s: str) -> str:
    s = re.sub(r"[^0-9Xx]", "", str(s or ""))
    if len(s) == 13:
        return s
    if len(s) == 10:
        core = "978" + s[:9]
        tot = sum((1 if i % 2 == 0 else 3) * int(d) for i, d in enumerate(core))
        return core + str((10 - tot % 10) % 10)
    return s


def fmt_date(s: str) -> str:
    s = str(s or "").strip()
    m = re.match(r"(\d{4})[.\-/](\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    m = re.match(r"(\d{4})(\d{2})$", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.match(r"(\d{4})", s)
    return m.group(1) if m else s


def main():
    con = sqlite3.connect(DB)
    c = con.cursor()
    drafts = yaml.safe_load(open(DRAFTS, encoding="utf-8")) or []

    def sids_for(keys):
        s = set()
        for k in keys or []:
            for r in c.execute("SELECT id FROM series WHERE series_key=?", (k,)):
                s.add(r[0])
        return s

    def isbn_norm(s):
        return re.sub(r"[^0-9X]", "", str(s or "").upper())

    # ★ 種2(db)の全 ISBN (= 既存ISBN なら別クラスタに実在 = 取込もれでない、 除外)
    db_isbns = {isbn_norm(r[0]) for r in
                c.execute("SELECT isbn13 FROM volumes WHERE isbn13 IS NOT NULL")}

    entries = []
    pending = []
    n_ok = n_bind = n_dup = n_exist = 0
    for d in drafts:
        keys = d.get("series_keys") or []
        num = d["number"]
        ib = isbn13(d.get("isbn13"))
        # ★ ISBN が既に種2にある = 別クラスタに実在(表記揺れ/未統合) → 取込もれでない
        if isbn_norm(ib) in db_isbns:
            n_exist += 1
            pending.append({"title": d["title"], "number": num, "isbn13": ib,
                            "reason": "種2に既存ISBN(別クラスタ=未統合/表記揺れ、 取込もれでない)",
                            "source": "ndl"})
            continue
        sids = sids_for(keys)
        if not sids:
            n_bind += 1
            pending.append({"title": d["title"], "number": num, "isbn13": isbn13(d.get("isbn13")),
                            "reason": "series_keys bind不可", "source": "ndl"})
            continue
        # 巻番号 既存チェック
        exists = any(c.execute("SELECT 1 FROM volumes v JOIN editions e ON e.id=v.edition_id "
                               "WHERE e.series_id=? AND v.number=?", (sid, num)).fetchone()
                     for sid in sids)
        if exists:
            n_dup += 1
            pending.append({"title": d["title"], "number": num, "isbn13": isbn13(d.get("isbn13")),
                            "reason": "巻番号が既存(重複)", "source": "ndl"})
            continue
        n_ok += 1
        entries.append({
            "series_keys": keys,
            "qid": None,
            "number": num,
            "isbn13": isbn13(d.get("isbn13")),
            "release_date": fmt_date(d.get("issued")),
            "pages": d.get("pages"),
            "publisher": d.get("publisher") or "",
            "edition_type": "standard",
            "title_display": d.get("ndl_title") or d["title"],
            "source": "ndl-auto",
            "added_at": ADDED,
            "note": f"MADB取込もれ。NDL Search で確認 (ISBN/巻/発売日)。自動登録 (_register-seed4-ndl.py)。",
        })

    # 未確認 (NDL miss) を pending に
    n_miss = 0
    if PROGRESS.exists():
        for line in PROGRESS.open(encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("status") == "miss":
                n_miss += 1
                pending.append({"title": r["title"], "number": r["number"],
                                "reason": "NDL未確認 (実在不明/取込もれ候補)", "source": "ndl-miss"})

    print(f"=== 種4 NDL登録 ===", file=sys.stderr)
    print(f"  ドラフト {len(drafts)} / 登録OK {n_ok} / 種2に既存ISBN {n_exist} / bind不可 {n_bind} / 重複 {n_dup}", file=sys.stderr)
    print(f"  pending (NDL miss {n_miss} + 種2既存 {n_exist} + bind/重複 {n_bind + n_dup}) = {len(pending)}", file=sys.stderr)

    if not APPLY:
        print("\n(--apply で書き込み)", file=sys.stderr)
        return

    # ★★ merge: 既存の非 ndl-auto entry(日次zokkan/巻抜けfillの蓄積台帳)は必ず保存する。
    #   全消し事故(2026-08-21, 916巻)の恒久修正。既存が読めない時は上書きせず abort。
    preserved = []
    n_prev_total = n_prev_ndl = 0
    if OUT_AUTO.exists():
        try:
            prev = yaml.safe_load(OUT_AUTO.read_text(encoding="utf-8")) or {}
            prev_vols = prev.get("volumes") or []
        except Exception as e:
            print(f"\n★abort: 既存 {OUT_AUTO.name} が parse できない ({e})。"
                  f"壊れたまま上書き=全消しになるので書き込まない。先にファイルを直すこと。", file=sys.stderr)
            sys.exit(1)
        n_prev_total = len(prev_vols)
        prev_ndl = []
        for v in prev_vols:
            if (v or {}).get("source") == "ndl-auto":
                n_prev_ndl += 1
                prev_ndl.append(v)
            else:
                preserved.append(v)
        # ★安全弁: 新 ndl-auto が0件(=staleドラフト/空cache)の時は旧 ndl-auto を消さず保持。
        #   「登録するものが無い」と「全部退役」は別物=空入力で削らない。
        if not entries and prev_ndl:
            print(f"  新ndl-auto 0件 → 旧ndl-auto {n_prev_ndl} 件を保持(空入力で削らない)", file=sys.stderr)
            preserved += prev_ndl
            n_prev_ndl = 0
    # 保存分と新 ndl-auto の ISBN 重複は保存分(蓄積台帳)を優先
    kept_isbns = {isbn_norm(v.get("isbn13")) for v in preserved if v.get("isbn13")}
    entries = [e for e in entries if isbn_norm(e.get("isbn13")) not in kept_isbns]
    merged = preserved + entries
    # 縮小ガード: 保存対象(非ndl-auto)が1件でも落ちる書き込みは構造上あり得ない=起きたらバグ。
    if len(preserved) != n_prev_total - n_prev_ndl or len(merged) < len(preserved):
        print(f"\n★abort: merge結果が不整合 (既存{n_prev_total}=非ndl{n_prev_total - n_prev_ndl}+ndl{n_prev_ndl} "
              f"/ 保存{len(preserved)} / merge後{len(merged)})。書き込まない。", file=sys.stderr)
        sys.exit(1)
    # 書込前バックアップ (可逆)
    if OUT_AUTO.exists():
        import datetime as _dt
        import shutil as _sh
        bak = ROOT / ".cache" / f"volumes-supplement-auto.yml.bak-{_dt.datetime.now():%Y%m%d-%H%M%S}"
        _sh.copyfile(OUT_AUTO, bak)
        print(f"  backup: {bak}", file=sys.stderr)

    out_text = (
        "# 種4 auto = MADB取込もれ巻の**蓄積台帳** (日次zokkan/巻抜けfill/NDL確認の合流先)。\n"
        "# 手動版 data/seeds/volumes-supplement.yml は不変。 promote/audit が両方 load。\n"
        "# ★全消し禁止: _register-seed4-ndl.py は source: ndl-auto の entry だけを差し替え、\n"
        "#   他 source (rakuten-preorder/rakuten-local/rakuten-live 等) は必ず保存する (2026-08-26恒久修正)。\n"
        + yaml.dump({"schema_version": 1, "generator": "ndl-auto", "volumes": merged},
                    allow_unicode=True, sort_keys=False, width=200))
    # 書き戻し検証 (silent不着防止)
    if len((yaml.safe_load(out_text) or {}).get("volumes") or []) != len(merged):
        print("\n★abort: 出力の再parse件数が一致しない。書き込まない。", file=sys.stderr)
        sys.exit(1)
    OUT_AUTO.write_text(out_text, encoding="utf-8")
    print(f"  merge: 保存(非ndl-auto) {len(preserved)} + ndl-auto {len(entries)}"
          f" (旧ndl-auto {n_prev_ndl} を差替) = {len(merged)}", file=sys.stderr)
    OUT_PENDING.write_text(
        "# 取り込めなかった巻の追跡 (= 将来 NDL更新/別ソースで再訪用)。\n"
        "# reason: NDL未確認(実在不明orラグ) / bind不可 / 重複。 生成元 _register-seed4-ndl.py。\n"
        + yaml.dump({"pending": pending}, allow_unicode=True, sort_keys=False, width=200),
        encoding="utf-8")
    print(f"\n  wrote {OUT_AUTO} ({len(merged)} entries)", file=sys.stderr)
    print(f"  wrote {OUT_PENDING} ({len(pending)} entries)", file=sys.stderr)


if __name__ == "__main__":
    main()
