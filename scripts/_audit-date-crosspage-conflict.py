#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同一ISBNなのに情報が食い違う層の検出器 (family=date-crosspage-conflict, 2026-08-29 新設)。

【何を見るか】
  ISBN13 は「その一冊」の一意キー。 本番(.cache/volume-flat.tsv = data/manga.v2 を1行1巻に展開)
  で **同じ isbn13 が複数の行に現れ、その release_date / number(巻番号) が食い違う** 群を洗う。
  同じ本なのに発売日が違う・巻番号が違うのは、 どちらか一方が**確実に誤り**である。
  ★本検出器は「どちらが正しいか」を裁定しない。 矛盾の存在を確定させ、
    食い違いの幅(日数差・巻番号差)で並べるところまでを担当する。

【なぜ要るか(既存検出器との棲み分け)】
  ・`_audit-isbn-dup-pages.py` = 「同じISBNが複数**頁**に載っている」ことは見るが、
    ①同一頁内の**別版(ed_idx)間**の重複を見ない ②重複行の**中身が食い違うか**を見ない。
    重複しても date/number が完全一致なら単なる二重掲載(頁dedupの仕事)だが、
    食い違えば**書誌そのものが壊れている** = 別レイヤの是正が要る。 そこを分離するのが本器。
  ・`_audit-date-disorder.py` / `_audit-vol-date-regression.py` = edition 内の
    「巻順に対する日付の逆行」。 ISBN同一性を一切使わない = 守備範囲が違う。
  ・`_audit-cover-dup.py` = 同一頁で cover_url が重複。 症状が書影側に出た時だけ拾う。

【判定】
  ・release_date は 'YYYY' / 'YYYY-MM' / 'YYYY-MM-DD' が混在するので、
    各値を**日付レンジ**に展開して比較する。 '1990' と '1990-05-20' は包含関係 = 矛盾ではない。
    レンジが**互いに素**の時だけ矛盾とし、 その隙間の日数を gap_days とする(粒度の罠の恒久封鎖)。
  ・number は空を除いた distinct が2つ以上あれば矛盾。 幅 = max-min。
  ・is_version=1 (versions[] = 刷タブ由来のミラー行) は **既定で除外**。
    実測で versions[0] は edition.volumes の完全ミラー(同 number/同 date)であり、
    472群すべてが偽陽性になる既知型のため。 --with-versions で含められる。

【偽陽性の既知型】
  1. **versions[] ミラー** (上記。 既定で除外済み)
  2. **同日刊行の上下巻/合本** … number が違っても date は同じ。 NUM_CONFLICT に混じるが、
     同一ISBNが2つの巻番号スロットを占める時点で片方は幽霊なので、 やはり要調査。
  3. **DATE_CONFLICT_DAY (gap<31日)** … 取次搬入日 vs 奥付発売日、 月末/月初の丸めで
     数日ずれることがある。 「確実な破損」ではなく「要確認」に落としてある。
  4. **ISBN-10→13 変換の名残** … 本器は13桁同士の同一性しか見ないので影響しない。
  5. **一括登録の偽日付** … 楽天/取次が全巻同じ日付を返す型。 rk_* 列が本番と食い違っても
     楽天側が誤りのことがある = rk_* は**参考証拠**であり裁定ではない。

【是正先(本器は一切書き換えない)】
  ・CROSS_PAGE で丸ごと重複 … 頁dedup (skill isbn-dup-cleanup) → 片方をdrop+リダイレクト
  ・CROSS_PAGE で少数ISBNだけ共有 … 帯混入/過merge → per-case (skill band-intruder-fix)
  ・CROSS_EDITION (同一頁の別版に同ISBN) … 版の取り違え → edition-canonical / edition-overrides
  ・SAME_EDITION で number 違い … 巻番号スロット重複 → 種4(volumes-supplement)/canonical
  ・日付だけの食い違い … 正しい側を残す。 ★canonical結線頁は edition-canonical が後勝ちなので
    種4や overrides でなく canonical 本体を直す(CLAUDE.md 厳守ルール6)。

使い方:
  python scripts/_audit-date-crosspage-conflict.py            # 楽天キャッシュ1パスで証拠列も付ける
  python scripts/_audit-date-crosspage-conflict.py --no-rakuten
  python scripts/_audit-date-crosspage-conflict.py --with-versions
出力: docs/production-diagnostics/date-crosspage-conflict.tsv
"""
import argparse, csv, datetime, json, os, re, sys
from collections import defaultdict, Counter

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAT = os.path.join(ROOT, ".cache", "volume-flat.tsv")
RAKUTEN = os.path.join(ROOT, ".cache", "rakuten-isbn-delta.jsonl")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "date-crosspage-conflict.tsv")


def date_range(s):
    """'YYYY'/'YYYY-MM'/'YYYY-MM-DD' -> (lo_ordinal, hi_ordinal)。 不正/空は None。"""
    s = (s or "").strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        try:
            d = datetime.date(int(s[:4]), int(s[5:7]), int(s[8:10]))
            return (d.toordinal(), d.toordinal())
        except ValueError:
            pass
    if len(s) >= 7 and s[4] == "-" and s[5:7].isdigit():
        try:
            y, m = int(s[:4]), int(s[5:7])
            a = datetime.date(y, m, 1)
            b = datetime.date(y + (m == 12), 1 if m == 12 else m + 1, 1) - datetime.timedelta(days=1)
            return (a.toordinal(), b.toordinal())
        except ValueError:
            pass
    if len(s) >= 4 and s[:4].isdigit():
        y = int(s[:4])
        if 1900 <= y <= 2100:
            return (datetime.date(y, 1, 1).toordinal(), datetime.date(y, 12, 31).toordinal())
    return None


RE_SALES = re.compile(r"(\d{4})年(\d{1,2})月(?:(\d{1,2})日)?")


def rakuten_date(s):
    m = RE_SALES.search(s or "")
    if not m:
        return ""
    y, mo, d = m.group(1), int(m.group(2)), m.group(3)
    return f"{y}-{mo:02d}" + (f"-{int(d):02d}" if d else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-rakuten", action="store_true")
    ap.add_argument("--with-versions", action="store_true")
    a = ap.parse_args()

    groups = defaultdict(list)
    total = 0
    with open(FLAT, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            total += 1
            if not a.with_versions and row.get("is_version") == "1":
                continue
            isbn = (row.get("isbn13") or "").strip()
            if len(isbn) == 13 and isbn.isdigit():
                groups[isbn].append(row)
    dups = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"読込 {total:,}行 / ISBN実数 {len(groups):,} / 重複ISBN {len(dups):,}群", flush=True)

    recs = []
    for isbn, rows in dups.items():
        slugs = sorted({r["slug"] for r in rows})
        eds = {(r["slug"], r["ed_idx"]) for r in rows}
        scope = "CROSS_PAGE" if len(slugs) > 1 else ("CROSS_EDITION" if len(eds) > 1 else "SAME_EDITION")

        rngs = [date_range(r["release_date"]) for r in rows]
        gap = 0
        for i in range(len(rngs)):
            for j in range(i + 1, len(rngs)):
                x, y = rngs[i], rngs[j]
                if not x or not y:
                    continue
                gap = max(gap, max(x[0] - y[1], y[0] - x[1]))
        n_empty = sum(1 for r in rows if not (r["release_date"] or "").strip())

        nums = sorted({int(r["number"]) for r in rows if (r["number"] or "").strip().lstrip("-").isdigit()})
        num_span = (nums[-1] - nums[0]) if len(nums) > 1 else 0
        num_conflict = len(nums) > 1

        if num_conflict:
            klass, sev = "NUM_CONFLICT", "確実"
        elif gap >= 365:
            klass, sev = "DATE_CONFLICT_YEAR", "確実"
        elif gap >= 31:
            klass, sev = "DATE_CONFLICT_MONTH", "高"
        elif gap > 0:
            klass, sev = "DATE_CONFLICT_DAY", "中"
        elif n_empty and n_empty < len(rows):
            klass, sev = "DATE_ASYM", "低"
        else:
            klass, sev = "DUP_ONLY", "参考"

        detail = " || ".join(
            f"{r['slug']}#{r['ed_idx']}({r['ed_type']}/{r['ed_imprint'] or '-'})"
            f" vol={r['number'] or '-'}"
            + (f"[{r['volume_label']}]" if r["volume_label"] else "")
            + f" date={r['release_date'] or '-'}"
            for r in sorted(rows, key=lambda r: (r["slug"], int(r["ed_idx"] or 0), r["number"]))
        )
        recs.append({
            "class": klass, "severity": sev, "scope": scope, "isbn13": isbn,
            "gap_days": gap, "num_span": num_span, "rows": len(rows),
            "pages": len(slugs), "editions": len(eds),
            "titles": " / ".join(sorted({r["title"] for r in rows}))[:80],
            "slugs": ",".join(slugs),
            "detail": detail,
            "rk_date": "", "rk_title": "", "rk_series": "", "rk_verdict": "",
        })

    # --- 楽天キャッシュ 1パス走査(該当ISBNだけ拾う。 裁定でなく参考証拠) ---
    if not a.no_rakuten and os.path.exists(RAKUTEN):
        want = {r["isbn13"] for r in recs}
        found = {}
        print(f"楽天キャッシュ 1パス走査 ({os.path.getsize(RAKUTEN)/1e9:.2f}GB) ...", flush=True)
        with open(RAKUTEN, encoding="utf-8") as f:
            for line in f:
                i = line.find('"isbn": "')  # 高速前置フィルタ(JSONパースを該当行だけに絞る)
                if i < 0:
                    continue
                key = line[i + 9:i + 22]
                if key not in want or key in found:
                    continue
                try:
                    it = json.loads(line).get("item") or {}
                except Exception:
                    continue
                found[key] = it
        print(f"  楽天ヒット {len(found):,}/{len(want):,}", flush=True)
        for r in recs:
            it = found.get(r["isbn13"])
            if not it:
                continue
            rd = rakuten_date(it.get("salesDate"))
            r["rk_date"] = rd
            r["rk_title"] = (it.get("title") or "")[:50]
            r["rk_series"] = it.get("seriesName") or ""
            rr = date_range(rd)
            if rr:
                allr = [d for d in (date_range(x["release_date"]) for x in dups[r["isbn13"]]) if d]
                agree = [d for d in allr if not (d[0] > rr[1] or rr[0] > d[1])]
                if allr:
                    r["rk_verdict"] = ("楽天=全行一致" if len(agree) == len(allr)
                                       else f"楽天一致 {len(agree)}/{len(allr)}行" if agree
                                       else "楽天=どの行とも不一致")

    order = {"NUM_CONFLICT": 0, "DATE_CONFLICT_YEAR": 1, "DATE_CONFLICT_MONTH": 2,
             "DATE_CONFLICT_DAY": 3, "DATE_ASYM": 4, "DUP_ONLY": 5}
    recs.sort(key=lambda r: (order[r["class"]], -r["gap_days"], -r["num_span"], r["isbn13"]))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    cols = ["class", "severity", "scope", "isbn13", "gap_days", "num_span", "rows", "pages",
            "editions", "titles", "slugs", "rk_date", "rk_verdict", "rk_title", "rk_series", "detail"]
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        w.writerows(recs)

    print(f"\n出力: {OUT}  ({len(recs):,}群)", flush=True)
    ck = Counter(r["class"] for r in recs)
    for k in sorted(ck, key=lambda x: order[x]):
        sc = Counter(r["scope"] for r in recs if r["class"] == k)
        print(f"  {k:<20} {ck[k]:>5}   " + " ".join(f"{s}={n}" for s, n in sc.most_common()), flush=True)
    real = sum(n for k, n in ck.items() if k != "DUP_ONLY")
    print(f"\n★情報が食い違う群 = {real} (DUP_ONLY {ck.get('DUP_ONLY', 0)} は既存 _audit-isbn-dup-pages 担当)")
    print("\n=== 重症 Top20 ===", flush=True)
    for r in recs[:20]:
        print(f"[{r['class']}/{r['scope']}] {r['isbn13']} gap={r['gap_days']}d span={r['num_span']} "
              f"{r['titles'][:34]} | rk={r['rk_date']} {r['rk_verdict']} | {r['detail'][:130]}", flush=True)


if __name__ == "__main__":
    main()
