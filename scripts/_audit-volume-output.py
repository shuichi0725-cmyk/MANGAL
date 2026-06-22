#!/usr/bin/env python3
"""巻 出力サニティ監査 (= ★promote 出力 = 本番 yml を読む、 read-only)。

既存 `_audit-volume-numbering.py` は ★種2 sqlite (ソース) を読むため、 promote の
merge/dedup が ★出力側で作った穴 (= 菜の #1 欠落型) を原理的に検出できなかった。
本監査は ★本番 yml (= data/manga.v2) を直接読み、 出力にだけ存在する異常を洗い出す。

検出する型 (= 各 edition 単位、 すべて flag のみ・自動修正しない):
  - MISSING_VOL1   = 巻番号が 1 から始まらない (= #1 欠落)。 ★何度でも確実に再現検出。
  - GAP            = 1..max の連番に欠番 (= 中抜け)。
  - PUBLISHER_MIX  = 1 edition 内で ISBN 出版者記号が混在 (= 別社混入 = 誤merge/誤dedupの兆候)。
  - DATE_DISORDER  = 巻番号順に並べた発売日が逆行 (= 日付の矛盾。 ★菜の 2025↔1994 混在型)。

★種2 sqlite と突合し、 欠番が「ソースに在る=promoteが落とした=RECOVERABLE」か
  「ソースにも無い=真の取りこぼし=種4領域」かを判定 (= 直し方の優先度づけ)。

使い方:
  python scripts/_audit-volume-output.py                  # 本番 data/manga.v2 を監査
  python scripts/_audit-volume-output.py .preview-data/manga   # プレビューを監査(高速・検証用)
出力: .cache/audit-vol-output-*.tsv + summary.md
"""
import sys, os, glob, time, json
from collections import defaultdict, Counter
sys.stdout.reconfigure(encoding="utf-8")
import yaml
try: from yaml import CSafeLoader as L
except ImportError: from yaml import SafeLoader as L
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / ".cache" / "db-v2.sqlite"

KEEP_TYPES = {"standard", "bunkobon", "wideban", "kanzenban", "shinsoban", "aizoban"}
# 巻番号順に並べた発売日が「これ以上 逆行」したら矛盾とみなす閾値(日)。
#   = 高番号巻が低番号巻より明らかに前に出た = 別版/別社混入のシグナル。
DATE_BACKSTEP_DAYS = 365


def norm_isbn(s) -> str:
    if s is None: return ""
    return "".join(ch for ch in str(s) if ch.isdigit())


def jp_pub_prefix(isbn: str) -> str:
    """日本(978-4)ISBNの ★出版者記号プレフィックスを登録グループ長ルールで正確に返す。
    publisher コードは可変長(2-7桁) = 固定長 slice では大手を誤分割する。
    978-4 群の範囲: 0-1→2桁 / 2-6→3桁 / 70-84→4桁 / 85-89→5桁 / 900-949→6桁 / 950-999→7桁。
    例: 講談社=9784-06(978406) / 別社=9784-7683(97847683) / 双葉社=9784-575(9784575)。"""
    i = norm_isbn(isbn)
    if len(i) < 13 or not i.startswith("9784"):
        return i[:7]
    r = i[4:]  # 9784 の後
    if r[0] in "01": ln = 2
    elif r[0] in "23456": ln = 3
    elif "70" <= r[:2] <= "84": ln = 4
    elif "85" <= r[:2] <= "89": ln = 5
    elif "900" <= r[:3] <= "949": ln = 6
    else: ln = 7
    return i[:4 + ln]


def to_days(d) -> int | None:
    """'YYYY-MM' / 'YYYY-MM-DD' / 'YYYY' を概算日数に。 比較専用。"""
    if not d: return None
    s = str(d)
    parts = s.split("-")
    try:
        y = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
    except (ValueError, IndexError):
        return None
    return y * 365 + m * 30 + day


def load_source_index(con):
    """種2 sqlite から isbn→sid と sid→{number:[(isbn,date,pub)]} を構築 (= 復元可否判定用)。"""
    isbn2sid = {}
    sid_num = defaultdict(lambda: defaultdict(list))
    rows = con.execute(
        """SELECT e.series_id, v.number, v.isbn13, v.release_date
           FROM volumes v JOIN editions e ON e.id=v.edition_id
           WHERE v.isbn13 IS NOT NULL AND v.isbn13!=''"""
    ).fetchall()
    for sid, num, isbn, rd in rows:
        ni = norm_isbn(isbn)
        if not ni: continue
        isbn2sid[ni] = sid
        if num:
            sid_num[sid][num].append((ni, rd, jp_pub_prefix(ni)))
    return isbn2sid, sid_num


def edition_volumes(ed):
    """edition の主巻列 (= versions でなく直下 volumes)。 number 有のみ。"""
    out = []
    for v in (ed.get("volumes") or []):
        n = v.get("number")
        if isinstance(n, int) and n >= 1:
            out.append(v)
    return out


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data" / "manga.v2")
    if not os.path.isdir(src): src = str(ROOT / "data" / "manga.v2")
    con = sqlite3.connect(DB)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    isbn2sid, sid_num = load_source_index(con)

    miss1, gap, pubmix, disorder = [], [], [], []
    t0 = time.time(); n_files = 0; n_eds = 0

    for f in glob.glob(os.path.join(src, "*.yml")):
        try: d = yaml.load(open(f, encoding="utf-8"), Loader=L)
        except Exception: continue
        if not d: continue
        n_files += 1
        slug = d.get("slug") or os.path.basename(f)[:-4]
        title = d.get("title") or ""
        for ed in (d.get("editions") or []):
            ty = ed.get("type")
            if ty not in KEEP_TYPES: continue
            vols = edition_volumes(ed)
            if not vols: continue
            n_eds += 1
            nums = sorted({v["number"] for v in vols})
            mx = nums[-1]
            isbns = [norm_isbn(v.get("isbn13")) for v in vols if v.get("isbn13")]
            # このページの source sid 集合(= 出力ISBNから逆引き)
            sidset = {isbn2sid[i] for i in isbns if i in isbn2sid}
            # 主出版者プレフィックス(= 多数派)
            pubs = Counter(jp_pub_prefix(i) for i in isbns if i)
            dom_pub = pubs.most_common(1)[0][0] if pubs else ""

            def recover(numbers):
                """欠番 numbers がソース(同ページsid)に在るか → 復元候補ISBNを返す。"""
                rec = {}
                for nn in numbers:
                    cands = []
                    for sid in sidset:
                        cands += sid_num.get(sid, {}).get(nn, [])
                    if cands:
                        # 多数派出版者線に一致する候補を優先(= 本物の版)
                        same = [c for c in cands if c[2] == dom_pub]
                        pick = (same or cands)[0]
                        rec[nn] = pick[0]
                return rec

            # ── MISSING_VOL1 ──
            if nums[0] > 1:
                missing_low = list(range(1, nums[0]))
                rec = recover(missing_low)
                miss1.append([slug, title, ty, missing_low, nums, len(sidset),
                              "RECOVERABLE" if rec else "SOURCE_GAP", rec])
            # ── GAP (中抜け。 vol1欠落以外の欠番) ──
            missing_mid = [k for k in range(nums[0], mx + 1) if k not in set(nums)]
            if missing_mid:
                rec = recover(missing_mid)
                gap.append([slug, title, ty, missing_mid, mx, len(nums),
                            "RECOVERABLE" if rec else "SOURCE_GAP", rec])
            # ── PUBLISHER_MIX ──
            if len(pubs) > 1:
                minority = sum(c for p, c in pubs.items() if p != dom_pub)
                pubmix.append([slug, title, ty, dict(pubs), dom_pub, minority])
            # ── DATE_DISORDER (巻番号順 発売日 逆行) ──
            seq = [(v["number"], to_days(v.get("release_date"))) for v in vols]
            seq = [(n, dd) for n, dd in seq if dd is not None]
            seq.sort(key=lambda x: x[0])
            worst = 0; pair = None
            prev_n, prev_d = None, None
            for nn, dd in seq:
                if prev_d is not None and dd < prev_d:
                    back = prev_d - dd
                    if back > worst:
                        worst = back; pair = (prev_n, prev_d, nn, dd)
                # 単調増加の追跡 = 直前の最大日付でなく、 連続比較(隣接逆行)
                prev_n, prev_d = nn, dd
            if worst > DATE_BACKSTEP_DAYS and pair:
                disorder.append([slug, title, ty, round(worst / 365, 1), pair, nums])

    # ── 出力 ──
    OUT = ROOT / ".cache"
    def w(path, header, recs):
        with (OUT / path).open("w", encoding="utf-8") as fp:
            fp.write(header + "\n")
            for r in recs:
                fp.write("\t".join(str(x) for x in r) + "\n")

    miss1.sort(key=lambda r: (r[6] != "RECOVERABLE", r[0]))  # RECOVERABLE 先頭
    gap.sort(key=lambda r: (r[6] != "RECOVERABLE", -len(r[3])))
    pubmix.sort(key=lambda r: -r[5])
    disorder.sort(key=lambda r: -r[3])

    w("audit-vol-output-missing1.tsv", "slug\ttitle\ttype\tmissing_low\tnums\tn_sid\tverdict\trecover_isbn",
      [[r[0], r[1], r[2], r[3], r[4], r[5], r[6], json.dumps(r[7], ensure_ascii=False)] for r in miss1])
    w("audit-vol-output-gap.tsv", "slug\ttitle\ttype\tmissing\tmax\tcount\tverdict\trecover_isbn",
      [[r[0], r[1], r[2], r[3], r[4], r[5], r[6], json.dumps(r[7], ensure_ascii=False)] for r in gap])
    w("audit-vol-output-pubmix.tsv", "slug\ttitle\ttype\tpub_counts\tdominant\tminority_vols",
      [[r[0], r[1], r[2], json.dumps(r[3], ensure_ascii=False), r[4], r[5]] for r in pubmix])
    w("audit-vol-output-datedisorder.tsv", "slug\ttitle\ttype\tback_years\tpair(prevN,prevD,curN,curD)\tnums",
      [[r[0], r[1], r[2], r[3], r[4], r[5]] for r in disorder])

    miss1_rec = sum(1 for r in miss1 if r[6] == "RECOVERABLE")
    gap_rec = sum(1 for r in gap if r[6] == "RECOVERABLE")
    summary = (
        f"# 巻 出力サニティ監査 (本番yml = {src})\n\n"
        f"- 走査: {n_files:,}作品 / {n_eds:,}edition / {time.time()-t0:.1f}秒\n\n"
        f"- MISSING_VOL1 (#1欠落): {len(miss1):,}  "
        f"(うち RECOVERABLE=ソースに在る={miss1_rec:,} / SOURCE_GAP=真の欠落={len(miss1)-miss1_rec:,})\n"
        f"- GAP (中抜け): {len(gap):,}  (うち RECOVERABLE={gap_rec:,})\n"
        f"- PUBLISHER_MIX (別社混入): {len(pubmix):,}\n"
        f"- DATE_DISORDER (日付逆行): {len(disorder):,}\n"
    )
    (OUT / "audit-vol-output-summary.md").write_text(summary, encoding="utf-8")
    print(summary)
    print("MISSING_VOL1 (RECOVERABLE 例):")
    for r in miss1[:8]:
        print(f"  {r[0]} 「{r[1][:18]}」 {r[2]} 欠={r[3]} {r[6]} 復元={r[7]}")
    print("\nDATE_DISORDER 例:")
    for r in disorder[:8]:
        print(f"  {r[0]} 「{r[1][:18]}」 逆行{r[3]}年 {r[4]}")
    print("\nPUBLISHER_MIX 例:")
    for r in pubmix[:8]:
        print(f"  {r[0]} 「{r[1][:18]}」 {r[3]} 少数={r[5]}巻")


if __name__ == "__main__":
    main()
