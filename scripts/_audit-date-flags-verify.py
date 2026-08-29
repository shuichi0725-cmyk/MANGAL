"""★date系2検出器(date-outlier / date-bulk-registered)の **反証(偽陽性抑制)** レイヤ。

【何を・なぜ】
`_audit-date-outlier.py` と `_audit-date-bulk-registered.py` は「同一版の複数巻が同じ発売日」を
異常として上げる。だが日本の漫画出版では **同日一斉刊行が構造的に普通** に起きる:
  ①文庫/愛蔵版/復刻BOXの全巻同時刊行 ②版元移管・レーベル継承による既刊一斉再刊
  ③改題/アニメ化タイアップの既刊一斉再刊 ④完結済みWeb作品の全巻同時商業化
無作為16件(両検出器から各8件)を raw yml + 楽天キャッシュで裏取りした結果、
actionable段(確実/高/要確認・BROKEN/HIGH/MED)の **本物は16件中3件** しか無かった。
本script は「機械で確実に偽陽性と言える型」だけを列挙し、降格候補として出す。
★本script はデータを一切変更しない。既存TSVを読み、降格/再検査の候補を別TSVに書くだけ。

【出す型】
 A RK_MONTH_BOUNDARY   (outlier) 楽天の散りが隣接月のみ かつ DBの月がその範囲内。
                        = 月末発売を翌月表記にしただけの境界ノイズ。「確実」の根拠にならない。
                        実測: 確実19行のうち5行(taiman-buruusu/taraobannai/captain/
                        samurai-giants/mitsumegatooru)がこれだけを根拠にしている。
 B PRECISION_MULTI     (outlier) PRECISION_Y_ONLY で 同一版に年のみ巻が複数。
                        detail の「この巻だけ年のみ」が事実に反する。実測 28行中13行。
                        さらに巻の年<1985 なら当時のMADB記録の粒度そのもの=異常でない。
 C RK_CONFIRMS_SIMUL   (bulk) 楽天が独立に「1種類の日付」を返し DBとのズレ<=1ヶ月。
                        = 外部ソースが同日一斉刊行を裏書き。偽日付ではない。実測 actionable
                        93行中 **50行(54%)**。雨柳堂夢咄(朝日ソノラマ移管)・熱愛プリンス・
                        サザエさん朝日文庫 など、両検出器のdocstringが自ら「正当」と書いた
                        ケースがそのまま残っている。
 D PRE_SERIAL_BAD_YS   (bulk) PRE_SERIAL の根拠 year_started より、その頁の**最古巻**が前。
                        = 誤っているのは日付でなく year_started(種3)。outlier検出器は同じ型を
                        BEFORE_SERIES_START として自ら情報段に落としている(632行)。
                        bulk側だけ BROKEN に上げているのは不整合。実測 1/1行。
 E DEGENERATE_ED_BATCH (bulk) ED_REGULAR_BATCH の降格根拠 ed_batch は「版の日付グループの
                        中央値」。塊==版全体 のとき ed_batch==n が自明に成立し、降格が
                        無条件で発火する。実測 85行中72行(85%)がこの自明ケース。
                        = 「版がまとめ配本体質」の証明になっていない。再検査対象。
 F RK_STAGGERED_IN_LOW (bulk) LOW なのに楽天が3種以上・巻順に単調増加=本物の刊行列。
                        取りこぼし(false negative)候補。実測2行
                        (jungle-shounen-jan-bangaihen は raw検証で本物と確認)。

【既知の偽陽性(=本scriptが逆に見逃す型)】
 ・楽天 salesDate が重版日のとき「1種類」に見えることがある(はだしのゲン=2014/2020型)。
   C は DBとのズレ<=1ヶ月に限定しているので重版日は入らないが、絶対ではない。
 ・A は「DBが1ヶ月ずれている」こと自体は否定しない。値の精度を直したい場合は残る。

【是正先】
 本script の出力は seed を直すものではない。上流2検出器の **severity 付けの是正** に使う。
 日付の値を直す時は edition-canonical(SRC slug) / 種4。裏取りは NDL 奥付が ground truth。

入力: docs/production-diagnostics/date-outlier.tsv
      docs/production-diagnostics/date-bulk-registered.tsv
      .cache/volume-flat.tsv (D の判定のみ)
出力: docs/production-diagnostics/date-flags-verify.tsv (read-only 診断)
"""
import csv
import os
import re
import sys
import collections

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIAG = os.path.join(ROOT, "docs", "production-diagnostics")
OUTL = os.path.join(DIAG, "date-outlier.tsv")
BULK = os.path.join(DIAG, "date-bulk-registered.tsv")
FLAT = os.path.join(ROOT, ".cache", "volume-flat.tsv")
OUT = os.path.join(DIAG, "date-flags-verify.tsv")


def _i(x):
    try:
        return int(float(x))
    except Exception:
        return 0


def _read(p):
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _months(s):
    return [int(a) * 12 + int(b) for a, b in re.findall(r"(\d{4})-(\d{2})", s)]


def main():
    out = []
    # ---------- outlier ----------
    orows = _read(OUTL)
    prec = collections.Counter(
        (r["slug"], r["ed_idx"]) for r in orows if r["class"] == "PRECISION_Y_ONLY")
    for r in orows:
        v = r.get("verdict", "")
        if v.startswith("RAKUTEN_SPREAD"):
            ms = _months(v)
            db = _months(r["date"])
            if len(ms) >= 2 and max(ms) - min(ms) <= 1 and db and min(ms) <= db[0] <= max(ms):
                out.append(["A_RK_MONTH_BOUNDARY", "date-outlier", r["severity"], "要確認",
                            r["slug"], r["ed_idx"], r["date"], r["n_vols"],
                            f"楽天の散りが隣接月のみ({v})でDBの月もその範囲内=月末発売の翌月表記。確実の根拠にならない"])
        if r["class"] == "PRECISION_Y_ONLY":
            k = (r["slug"], r["ed_idx"])
            why = []
            if prec[k] > 1:
                why.append(f"同一版に年のみ巻が{prec[k]}件=detailの『この巻だけ』が事実に反する")
            y = _i(r["date"][:4])
            if y and y < 1985:
                why.append(f"{y}年=当時のMADB記録の粒度(年のみ)であって値の異常でない")
            if why:
                out.append(["B_PRECISION_MULTI", "date-outlier", r["severity"], "情報",
                            r["slug"], r["ed_idx"], r["date"], r["n_vols"], " / ".join(why)])

    # ---------- bulk ----------
    brows = _read(BULK)
    # D 用: 頁ごとの最古巻年
    need_ys = {r["slug"] for r in brows if r["kind"] == "PRE_SERIAL"}
    minyear = {}
    if need_ys and os.path.exists(FLAT):
        with open(FLAT, encoding="utf-8") as f:
            for rec in csv.DictReader(f, delimiter="\t"):
                if rec["slug"] not in need_ys or rec.get("is_version") == "1":
                    continue
                y = _i((rec.get("release_date") or "")[:4])
                if y:
                    minyear[rec["slug"]] = min(minyear.get(rec["slug"], 9999), y)

    for r in brows:
        sev, kind = r["severity"], r["kind"]
        if sev in ("BROKEN", "HIGH", "MED") and _i(r["rk_distinct"]) == 1 \
                and abs(_i(r["rk_offset_mo"])) <= 1:
            out.append(["C_RK_CONFIRMS_SIMUL", "date-bulk-registered", sev, "LOW",
                        r["slug"], r["ed_idx"], r["date"], r["n"],
                        f"楽天が独立に1種類の日付を返しズレ{r['rk_offset_mo']}ヶ月=同日一斉刊行を外部が裏書き ({r['rakuten_dates'][:70]})"])
        if kind == "PRE_SERIAL":
            my = minyear.get(r["slug"])
            ys = _i(r["year_started"])
            if my and ys and my < ys:
                out.append(["D_PRE_SERIAL_BAD_YS", "date-bulk-registered", sev, "別family(種3)",
                            r["slug"], r["ed_idx"], r["date"], r["n"],
                            f"頁の最古巻={my}年 < year_started={ys} = 誤っているのは日付でなくyear_started。outlier側は同型をBEFORE_SERIES_STARTとして情報段に落としている"])
        if kind == "ED_REGULAR_BATCH" and _i(r["n"]) == _i(r["ed_vols"]):
            out.append(["E_DEGENERATE_ED_BATCH", "date-bulk-registered", sev, "再検査",
                        r["slug"], r["ed_idx"], r["date"], r["n"],
                        f"塊が版全体(n={r['n']}=ed_vols)なので ed_batch が自明に n と等しくなり降格が無条件発火。まとめ配本体質の証明になっていない"])
        if sev == "LOW" and _i(r["rk_distinct"]) >= 3 and r["rk_mono"] == "1":
            out.append(["F_RK_STAGGERED_IN_LOW", "date-bulk-registered", sev, "昇格候補",
                        r["slug"], r["ed_idx"], r["date"], r["n"],
                        f"LOWだが楽天が3種以上を巻順単調増加で返す=本物の刊行列 ({r['rakuten_dates'][:70]})"])

    order = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5}
    out.sort(key=lambda x: (order[x[0][0]], x[4]))
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["rule", "family", "now_severity", "should_be",
                    "slug", "ed_idx", "date", "n", "why"])
        w.writerows(out)
    print("wrote", OUT, len(out), "rows")
    for k, v in sorted(collections.Counter(x[0] for x in out).items()):
        print("  ", k, v)


if __name__ == "__main__":
    main()
