"""★発売日の「値そのもの」の異常監査 (family = date-outlier)。

既存の date 系監査 (_audit-date-disorder / _audit-date-order / _audit-vol-date-regression) は
すべて **巻どうしの相対的な並び順** (逆行) を見ている。本監査はそれとは直交して、
**1つの値が単体で・あるいは同一版内の分布として ありえないか** を見る。

--- 検出する型 -------------------------------------------------------------
FORMAT_BAD      形式異常。月00/13・日32・2月30日・年が4桁でない・年<1900 or >2100。
                → 実測 0件。本番は完全に正規化済み。**恒久的な番人**として残す。
FUTURE_FAR      今日+2年より先。予約(発売前)は正当に未来日付を持つので2年を境にする。
                → 実測 0件(最大は2027年)。これも番人。
PRE_ISBN_ERA    ISBN13を持つのに発売日が日本のISBN導入前(日本図書コード=1981-01)。
                ★検証の結果 **日付はほぼ常に正しい** (ブラック・ジャック1974-05-20/海のオーロラ
                1978-08-15 とも楽天・史実と一致)。ISBNの方が「後の刷に遡って採番されたもの」。
                よって **日付の誤りではない**=情報段。価格/書影/在庫をこのISBNに紐づける時の
                注意喚起としてのみ使う。
BULK_SAME_DATE_ALL   同一版の全巻(異なる巻番号4つ以上)が **まったく同じ発売日**。
BULK_SAME_DATE_PART  同一版で4巻以上が1つの日付に固まり、残りの巻は散らばっている
                (=残りが散っている分だけ、固まりの方が異常だと言える。ALLより強い)。
                ★これがCLAUDE.mdの「一括登録の偽日付」型。取次/楽天/MADBが刊行期間の
                実日付を持たず、レーベル一括登録の1日を全巻に配ったもの。
PRECISION_Y_ONLY  同一版の多数がYYYY-MM-DDなのに、その巻だけ年しか無い(値の精度欠落)。
BEFORE_SERIES_START 巻の発売年が、その頁の year_started より2年以上前。
                ★注意=大半は **日付でなく year_started(種3)の方が誤り** (手塚治虫漫画全集型)。
                INFO段として出すだけ。日付を直す根拠にはしない。
ANCIENT         発売年<1946。実測45件は のらくろ/一平全集/漫画吾輩は猫である 等
                **実在する戦前漫画**。INFO段。年が古いこと自体は異常でない。

--- 既知の偽陽性(=検出器に入れなかったもの) --------------------------------
★**全DBで同じ日に大量発売されるのは日本では正常**。2024-09-06=534巻、2024-12-27=300巻 等の
  「日単位の全体スパイク」は 講談社/集英社/小学館 の一斉発売日であって異常でない。
  よって **グローバルな日付頻度は一切見ない**。見るのは常に「同一版の中の分布」に閉じる。
★ISBNの連番具合だけでは同時刊行と通常刊行を **区別できない** (出版社は連載シリーズにも連番
  ブロックを前もって確保するため。日本の歴史[同時20冊]も 翔んだカップル[逐次10冊]も spread=n-1)。
  ただし逆向きには効く= **連番が飛んでいれば別時期の採番=同日発売はありえない**。参考列に出す。
★BULK_SAME_DATE の正当例 = ①学習まんが/全集/文庫の **全巻同時刊行** (学研まんがNEW世界の歴史
  12冊、集英社 日本の歴史20冊、講談社漫画文庫 君の手がささやいている5冊)
  ②★**版元移管・レーベル継承による既刊一斉再刊** (雨柳堂夢咄1-11巻=朝日ソノラマ廃業に伴い
  2007-10に朝日新聞社から一斉再刊。楽天も同月で一致)。**自動是正は禁止**。

--- ★裏取り: --rakuten (単一パス) ------------------------------------------
BULK候補は機械だけでは同時刊行と偽日付を分けられない。そこで .cache/rakuten-isbn-delta.jsonl
を **1パスだけ** 走査し、固まりの各ISBNの salesDate を引いて verdict を付ける:
  RAKUTEN_SPREAD  楽天は同じISBN群を複数の月に散らす → **DBの同一日付は偽で確定**(最強)
  RAKUTEN_AGREE   楽天も同一月 → 同時刊行らしい(偽陽性寄り)
  RAKUTEN_OTHER   楽天も同一だがDBと別の月 → どちらかが誤り(中)
  NO_RAKUTEN      楽天に無い(古書/学習まんが等) → 人手かNDLで裏取り
実測(2026-08-29): SPREAD 18 / AGREE 112 / OTHER 36 / NO_RAKUTEN 37。

--- 是正先 -----------------------------------------------------------------
日付の値そのものを直すのは種4(volumes-supplement)か edition-canonical。
BULK_SAME_DATE は外部権威(NDL 出版年月 / Wikipedia刊行リスト)での裏取りが必須で、
機械一括置換は禁止(偽日付を別の偽日付に替えるだけになる)。

入力 : .cache/volume-flat.tsv (本番全巻フラット / is_version=1 は既定で除外)
出力 : docs/production-diagnostics/date-outlier.tsv
"""
import argparse
import collections
import csv
import datetime
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, ".cache", "volume-flat.tsv")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "date-outlier.tsv")

TODAY = datetime.date(2026, 8, 29)
FUTURE_LIMIT = TODAY.replace(year=TODAY.year + 2).isoformat()  # これより先は異常
ISBN_ERA_HARD = 1975   # 日本でISBNが存在し得ない
ISBN_ERA_SOFT = 1980   # 日本図書コード導入=1981-01
ANCIENT_YEAR = 1946
BULK_MIN = 4           # 同一版で同一日付を共有する「異なる巻番号」の下限
RAKUTEN = os.path.join(ROOT, ".cache", "rakuten-isbn-delta.jsonl")


def rakuten_months(isbns):
    """楽天キャッシュを1パスだけ走査し {isbn: 'YYYY-MM'} を返す。"""
    want = set(isbns)
    got = {}
    if not os.path.exists(RAKUTEN):
        print("  ! 楽天キャッシュ不在: {}".format(RAKUTEN), flush=True)
        return got
    for line in open(RAKUTEN, encoding="utf-8"):
        i = line.find('"isbn":')
        if i < 0:
            continue
        j = line.find('"', i + 7)
        k = line.find('"', j + 1)
        if line[j + 1:k] not in want:
            continue
        try:
            o = json.loads(line)
        except ValueError:
            continue
        sd = (o.get("item") or {}).get("salesDate") or ""
        m = re.match(r"(\d{4})年(\d{2})月", sd)
        if m:
            got[str(o.get("isbn"))] = m.group(1) + "-" + m.group(2)
    return got


def parse(d):
    """(ok, year, precision) を返す。precision: 1=年 2=年月 3=年月日 / 0=無効。"""
    if not d:
        return None, None, 0
    m = re.fullmatch(r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", d)
    if not m:
        return False, None, 0
    y = int(m.group(1))
    mo, da = m.group(2), m.group(3)
    if y < 1900 or y > 2100:
        return False, y, 0
    prec = 3 if da else (2 if mo else 1)
    if mo is not None and not (1 <= int(mo) <= 12):
        return False, y, prec
    if da is not None:
        try:
            datetime.date(y, int(mo), int(da))
        except ValueError:
            return False, y, prec
    return True, y, prec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rakuten", action="store_true",
                    help="楽天キャッシュを1パス走査してBULK候補にverdictを付ける(重い)")
    args = ap.parse_args()
    rows = [r for r in csv.DictReader(open(SRC, encoding="utf-8", newline=""), delimiter="\t")
            if r["is_version"] != "1"]
    print("読込 {:,}巻 (is_version除外後) / {:,}頁".format(
        len(rows), len(set(r["slug"] for r in rows))), flush=True)

    out = []

    def add(cls, sev, r, date, n, detail, nums="", extra="", isbns=None):
        d = {
            "class": cls, "severity": sev, "slug": r["slug"], "title": r["title"][:40],
            "ed_idx": r["ed_idx"], "ed_label": r["ed_label"], "ed_imprint": r["ed_imprint"],
            "ed_publisher": r["ed_publisher"], "n_vols": n, "numbers": nums,
            "date": date, "verdict": "", "detail": detail, "extra": extra,
        }
        if isbns:
            d["_isbns"] = isbns
        out.append(d)
        return d

    # ---- 巻単位の検査 ----
    for r in rows:
        d = (r["release_date"] or "").strip()
        ok, y, prec = parse(d)
        if ok is False:
            add("FORMAT_BAD", "確実", r, d, 1, "形式異常/存在しない日付", r["number"], r["isbn13"])
            continue
        if ok is None:
            continue  # 空欄は本family外(= missing-isbn/loss 系の担当)
        if d > FUTURE_LIMIT[:len(d)]:
            add("FUTURE_FAR", "確実", r, d, 1,
                "今日+2年({})より先".format(FUTURE_LIMIT), r["number"], r["isbn13"])
        if r["isbn13"] and y <= ISBN_ERA_SOFT:
            add("PRE_ISBN_ERA", "情報", r, d, 1,
                "ISBN有なのに{}年(ISBN導入=1981-01)。★検証済=日付は正・ISBNが後刷り由来".format(y),
                r["number"], r["isbn13"])
        if y < ANCIENT_YEAR:
            add("ANCIENT", "情報", r, d, 1,
                "{}年=戦前。実在の戦前漫画が大半".format(y), r["number"], r["isbn13"])
        ys = r["year_started"]
        if ys.isdigit() and y is not None and int(ys) - y >= 2:
            add("BEFORE_SERIES_START", "情報", r, d, 1,
                "year_started={} より{}年前。★大半は year_started 側の誤り".format(ys, int(ys) - y),
                r["number"], r["isbn13"])

    # ---- 版単位の検査 ----
    ed = collections.defaultdict(list)
    for r in rows:
        ed[(r["slug"], r["ed_idx"])].append(r)

    for key, vs in ed.items():
        dated = [x for x in vs if x["release_date"] and parse(x["release_date"])[0]]
        if len(dated) < BULK_MIN:
            continue
        cnt = collections.Counter(x["release_date"] for x in dated)
        top_date, top_n = cnt.most_common(1)[0]
        clump = [x for x in dated if x["release_date"] == top_date]
        nums = sorted(set(x["number"] for x in clump if x["number"]))
        if len(nums) >= BULK_MIN:
            whole = (top_n == len(dated))
            cls = "BULK_SAME_DATE_ALL" if whole else "BULK_SAME_DATE_PART"
            if whole:
                sev = "高" if len(nums) >= 8 else "要確認"
            else:
                sev = "高" if len(nums) >= 6 else "要確認"
            spread = ""
            ib = sorted(int(x["isbn13"][4:12]) for x in clump
                        if x["isbn13"] and x["isbn13"].startswith("9784"))
            if len(ib) >= 3:
                spread = "isbn連番幅={}/{}冊".format(ib[-1] - ib[0], len(ib))
            if len(ib) >= 3 and (ib[-1] - ib[0]) >= (len(ib) - 1) * 2:
                spread += " ★連番飛び=別時期採番"
                sev = "高"
            rest = "版の全巻が同日" if whole else "他{}巻は別日付".format(len(dated) - top_n)
            add(cls, sev, clump[0], top_date, len(nums),
                "{}巻が同一発売日。{}".format(len(nums), rest),
                ",".join(nums[:14]) + ("…" if len(nums) > 14 else ""), spread,
                isbns=[x["isbn13"] for x in clump if x["isbn13"]])

        # 精度欠落: 年だけの巻が、日まで在る版の中に混じる
        precs = [parse(x["release_date"])[2] for x in dated]
        if 1 in precs and max(precs) >= 3 and precs.count(1) <= len(precs) * 0.34:
            for x in dated:
                if parse(x["release_date"])[2] == 1:
                    add("PRECISION_Y_ONLY", "要確認", x, x["release_date"], 1,
                        "同版{}巻中この巻だけ年のみ(他は年月日)".format(len(dated)),
                        x["number"], x["isbn13"])

    # ---- 楽天による裏取り(opt-in / 単一パス) ----
    if args.rakuten:
        bulk = [r for r in out if r["class"].startswith("BULK")]
        allisbn = [i for r in bulk for i in r.get("_isbns", [])]
        print("楽天キャッシュを1パス走査 (BULK {}件 / ISBN {}件)…".format(
            len(bulk), len(allisbn)), flush=True)
        mon = rakuten_months(allisbn)
        for r in bulk:
            ms = [mon[i] for i in r.get("_isbns", []) if i in mon]
            if len(ms) < 3:
                r["verdict"] = "NO_RAKUTEN"
                continue
            u = set(ms)
            if len(u) > 1:
                r["verdict"] = "RAKUTEN_SPREAD({}種:{})".format(
                    len(u), ",".join(sorted(u)[:5]))
                r["severity"] = "確実"
            elif list(u)[0] == r["date"][:7]:
                r["verdict"] = "RAKUTEN_AGREE"
                r["severity"] = "情報"
            else:
                r["verdict"] = "RAKUTEN_OTHER({})".format(list(u)[0])
                r["severity"] = "要確認"

    for r in out:
        r.pop("_isbns", None)

    order = {"確実": 0, "高": 1, "要確認": 2, "情報": 3}
    out.sort(key=lambda r: (order.get(r["severity"], 9), r["class"], -int(r["n_vols"]), r["slug"]))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    cols = ["class", "severity", "slug", "title", "ed_idx", "ed_label", "ed_imprint",
            "ed_publisher", "n_vols", "numbers", "date", "verdict", "detail", "extra"]
    with open(OUT, "w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=cols, delimiter="\t")
        w.writeheader()
        w.writerows(out)

    print("\nflag {:,}件 -> {}\n".format(len(out), OUT), flush=True)
    bc = collections.Counter(r["class"] for r in out)
    bs = collections.Counter(r["severity"] for r in out)
    for k in ["FORMAT_BAD", "FUTURE_FAR", "PRE_ISBN_ERA", "BULK_SAME_DATE_PART",
              "BULK_SAME_DATE_ALL", "PRECISION_Y_ONLY", "BEFORE_SERIES_START", "ANCIENT"]:
        print("  {:22s} {:>6,}".format(k, bc.get(k, 0)))
    print("  ---")
    for k in ["確実", "高", "要確認", "情報"]:
        print("  {:10s} {:>6,}".format(k, bs.get(k, 0)))
    bulk = [x for x in out if x["class"].startswith("BULK")]
    if any(x["verdict"] for x in bulk):
        print("  --- BULK verdict (--rakuten) ---")
        for k, n in collections.Counter(
                x["verdict"].split("(")[0] for x in bulk).most_common():
            print("  {:16s} {:>6,}".format(k, n))
    print("")
    print("=== BULK_SAME_DATE (重い順) ===", flush=True)
    for r in bulk[:30]:
        print("  {:4s} {:>3}巻 {:10s} {:34s} {:20s} {}".format(
            r["class"][-4:], r["n_vols"], r["date"], r["slug"][:34],
            r["title"][:20], r["verdict"][:54] or r["ed_imprint"][:20]))


if __name__ == "__main__":
    main()
