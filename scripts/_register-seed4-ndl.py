"""NDL 確認済ドラフト (.cache/seed4-drafts.yml) を 種4 auto ファイルに登録 + 未確認分を追跡。

★ 慎重設計:
- 手動キュレーションの data/seeds/volumes-supplement.yml は **不変**。
  自動分は別ファイル data/seeds/volumes-supplement-auto.yml に書く (= promote/audit が両方 load)。
- 登録前に validate: series_keys が db に bind するか / 巻番号が既存でないか。
  bind不可 or 重複 は skip して pending に回す。
- ISBN-10 → ISBN-13 変換、 発売日を YYYY-MM 正規化。
- 「取り込めなかった物」= NDL未確認(progress の miss) + validate失敗 を
  data/seeds/volumes-pending.yml に追跡記録 (将来 NDL更新/別ソースで再訪用)。

入力: .cache/seed4-drafts.yml (hit) + .cache/seed4-progress.jsonl (miss)
出力: data/seeds/volumes-supplement-auto.yml / data/seeds/volumes-pending.yml
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

    entries = []
    pending = []
    n_ok = n_bind = n_dup = 0
    for d in drafts:
        keys = d.get("series_keys") or []
        num = d["number"]
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
    print(f"  ドラフト {len(drafts)} / 登録OK {n_ok} / bind不可 {n_bind} / 重複 {n_dup}", file=sys.stderr)
    print(f"  pending (未確認NDL miss {n_miss} + validate失敗 {n_bind + n_dup}) = {len(pending)}", file=sys.stderr)

    if not APPLY:
        print("\n(--apply で書き込み)", file=sys.stderr)
        return

    OUT_AUTO.write_text(
        "# 【自動生成】NDL 確認済 MADB取込もれ巻 (= 種4 auto)。 生成元 _register-seed4-ndl.py。\n"
        "# 手動版 data/seeds/volumes-supplement.yml は不変。 promote/audit が両方 load。\n"
        "# ★ db-v2 再build / NDL再取得時は再生成。\n"
        + yaml.dump({"schema_version": 1, "generator": "ndl-auto", "volumes": entries},
                    allow_unicode=True, sort_keys=False, width=200),
        encoding="utf-8")
    OUT_PENDING.write_text(
        "# 取り込めなかった巻の追跡 (= 将来 NDL更新/別ソースで再訪用)。\n"
        "# reason: NDL未確認(実在不明orラグ) / bind不可 / 重複。 生成元 _register-seed4-ndl.py。\n"
        + yaml.dump({"pending": pending}, allow_unicode=True, sort_keys=False, width=200),
        encoding="utf-8")
    print(f"\n  wrote {OUT_AUTO} ({n_ok} entries)", file=sys.stderr)
    print(f"  wrote {OUT_PENDING} ({len(pending)} entries)", file=sys.stderr)


if __name__ == "__main__":
    main()
