#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**同一頁の中**で同じ isbn13 が2箇所以上に現れる型の検出器 (2026-08-29 新設)。

★何を見るか
  ISBN は1つの物理商品を一意に指す番号なので、**1つの作品頁の中に同じ ISBN が2度出る**のは
  原則すべて構造の壊れ。頁の中でどこに重複したかで原因の型が違うので3つに分ける:
    (1) NUM_INFLATION  同一版(ed_idx)の**別の巻番号**に同じ ISBN = 巻番号の水増し。
                       1冊が2巻に見え、巻数が実際より多く出る。片方は中身の無い偽巻。
    (2) EDITION_DOUBLE 同一頁の**別の版**に同じ ISBN = 版の二重計上。
                       同じ本が「通常版」と「新装版」の両タブに座る。版の帰属がどちらか誤り。
                       版どうしの共有率で 版まるごと複製 / 大半重複 / 1〜数冊の混入 に分ける。
    (3) EXACT_DUP      同一版・同一巻番号に同じ ISBN が2行 = 単純重複(promote の潰し残し)。
  加えて刷タブ(versions[])絡みを別勘定にする:
    - MIRROR            versions[0] が edition.volumes をそのまま写した既知の正当ミラー(= 偽陽性)。
                        既定では**出力しない**(--include-mirror で出る)。summary には件数だけ出す。
    - VERSION_MISPLACED 刷タブと本体で ISBN は同じなのに**巻番号か版が食い違う** = ミラーの壊れ。
    - VERSION_ONLY      刷タブの中だけで同じ ISBN が重複。

★なぜ既存検出器で足りないか
  - `_audit-isbn-dup-pages.py`   = **頁と頁のあいだ**の同 ISBN(D・N・A^2型の頁分裂)。頁の内側は見ない。
  - `_audit-cover-dup.py`        = 同一頁で**書影URL**が重複。docstring 自身が「同一ISBN×複数版=ISBN構造
                                   ダブリは isbn-dup-cleanup 領域・書影は症状」と明言し**担当外**にしている。
                                   書影は null のことも別URLのこともあるので書影経由では ISBN 重複を取り逃す。
  - `_audit-volume-numbering.py` = 巻番号の連番異常(欠番/水増し)を番号の並びだけで見る。
                                   「同じ ISBN が2巻に居る」という**原因側**の署名は持たない。
  よって本検出器の対象(頁内 ISBN 重複)は既存のどれにも属していない。

★既知の偽陽性
  - MIRROR(刷タブが本体のミラー)。正当。既定で除外。
  - 復刻版/新装版/文庫版が同一頁に並ぶのは正当だが、**同じ ISBN を共有することは正当でない**
    (別の版は必ず別 ISBN)。合本・セット商品も構成単行本と ISBN を共有しない。
    よって EDITION_DOUBLE に「正当な版違い」は入らない。ただし *どちらの版が正しい帰属か* は
    本検出器では決まらない(= 是正は人手裁定)。

★是正先(本検出器は検出のみ・データを一切変更しない)
  - NUM_INFLATION / EXACT_DUP -> `data/seeds/edition-canonical/<SRC slug>.yml` で巻を再構築
                                 (canonical のキーは **SRC slug**)。canonical 不在なら
                                 volume-exclude 系で偽スロットを落とす。
  - EDITION_DOUBLE            -> `edition-overrides.json`(キーは **公開slug**)で版を統合、
                                 または canonical の suppress_types で旧版を消す。
  - VERSION_MISPLACED         -> versions[](刷タブ)の組み立て側を疑う。

入力: .cache/volume-flat.tsv (親が展開済みの巻フラットTSV)
出力: docs/production-diagnostics/isbn-dup-internal.tsv
使い方:
  python scripts/_audit-isbn-dup-internal.py
  python scripts/_audit-isbn-dup-internal.py --include-mirror
"""
import argparse, csv, io, os, sys
from collections import defaultdict
from itertools import combinations

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, ".cache", "volume-flat.tsv")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "isbn-dup-internal.tsv")

COLS = ["class", "severity", "slug", "title", "isbn13", "isbn_ok", "n_rows",
        "n_editions", "numbers", "ed_idx", "ed_types", "ed_labels", "ed_imprints",
        "release_dates", "ed_overlap", "flags", "slot_conflict", "note"]

# flags の意味:
#   PHANTOM_ED   重複に噛む版のどれかが imprint も publisher も空 = 種4の edition_type 既定値が
#                作った「実在しない幻の版」の署名([[edition_run_split_arms_wide_type]] 真因3)。
#   JOGE         重複に噛む行に volume_label(上/下 等)がある = 1冊の分冊表記が別巻に化けた型。
#   DATE_DIFF    同じ ISBN なのに release_date が食い違う = 片方の日付が別商品由来。
#   PUB_DIFF     重複に噛む版で publisher(出版社)が違う = 他社の ISBN を貼っている確定的な誤り。
#   ISBN_BAD     ISBN-13 として不正(チェックディジット/桁/二重接頭辞)。


def isbn13_ok(s):
    """ISBN-13 として妥当か。チェックディジットに加え **二重接頭辞** も落とす。
    '9789784537100' = '978' + '9784537100'(既に978始まりの日本ISBNの頭10桁)を連結した壊れ。
    チェックディジットは偶然通ってしまうので、構造(978の直後にまた9784が来る)で名指しする。"""
    if not s or len(s) != 13 or not s.isdigit():
        return False
    if s[:3] in ("978", "979") and s[3:7] == "9784":
        return False  # 二重接頭辞
    t = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(s[:12]))
    return (10 - t % 10) % 10 == int(s[12])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-mirror", action="store_true",
                    help="刷タブの正当ミラー(既知偽陽性)も出力する")
    args = ap.parse_args()

    pages = defaultdict(list)
    with io.open(SRC, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            pages[r["slug"]].append(r)
    print("読み込み: %d頁" % len(pages), flush=True)

    rows_out = []
    counts = defaultdict(int)
    pages_flagged = set()
    vols_flagged = 0

    for slug, rs in pages.items():
        title = rs[0]["title"]
        slot_isbns = defaultdict(set)   # (ed_idx, number, is_version) -> set(isbn) 偽スロット判定用
        for r in rs:
            if r["isbn13"]:
                slot_isbns[(r["ed_idx"], r["number"], r["is_version"])].add(r["isbn13"])
        ed_isbns = defaultdict(set)     # 版ごとの ISBN 集合(主 volumes のみ)
        for r in rs:
            if r["isbn13"] and r["is_version"] == "0":
                ed_isbns[r["ed_idx"]].add(r["isbn13"])

        by_isbn = defaultdict(list)
        for r in rs:
            if r["isbn13"]:
                by_isbn[r["isbn13"]].append(r)

        for isbn, grp in by_isbn.items():
            if len(grp) < 2:
                continue
            main_rows = [x for x in grp if x["is_version"] == "0"]
            ver_rows = [x for x in grp if x["is_version"] == "1"]
            eds = sorted({x["ed_idx"] for x in grp}, key=lambda v: int(v))
            nums = sorted({x["number"] for x in grp})
            note = ""
            overlap = ""

            if main_rows and ver_rows:
                if ({x["ed_idx"] for x in main_rows} == {x["ed_idx"] for x in ver_rows}
                        and {x["number"] for x in main_rows} == {x["number"] for x in ver_rows}):
                    klass, sev = "MIRROR", "既知偽陽性"
                    note = "versions[]が本体volumesを写した正当ミラー"
                else:
                    klass, sev = "VERSION_MISPLACED", "要確認"
                    note = "刷タブと本体で版か巻番号が食い違う"
            elif ver_rows and not main_rows:
                klass, sev = "VERSION_ONLY", "要確認"
                note = "刷タブ内で同一ISBNが重複"
            elif len(eds) > 1:
                klass = "EDITION_DOUBLE"
                best = 0.0
                for a, b in combinations(eds, 2):
                    ia, ib = ed_isbns.get(a, set()), ed_isbns.get(b, set())
                    small = min(len(ia), len(ib)) or 1
                    best = max(best, len(ia & ib) / small)
                overlap = "%.0f%%" % (best * 100)
                if best >= 0.8:
                    sev, note = "確実な破損", "版まるごと複製(共有率%s)" % overlap
                elif best >= 0.3:
                    sev, note = "確実な破損", "版の大半が重複(共有率%s)" % overlap
                else:
                    sev, note = "要確認", "1〜数冊だけ別版に混入(共有率%s)" % overlap
                if len(nums) > 1:
                    note += " / 巻番号も食い違う(%s)" % ",".join(nums)
            elif len(nums) > 1:
                klass, sev = "NUM_INFLATION", "確実な破損"
                note = "同一版の巻%sに同じ本 = 巻数水増し" % ",".join(nums)
            else:
                klass, sev = "EXACT_DUP", "確実な破損"
                note = "同一版・同一巻番号に同じ行が2つ"

            if klass == "MIRROR" and not args.include_mirror:
                counts["MIRROR"] += 1
                continue

            # 重複ISBNが占めるスロットに「別のISBN」も居るか(= 偽スロットの決定打)
            conflict = []
            for x in grp:
                others = slot_isbns[(x["ed_idx"], x["number"], x["is_version"])] - {isbn}
                if others:
                    conflict.append("ed%s/vol%s<-%s" % (x["ed_idx"], x["number"], ",".join(sorted(others))))
            ok = isbn13_ok(isbn)
            if not ok:
                sev = "確実な破損"
                note = ("ISBN自体が不正(チェックディジット/桁) ; " + note).strip(" ;")

            flags = []
            if not ok:
                flags.append("ISBN_BAD")
            if any(not (x["ed_imprint"] or x["ed_publisher"]) for x in grp):
                flags.append("PHANTOM_ED")
            if any(x["volume_label"] for x in grp):
                flags.append("JOGE")
            if len({x["release_date"] for x in grp}) > 1:
                flags.append("DATE_DIFF")
            if len({x["ed_publisher"] for x in grp if x["ed_publisher"]}) > 1:
                flags.append("PUB_DIFF")

            counts[klass] += 1
            pages_flagged.add(slug)
            vols_flagged += len(grp)
            rows_out.append([
                klass, sev, slug, title, isbn, "1" if ok else "0", len(grp),
                len(eds), ",".join(nums), ",".join(eds),
                "|".join(dict.fromkeys(x["ed_type"] for x in grp)),
                "|".join(dict.fromkeys(x["ed_label"] for x in grp)),
                "|".join(dict.fromkeys(x["ed_imprint"] for x in grp)),
                "|".join(dict.fromkeys(x["release_date"] for x in grp)),
                overlap, ",".join(flags), " ; ".join(dict.fromkeys(conflict)), note,
            ])

    order = {"EXACT_DUP": 0, "NUM_INFLATION": 1, "EDITION_DOUBLE": 2,
             "VERSION_MISPLACED": 3, "VERSION_ONLY": 4, "MIRROR": 5}
    sev_order = {"確実な破損": 0, "要確認": 1, "既知偽陽性": 2}
    rows_out.sort(key=lambda r: (sev_order.get(r[1], 9), order.get(r[0], 9), -int(r[6]), r[2]))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(COLS)
        w.writerows(rows_out)

    print("=== 頁内ISBN重複 監査 ===")
    for k in sorted(counts, key=lambda k: order.get(k, 9)):
        tag = " (既知偽陽性・既定で非出力)" if k == "MIRROR" and not args.include_mirror else ""
        print("  %-18s %5d group%s" % (k, counts[k], tag))
    print("  出力 %d行 / %d頁 / のべ%d巻 -> %s"
          % (len(rows_out), len(pages_flagged), vols_flagged, os.path.relpath(OUT, ROOT)))


if __name__ == "__main__":
    main()
