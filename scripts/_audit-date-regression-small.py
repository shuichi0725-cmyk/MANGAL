"""★発売日の「小さな逆行」監査 (= date-regression-small)。

■何を見るか
同一版(edition)の中で **巻番号が進むのに発売日が過去へ戻る**箇所のうち、
逆行幅が **1日以上〜5年未満** のものを担当する。

■なぜ(既存検出器との棲み分け)
  - `_audit-vol-date-regression.py` = **年差5年以上**の大逆行(ギャラ型=別作品の接ぎ木)だけを見る。
  - `_audit-date-disorder.py` = **standard版 × 総巻数10以上**の長期連載だけ。しかも
    生の文字列比較なので "1990" < "1990-05" が常に真になり、日付精度の粗い巻で偽陽性を出す。
  - `_audit-date-order.py` = 全版だが 200日以上のみ、かつ 'YYYY' を 6/15、'YYYY-MM' を 15日で
    **埋めて**比較するため、精度の粗い巻で偽陽性/偽陰性が混ざる。出力先も .cache(=消える)。
  → 本検出器は「1日〜5年未満」の帯を、**日付精度を落として偽陽性を作らない**方式で拾い、
    docs/production-diagnostics に永続化する。

■判定(★偽陽性を作らない核)
発売日を「点」でなく **可能日区間 [lo,hi]** として扱う:
    'YYYY-MM-DD' → [その日, その日]
    'YYYY-MM'    → [月初, 月末]
    'YYYY'       → [1/1, 12/31]
巻番号 i < j の2巻について、**確実な逆行日数 = lo_i - hi_j**。これが 1 以上の時だけ flag。
つまり「日付精度をどう解釈しても i の方が後に出た」と言い切れる場合のみ拾う。
  → 同月内の前後(1990-05-30 と 1990-05 等)、同日発売、'YYYY' だけの巻は原理的に flag されない。

■階層(worst_days = そのeditionの最大の確実逆行日数)
  T1_1年以上   : 365 <= worst_days < 1825
  T2_3か月以上 :  90 <= worst_days < 365
  T3_1日以上   :   1 <= worst_days < 90
5年(1825日)以上は既存 _audit-vol-date-regression.py の担当なので **TSVから除外**(件数だけ報告)。

■形(shape) = 是正先の当たりをつける
逆行ペアに関与する巻を貪欲に取り除いて矛盾が消える最小集合(offenders)を求め、
  SINGLE   = 1巻だけ浮いている  → その巻の日付誤り / 帯混入(band-intruder) / 別版の1冊混入
  BLOCK    = 番号が連続した塊    → 後半が別run(復刻・版元移管・接ぎ木)= edition-canonical 領域
  SCATTER  = 散在               → 版そのものの混線(edition-mix / run-split 領域)
★offender_nums は「**除去数が最小**になる側」であって「犯人」とは限らない。
  例 g-defend 通常版 = 新装一括36冊(#1-36 / 2014-15)+ 原版39冊(#37-75 / 2010-23) の合体だが、
  最小除去は #37-44 側になる。列は当たりを付けるヒントで、裁定は必ず巻一覧を見て行う。

■既知の偽陽性型(★自動是正禁止の理由)
 1. **同日一括登録の偽日付**: 取次/楽天由来で 1レーベル全巻が同一日になる型。同一日は
    区間が重なるので flag されないが、その塊の直後の1冊だけがズレて SINGLE に見える。
    → 列 `max_same_date` (同一版で同じ発売日を持つ巻の最大数) で見分ける。
 2. **正当な後追い刊行**: ワイド版/文庫の1-2巻だけが後年に出る(永遠の野原=NDL確認済の正史)。
    番号の小さい側が「後発」= 逆行に見えるが正しい。
 3. **重版日/刷日の混入**: 初版でなく重版日が入ると数日〜数ヶ月の逆行になる(T3の主成分)。
 4. **番外編/0巻/分冊**: number の振り方(0巻・上下巻)で前後する。
 5. **予約巻**: 未来日付の巻が先に入ると、その後に確定した巻が「逆行」に見える。

■是正先
  SINGLE で日付が明らかに誤り → 種4(volumes-supplement) or per-case 修正 → 「反映して」。
  BLOCK/SCATTER で版が混線 → `edition-canonical/*.yml` で版を再構築。
  ★本スクリプトは **検出と報告のみ**。データは一切書き換えない。

出力: docs/production-diagnostics/date-regression-small.tsv
入力: .cache/volume-flat.tsv (本番全巻のフラット展開。yml は舐めない)
"""
import csv
import os
import re
import sys
from calendar import monthrange
from collections import defaultdict
from datetime import date

sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10 ** 7)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, ".cache", "volume-flat.tsv")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "date-regression-small.tsv")
BIG = 1825  # 5年 = 既存検出器の担当


def span(rd):
    """発売日文字列 -> (lo_ordinal, hi_ordinal, 精度) 。解釈不能なら None。"""
    rd = (rd or "").strip()
    m = re.match(r"^(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?$", rd)
    if not m:
        return None
    y = int(m.group(1))
    if not (1900 <= y <= 2100):
        return None
    mo, da = m.group(2), m.group(3)
    try:
        if mo and da:
            d = date(y, int(mo), int(da))
            return (d.toordinal(), d.toordinal(), "D")
        if mo:
            mo = int(mo)
            last = monthrange(y, mo)[1]
            return (date(y, mo, 1).toordinal(), date(y, mo, last).toordinal(), "M")
        return (date(y, 1, 1).toordinal(), date(y, 12, 31).toordinal(), "Y")
    except ValueError:
        return None


# ---- 1パス読み込み: (slug, ed_idx) ごとに巻を集める ------------------------
eds = defaultdict(list)          # (slug, ed_idx) -> [vol dict]
meta = {}                        # (slug, ed_idx) -> 版メタ
nrow = nver = nskip = 0
with open(SRC, encoding="utf-8", newline="") as fp:
    for r in csv.DictReader(fp, delimiter="\t"):
        nrow += 1
        if r.get("is_version") == "1":     # 刷タブ(versions[])由来はミラー = 対象外
            nver += 1
            continue
        try:
            num = int(str(r["number"]).strip())
        except (ValueError, KeyError, TypeError):
            nskip += 1
            continue
        sp = span(r.get("release_date"))
        if sp is None:
            nskip += 1
            continue
        key = (r["slug"], r["ed_idx"])
        eds[key].append({
            "n": num, "lo": sp[0], "hi": sp[1], "prec": sp[2],
            "rd": r["release_date"], "isbn": (r.get("isbn13") or "").strip(),
        })
        if key not in meta:
            meta[key] = {
                "title": r.get("title", "") or "", "ed_type": r.get("ed_type", "") or "",
                "ed_label": r.get("ed_label", "") or "",
                "ed_imprint": r.get("ed_imprint", "") or "",
                "ed_publisher": r.get("ed_publisher", "") or "",
                "status": r.get("status", "") or "",
            }

print("読込 {:,}行 / versions除外 {:,} / 番号or日付なしskip {:,} / 対象版 {:,}".format(
    nrow, nver, nskip, len(eds)), flush=True)

# ---- 既存5年検出器の台帳(重複報告用) -------------------------------------
existing = set()
p5 = os.path.join(ROOT, "docs", "production-diagnostics", "vol-date-regression.tsv")
if os.path.exists(p5):
    with open(p5, encoding="utf-8") as fp:
        for r in csv.DictReader(fp, delimiter="\t"):
            existing.add(r.get("slug", ""))

rows = []
n_big = 0
for key, vols in eds.items():
    if len(vols) < 2:
        continue
    vols.sort(key=lambda v: (v["n"], v["lo"]))
    n = len(vols)
    # 確実な逆行ペア: i<j(番号昇順) で lo_i - hi_j >= 1
    pairs = []
    for i in range(n):
        loi = vols[i]["lo"]
        ni = vols[i]["n"]
        for j in range(i + 1, n):
            if ni == vols[j]["n"]:
                continue                       # 同番号(上下巻・重複)は比較しない
            d = loi - vols[j]["hi"]
            if d >= 1:
                pairs.append((d, i, j))
    if not pairs:
        continue
    worst = max(pairs, key=lambda t: t[0])
    if worst[0] >= BIG:
        n_big += 1
        continue                                # 5年以上 = 既存検出器の担当

    # offenders: 逆行ペアが消えるまで「最も多くのペアに関与する巻」を貪欲に除去
    remain = list(pairs)
    offenders = []
    while remain:
        cnt = defaultdict(int)
        for _, i, j in remain:
            cnt[i] += 1
            cnt[j] += 1
        pick = max(cnt.items(), key=lambda kv: (kv[1], -vols[kv[0]]["n"]))[0]
        offenders.append(pick)
        remain = [p for p in remain if p[1] != pick and p[2] != pick]
    offenders.sort()
    if len(offenders) == 1:
        shape = "SINGLE"
    elif offenders == list(range(offenders[0], offenders[-1] + 1)):
        shape = "BLOCK"
    else:
        shape = "SCATTER"

    # 同一発売日の集中(= 一括登録の偽日付シグナル)
    dc = defaultdict(int)
    for v in vols:
        dc[v["rd"]] += 1
    max_same = max(dc.values())

    d, i, j = worst
    a, b = vols[i], vols[j]
    days = d
    tier = ("T1_1年以上" if days >= 365 else
            "T2_3か月以上" if days >= 90 else "T3_1日以上")
    m = meta[key]
    rows.append({
        "tier": tier,
        "worst_days": days,
        "shape": shape,
        "slug": key[0],
        "title": m["title"][:40],
        "ed_idx": key[1],
        "ed_type": m["ed_type"],
        "ed_label": m["ed_label"],
        "ed_imprint": m["ed_imprint"],
        "publisher": m["ed_publisher"],
        "status": m["status"],
        "n_vols": n,
        "n_pairs": len(pairs),
        "n_offenders": len(offenders),
        "offender_nums": ",".join(str(vols[k]["n"]) for k in offenders[:8]),
        "worst_pair": "{}巻({})→{}巻({})".format(a["n"], a["rd"], b["n"], b["rd"]),
        "prec": "{}/{}".format(a["prec"], b["prec"]),
        "isbn_pattern": "{}→{}".format("有" if a["isbn"] else "無", "有" if b["isbn"] else "無"),
        "isbn_pub_code": "{}/{}".format(a["isbn"][3:8] if a["isbn"] else "-",
                                        b["isbn"][3:8] if b["isbn"] else "-"),
        "max_same_date": max_same,
        "in_5y_ledger": "yes" if key[0] in existing else "",
    })

rows.sort(key=lambda r: (-r["worst_days"], r["slug"]))
cols = ["tier", "worst_days", "shape", "slug", "title", "ed_idx", "ed_type", "ed_label",
        "ed_imprint", "publisher", "status", "n_vols", "n_pairs", "n_offenders",
        "offender_nums", "worst_pair", "prec", "isbn_pattern", "isbn_pub_code",
        "max_same_date", "in_5y_ledger"]
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8", newline="") as fp:
    w = csv.DictWriter(fp, fieldnames=cols, delimiter="\t")
    w.writeheader()
    w.writerows(rows)


# ---- 集計 -----------------------------------------------------------------
def tally(f):
    c = defaultdict(int)
    for r in rows:
        c[f(r)] += 1
    return c


print("\nflag: {:,}版 / {:,}頁  -> {}".format(
    len(rows), len({r["slug"] for r in rows}), OUT))
print("(5年以上=既存担当のため除外: {}版)".format(n_big))
print("\n=== 逆行幅の階層 ===")
tt = tally(lambda r: r["tier"])
for k in ["T1_1年以上", "T2_3か月以上", "T3_1日以上"]:
    pg = len({r["slug"] for r in rows if r["tier"] == k})
    print("  {:12s} {:6,}版 / {:6,}頁".format(k, tt[k], pg))
print("\n=== 形 ===")
for k, v in sorted(tally(lambda r: r["shape"]).items(), key=lambda kv: -kv[1]):
    print("  {:8s} {:6,}".format(k, v))
print("\n=== 版種 ===")
for k, v in sorted(tally(lambda r: r["ed_type"]).items(), key=lambda kv: -kv[1])[:10]:
    print("  {:14s} {:6,}".format(k, v))
print("\n=== T1(1年以上) 上位30 ===")
for r in [x for x in rows if x["tier"] == "T1_1年以上"][:30]:
    print("  {:5d}日 {:7s} {:30s} [{}] {} {} 同日{}".format(
        r["worst_days"], r["shape"], r["slug"][:30], r["ed_label"][:10],
        r["worst_pair"], r["isbn_pattern"], r["max_same_date"]))
