"""巻番号サニティ監査 (= 月次サニティ監査の番号層、 read-only)。

MADB由来の巻番号異常を merge解決後の page×edition 単位で検出・分類する。

検出する型:
  - AUTO_FIXED   = 上下/上中下/前後 が★完全に揃い番号gap (= 下=3型の水増し)。
                   promote の _fix_complete_sequence_numbers が 1..N に自動是正済。
                   ★本監査は「是正対象が想定通りか」の可視化用 (= 件数監視)。
  - MISSING_HALF = 上 or 下 の片側のみ等、 sequence ラベルはあるが不完全 (= 取りこぼし。
                   上巻 or 下巻が未収録 → 種4/補完の領域。 ★renumberしてはいけない)。
  - GAP_OTHER    = sequence ラベル無しで max(巻番号) > 実巻数 (= 真の欠番 or 別要因。 要調査)。

判定は promote と同じ定義を import (= _SEQ_RANK / _COMPLETE_SEQS / KEEP_EDITION_TYPES /
_sanitize_volnum) して齟齬を防ぐ。

出力:
  .cache/audit-volnum-summary.md           = 件数サマリ
  .cache/audit-volnum-missing.tsv          = MISSING_HALF (= 取りこぼし候補、 actionable)
  .cache/audit-volnum-gapother.tsv         = GAP_OTHER (= 要調査)

使い方: python scripts/_audit-volume-numbering.py
"""
import sys
import json
import importlib.util
from pathlib import Path
from collections import defaultdict

import yaml
import sqlite3

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"

# promote の定義を import (= 判定ロジックを一元化)
_spec = importlib.util.spec_from_file_location("promote", ROOT / "scripts" / "_promote-bulk-v2.py")
pm = importlib.util.module_from_spec(_spec)
_saved_argv = sys.argv
sys.argv = ["x"]
_spec.loader.exec_module(pm)
sys.argv = _saved_argv

KEEP = pm.KEEP_EDITION_TYPES
SEQ_RANK = pm._SEQ_RANK
COMPLETE_SEQS = pm._COMPLETE_SEQS
sanitize = pm._sanitize_volnum


def load_sid2page(con) -> dict:
    """merge (auto + hand) を解決し sid -> page_key を返す。"""
    key2page = {}
    auto = json.load((ROOT / "data/seeds/series-merge-auto.json").open(encoding="utf-8"))["merges"]
    for g in auto:
        mk = g.get("merge_keys") or []
        for k in mk:
            key2page[k] = mk[0]
    hand = yaml.safe_load((ROOT / "data/seeds/series-merge.yml").read_text(encoding="utf-8")) or []
    for e in hand:
        if isinstance(e, dict):
            mk = e.get("merge_keys") or []
            if len(mk) >= 2:
                for k in mk:
                    key2page[k] = mk[0]
    return {sid: key2page.get(sk, sk) for sid, sk in con.execute("SELECT id, series_key FROM series")}


def norm_label(lab: str | None) -> str | None:
    if not lab:
        return None
    lab = lab.replace("巻", "").strip()
    return lab if lab in SEQ_RANK else None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    con = sqlite3.connect(DB)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    sid2page = load_sid2page(con)
    title_of = {sid: t for sid, t in con.execute("SELECT id, title FROM series")}

    # page × edition_type → {巻番号集合, ラベル集合, sid集合}
    page_ed = defaultdict(lambda: defaultdict(lambda: {"nums": set(), "labels": set(), "sids": set(), "title": ""}))
    rows = con.execute(
        """SELECT e.series_id, e.type, v.number, v.volume_label
           FROM editions e JOIN volumes v ON v.edition_id=e.id
           WHERE v.isbn13 IS NOT NULL AND v.isbn13!=''"""
    ).fetchall()
    for sid, ty, num, lab in rows:
        if ty not in KEEP:
            continue
        n = sanitize(num, None, lab)
        if not n:
            continue
        pg = sid2page.get(sid, sid)
        d = page_ed[pg][ty]
        d["nums"].add(n)
        d["sids"].add(sid)
        if lab:
            d["labels"].add(lab)
        d["title"] = title_of.get(sid, "")

    auto_fixed, missing_half, gap_other = [], [], []
    for pg, eds in page_ed.items():
        for ty, d in eds.items():
            nums = d["nums"]
            if not nums:
                continue
            cnt, mx = len(nums), max(nums)
            if mx <= cnt:
                continue  # gap 無し = 正常
            labset = {norm_label(x) for x in d["labels"]}
            labset.discard(None)
            expected = COMPLETE_SEQS.get(frozenset(labset))
            rec = [d["title"], ty, sorted(nums), cnt, mx, sorted(d["labels"])[:4], len(d["sids"])]
            if expected and cnt == expected and sorted(nums) != list(range(1, cnt + 1)):
                auto_fixed.append(rec)            # 完全揃い → promoteが是正済
            elif labset:
                missing_half.append(rec)          # 片側のみ等 = 取りこぼし
            else:
                gap_other.append(rec)             # ラベル無しgap = 真の欠番/要調査

    def write_tsv(path, recs):
        with (ROOT / path).open("w", encoding="utf-8") as f:
            f.write("title\ttype\tnums\tcount\tmax\tlabels\tsids\n")
            for r in recs:
                f.write(f"{r[0]}\t{r[1]}\t{r[2]}\t{r[3]}\t{r[4]}\t{r[5]}\t{r[6]}\n")

    write_tsv(".cache/audit-volnum-missing.tsv", missing_half)
    write_tsv(".cache/audit-volnum-gapother.tsv", gap_other)
    summary = (
        f"# 巻番号サニティ監査\n\n"
        f"- AUTO_FIXED (上下完全揃い+gap=下=3型、 promote是正済): {len(auto_fixed):,}\n"
        f"- MISSING_HALF (片側のみ=取りこぼし、 種4領域): {len(missing_half):,}\n"
        f"- GAP_OTHER (ラベル無しgap=真の欠番/要調査): {len(gap_other):,}\n"
    )
    (ROOT / ".cache/audit-volnum-summary.md").write_text(summary, encoding="utf-8")
    print(summary)
    print("MISSING_HALF 例:")
    for r in missing_half[:8]:
        print(f"  「{r[0][:24]}」 {r[1]} 番号{r[2]} {r[3]}冊 ラベル{r[5]}")
    print("\nGAP_OTHER 例:")
    for r in sorted(gap_other, key=lambda x: -(x[4] - x[3]))[:8]:
        print(f"  「{r[0][:24]}」 {r[1]} 番号{r[2]} {r[3]}冊 max{r[4]}")


if __name__ == "__main__":
    main()
