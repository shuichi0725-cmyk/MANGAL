"""★取次一括登録の偽日付 監査 (= key: date-bulk-registered)。

【何を見るか】
同一版(edition)の中で **同じ release_date が3巻以上に集中** している塊(cluster)を検出する。
実際には数年かけて刊行されたはずの巻が、取次/書店DBへ**まとめて登録**された結果、
全部が同じ「登録日」に化けている型。
★ユーザ実例: あるレーベル全6巻が実際は 1986-09〜1987-02 なのに、楽天も紀伊國屋も
  全部『1990年7月』を返した(= 外部ソースにも同じ偽日付が伝播している)。

【なぜ既存検出器で拾えないか】
既存の日付系(_audit-date-disorder / _audit-date-order / _audit-vol-date-regression)は
すべて **「巻番号が進むのに日付が戻る」= 順序違反** を見る。一括登録は全巻が同じ日なので
順序違反を一切起こさない(単調非減少)。したがって構造的に既存の網をすり抜ける。
_audit-volume-gaps / _audit-large-gaps は巻の欠落、_audit-publisher-vs-isbn は社名。
いずれも「日付が潰れている」ことは見ていない。

【判定に使う信号(すべてローカル・外部API不使用)】
  n        = 同一版内で同じ日付を持つ巻数 (>=3 が対象)
  frac     = n / その版の巻数。1.0 = 版まるごと1日に潰れている(FLAT_RUN)
  cadence  = その版が実際に観測している「1巻あたり何ヶ月」(日付の張る幅 / 巻数)
  span_m   = (n-1) * cadence = 本来この n 巻が跨ぐはずの月数。大きいほど不自然
  serial   = 頁の year_started..year_ended(連載期間)。連載3年以上なのに版が1日 = 破損
  event    = 同じ (imprint, date) に **別のシリーズも3巻以上の塊** を持つか
             = レーベル単位の一括登録イベント(例 眠れぬ夜の奇妙な話コミックス 2007-10)
  isbn_blk = 塊内ISBNの出版者記号内シリアルが連番か
             ★連番 = 同時発売のために採番された1ブロック(= 正当な一挙刊行の傍証)
             ★飛び飛び = 別々の時期に採番された本が同じ日付を名乗っている(= 偽日付の傍証)
  future   = 塊の日付が未来(実行日基準)
  ★nbr    = **ISBN近傍テーブル**(= 本familyの本命判定)。出版者記号ごとに
             「タイトル記号(シリアル) -> 発売月」を全DB分作り、塊のシリアル範囲の近傍に居る
             **他作品**の日付を見る。
               (a1) 近傍も同じ日に固まる → その日はレーベルの一斉出荷日 = **正当**
                   (パンローリング マンガショップ / ソノラマコミック文庫の創刊 /
                    赤塚不二夫漫画大全集 など)
               (a2) 近傍の**他作品も自分の巻を1日にまとめている**(label_ships_whole)
                    → そのレーベルは「1タイトル丸ごと同日出荷」する体質 = **正当**
                    (集英社 Personal you: ぽっかぽか4巻=1995-08 / 新編闇の果てから3巻=1996-03)
               (b) 近傍が散る → シリアルは時間とともに払い出される。
                   local_rate(serial/月) で塊のシリアル幅を割ると
                   **implied_months = この塊の本が実際には何ヶ月かけて登録されたか**。
                   implied_months が大きいのに日付が1点 = 偽日付の直接証明。
             ★前提: 塊のシリアルが「連番の予約ブロック」でないこと(isbn_proof_ok)。
               出版社はシリーズ用にシリアルをまとめて予約するので、幅≒巻数の連番塊は
               何ヶ月かけて出しても連番になり、払い出し速度からは何も言えない。
               幅が巻数の3倍以上に散り、かつ塊のシリアルの「間」に他作品が3つ以上
               挟まっている塊にだけこの証明を適用する
               (サザエさん朝日文庫 = 全45巻分のISBNを巻番号順に予約し実際は月4冊ずつ配本。
                幅は広いが間に他作品が居ないので証明不可)。

【重症度と型】
  BROKEN  ISBN_SPREAD_PROOF = ISBN近傍の払い出し速度から、この塊は実際には9ヶ月以上かけて
                              登録されたと判る。外部ソース不要の機械証明
          RAKUTEN_STAGGERED = 楽天が「巻順に単調増加する本物の刊行列」を返しているのに
                              本番は全巻同じ日 → 本番の同一日が偽。★最強の証拠
          RAKUTEN_CONFLICT  = 楽天が3種以上・6ヶ月以上に散る(単調でない=重版混じり)
          PRE_SERIAL        = 塊の日付が連載開始年より前(物理的にあり得ない)
  HIGH    FUTURE(未来日に3巻以上) / 楽天2種以上3ヶ月以上 /
          FLAT_RUN(版まるごと1日 かつ 連載3年以上) / EVENT_BULK(レーベル一括登録の構成員)
  HIGH(続) ISBN_SPREAD(implied_months>=4)
  MED     PLACEHOLDER_DATE(12-31 / 01-01 = 年しか判らない本に機械で付けた既定日) /
          RAKUTEN_WIDE(楽天が散りすぎ=重版日付の疑い。証拠として弱い) /
          FLAT_RUN(4巻以上) / PARTIAL_BULK(本来 span_m>=12ヶ月相当)
  LOW     PUBLISHER_BATCH(近傍の6割以上が同じ日 = レーベル一斉出荷日、または近傍の
                          複数巻作品の6割以上が全巻同日 = レーベル体質。いずれも正当) /
          SMALL_BATCH(同月まとめ出し等・正当の可能性が高い)

【既知の偽陽性(= 自動是正禁止)】
  ・学習まんが/全集/BOXの**同時発売**: 「角川まんが学習シリーズ 日本の歴史 全15巻」は
    実際に 2015-06-30 に全巻同時発売。ISBNも連番。 → isbn_blk が連番になり legit_hint に出る。
  ・文庫/愛蔵版/完全版の一挙刊行: 復刊は月1〜2冊でなく一気に出ることがある。
  ・上下巻・前後編の同日発売(n=2)は最初から対象外。
  ・「YYYY」だけの粗い日付(1980年代以前)は元から日単位が無いだけで一括登録ではない
    → gran=year は LOW 止まりにする。
  ・予約(未来日)の新刊が数巻まとめて告知されることはある。
  ・★**版自身がまとめ配本体質**: ちばてつや全集(ホーム社)は1997年に毎月3冊ずつ21巻を配本した。
    19-21巻が同じ1997-10なのは正常 → ed_batch(版の日付グループ大きさの中央値)以下の塊は落とす。
  ・★**文庫レーベルは創刊時に1タイトルを大量同日投入する**: 秋田文庫はブラック・ジャック12冊/
    ドカベン6冊を創刊時に同日出荷。小学館文庫も1タイトル丸ごと同日。
    → label_ships_whole(近傍の複数巻作品の半数以上が全巻同日)で落とす。
    ★この時 楽天が返す1995年等の日付は**重版日**であって反証にならない。
      楽天を反証に使うのは「巻順に単調増加(rk_mono)」の時だけに限る。
  ・★**楽天 salesDate は「重版・新装版の日付」のことがある**。ゲゲゲの鬼太郎(講談社コミックス)は
    本番が 1985-09..1986-01 の月次なのに楽天が 2018-2019 を返す = 2018年の重版日付。
    散りが刊行ペースとして非現実的(> max(24, n*18)ヶ月)なものは RAKUTEN_WIDE として
    証拠から外す。 はだしのゲン(2014/2020)も同型。
  ・楽天と本番のズレが1〜2ヶ月なのは「取次搬入日 vs 発売日」の差。3ヶ月未満は衝突扱いしない。

【是正先】
  seed を直すのはこの検出器の役目ではない。日付の是正は
  ・版まるごとが偽 → `data/seeds/edition-canonical/<SRC slug>.yml` に正しい巻×日付を書く
    (★canonicalキーは SRC slug。 edition-overrides は公開slug = 逆なので取り違え注意)
  ・一部の巻だけ → `data/seeds/volumes-supplement.yml`(種4)or per-case
  裏取りは NDL(奥付発行年月)が ground truth。楽天/紀伊國屋は同じ偽日付を持ちうるので
  **単独では根拠にならない**。

出力: docs/production-diagnostics/date-bulk-registered.tsv (read-only。本番は一切変更しない)
usage: python scripts/_audit-date-bulk-registered.py [--rakuten]
       --rakuten = .cache/rakuten-isbn-delta.jsonl を1パス走査し、塊のISBNに対する
                   楽天 salesDate が「バラけているか」を照合列として付ける(任意)。
"""
import argparse
import bisect
import collections
import csv
import datetime
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10 ** 9)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAT = os.path.join(ROOT, ".cache", "volume-flat.tsv")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "date-bulk-registered.tsv")
RAKUTEN = os.path.join(ROOT, ".cache", "rakuten-isbn-delta.jsonl")

MIN_N = 3
TODAY = datetime.date.today()
TODAY_M = TODAY.year * 12 + TODAY.month - 1

ap = argparse.ArgumentParser()
ap.add_argument("--rakuten", action="store_true", help="楽天キャッシュ1パスで salesDate 照合列を付ける")
ARGS = ap.parse_args()

# 正当な「一挙刊行」が起きやすい語(偽陽性ヒント。dropの根拠にはしない)
LEGIT_RE = re.compile("学習|学研まんが|日本の歴史|世界の歴史|人物館|大全集|全集|BOX|ボックス|セット|傑作選|復刻")
REISSUE_TYPES = {"bunkobon", "wideban", "kanzenban", "shinsoban", "aizoban", "deluxe"}


def dmon(d):
    """'YYYY' / 'YYYY-MM' / 'YYYY-MM-DD' -> 月通し番号。空/不正は None。"""
    if not d or len(d) < 4 or not d[:4].isdigit():
        return None
    y = int(d[:4])
    m = int(d[5:7]) if len(d) >= 7 and d[5:7].isdigit() else 6
    return y * 12 + m - 1


def rak_mon(sd):
    """楽天 salesDate ('1990年07月20日' / '2012年02月29日頃' 等) -> 月通し番号。"""
    m = re.search(r"(\d{4})\s*年\s*(\d{1,2})?", sd or "")
    if not m:
        return None
    return int(m.group(1)) * 12 + (int(m.group(2)) - 1 if m.group(2) else 5)


def gran(d):
    return {10: "day", 7: "month", 4: "year"}.get(len(d or ""), "none")


# ISBN(日本 978-4)を 出版者記号 と タイトル記号(シリアル)へ分解。
# 日本の出版者記号は桁可変(2〜7桁)。JPO の割当レンジで判定する。
_PUB_RANGES = ((2, 0, 19), (3, 200, 699), (4, 7000, 8499),
               (5, 85000, 89999), (6, 900000, 949999), (7, 9500000, 9999999))


def isbn_split(i13):
    if not i13 or len(i13) != 13 or not i13.isdigit() or not i13.startswith("9784"):
        return None
    body = i13[4:12]
    for plen, lo, hi in _PUB_RANGES:
        if lo <= int(body[:plen]) <= hi:
            tail = body[plen:]
            return body[:plen], (int(tail) if tail else 0)
    return None


print("[1/4] volume-flat.tsv 読み込み", flush=True)
rows = []
with open(FLAT, encoding="utf-8", newline="") as f:
    for r in csv.DictReader(f, delimiter="\t"):
        if r["is_version"] == "1":
            continue  # versions[]=刷タブのミラー。既定で除外
        rows.append(r)
print("    巻 {:,}".format(len(rows)), flush=True)

editions = collections.defaultdict(list)
for r in rows:
    editions[(r["slug"], r["ed_idx"])].append(r)
print("    版 {:,}".format(len(editions)), flush=True)

print("[2/4] 塊(cluster)抽出 + 版ごとの刊行ペース算出", flush=True)
clusters = []
for (slug, eidx), vs in editions.items():
    dated = [(v["release_date"], dmon(v["release_date"])) for v in vs if v["release_date"]]
    dated = [(d, m) for d, m in dated if m is not None]
    if not dated:
        continue
    months = sorted(set(m for _, m in dated))
    ed_n = len(vs)
    # 版の観測ペース(1巻あたり何ヶ月)。日付が1種類しか無い版は測れない(None)。
    if len(months) >= 2 and len(dated) > 1:
        cadence = (months[-1] - months[0]) / (len(dated) - 1)
    else:
        cadence = None
    cnt = collections.Counter(d for d, _ in dated)
    # 版が「まとめ配本」体質か: 日付グループの大きさの中央値。
    # ちばてつや全集は毎月3冊配本なので、3冊の塊は正常。
    sizes = sorted(cnt.values())
    ed_batch = sizes[len(sizes) // 2]
    for d, n in cnt.items():
        if n < MIN_N:
            continue
        mem = [v for v in vs if v["release_date"] == d]
        clusters.append({
            "slug": slug, "eidx": eidx, "date": d, "n": n, "ed_n": ed_n,
            "cadence": cadence, "mem": mem, "row0": vs[0], "ed_batch": ed_batch,
        })
print("    塊 {:,}".format(len(clusters)), flush=True)

# ---- ISBN近傍テーブル ------------------------------------------------------
# ★これが本families最大の判定材料。
# 出版者記号ごとに「タイトル記号(シリアル) -> 発売月」を全DBから作る。
# 塊のシリアル範囲の**近傍に居る他作品**の日付を見ると、
#   (a) 近傍も同じ日に固まっている  = その出版社/レーベルは実際にその日に一斉出荷した
#                                    (パンローリングのマンガショップ、ソノラマコミック文庫創刊、
#                                     集英社Personal you 等)= **正当**
#   (b) 近傍が数ヶ月〜数年に散っている = シリアルは時間とともに払い出されている。
#       塊のシリアル幅を近傍の払い出し速度(serial/月)で割れば
#       「この塊の本が実際には何ヶ月かけて登録されたか」(implied_months)が出る。
#       implied_months が大きいのに日付が1点 = **偽日付の直接証明**
print("[2b/4] ISBN近傍テーブル構築", flush=True)
_ntab = collections.defaultdict(list)
for r in rows:
    _sp = isbn_split(r["isbn13"])
    _m = dmon(r["release_date"])
    if _sp and _m is not None:
        _ntab[_sp[0]].append((_sp[1], _m, r["slug"]))
for _k in _ntab:
    _ntab[_k].sort()
_nkeys = {k: [x[0] for x in v] for k, v in _ntab.items()}


def neighbourhood(pref, lo, hi, slug):
    """塊のシリアル範囲の近傍(同じ出版者記号・別作品)を返す。"""
    arr = _ntab.get(pref)
    if not arr:
        return []
    ks = _nkeys[pref]
    pad = max(60, hi - lo)
    i0 = bisect.bisect_left(ks, lo - pad)
    i1 = bisect.bisect_right(ks, hi + pad)
    return [x for x in arr[i0:i1] if x[2] != slug]


# 一括登録イベント: 同じ (imprint, date) に 別シリーズの塊が並ぶか
ev = collections.defaultdict(set)
for c in clusters:
    ev[(c["row0"]["ed_imprint"], c["date"])].add(c["slug"])

# ---- 楽天照合(任意) --------------------------------------------------------
rak = {}
if ARGS.rakuten:
    want = set()
    for c in clusters:
        for v in c["mem"]:
            if v["isbn13"]:
                want.add(v["isbn13"])
    print("[3/4] 楽天キャッシュ1パス走査 (対象ISBN {:,})".format(len(want)), flush=True)
    if os.path.exists(RAKUTEN):
        with open(RAKUTEN, encoding="utf-8") as f:
            for line in f:
                # 高速前置フィルタ: ISBNが対象集合に無ければ json.loads しない
                m = re.match(r'\s*\{"isbn"\s*:\s*"?(\d{13})', line)
                if not m or m.group(1) not in want:
                    continue
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                sd = (o.get("item") or {}).get("salesDate") or ""
                if sd:
                    rak[m.group(1)] = sd
        print("    楽天ヒット {:,}".format(len(rak)), flush=True)
    else:
        print("    !! 楽天キャッシュが無いのでskip", flush=True)
else:
    print("[3/4] 楽天照合はskip (--rakuten で有効)", flush=True)


print("[4/4] 採点 + 出力", flush=True)
out = []
for c in clusters:
    r0, mem, n, d = c["row0"], c["mem"], c["n"], c["date"]
    g = gran(d)
    cm = dmon(d)
    frac = n / c["ed_n"] if c["ed_n"] else 0.0
    nums = sorted(int(v["number"]) for v in mem if (v["number"] or "").isdigit())
    span = (nums[-1] - nums[0] + 1) if nums else 0
    consecutive = bool(nums) and span == len(nums)

    ys = int(r0["year_started"]) if (r0["year_started"] or "").isdigit() else None
    ye = int(r0["year_ended"]) if (r0["year_ended"] or "").isdigit() else None
    serial_years = (ye - ys + 1) if (ys and ye) else ((TODAY.year - ys + 1) if ys else None)

    # ISBN連番性: 塊内シリアルの幅 / 巻数。幅 <= 巻数+1 なら 1ブロック採番 = 同時発売の傍証
    sers = [isbn_split(v["isbn13"]) for v in mem if v["isbn13"]]
    sers = [s for s in sers if s]
    isbn_blk = ""
    contiguous = False
    if len(sers) >= 3 and len(set(p for p, _ in sers)) == 1:
        ss = sorted(s for _, s in sers)
        width = ss[-1] - ss[0] + 1
        isbn_blk = "{}/{}".format(len(ss), width)
        contiguous = width <= len(ss) + 1

    # 本来この n 巻が跨ぐはずの月数
    cad = c["cadence"]
    if cad is None or cad <= 0:
        cad_used, cad_src = 2.5, "assumed"  # 手掛かりが無い時の一般的な単行本ペース
    else:
        cad_used, cad_src = cad, "observed"
    span_m = round((n - 1) * cad_used, 1)

    ev_n = len(ev[(r0["ed_imprint"], d)])
    future = cm is not None and cm > TODAY_M
    pre_serial = bool(ys) and cm is not None and (cm // 12) < ys

    # 楽天照合: 塊のISBNに対する楽天 salesDate が何種類あるか / 何ヶ月に散っているか
    rk_pairs = []
    for v in sorted(mem, key=lambda x: (int(x["number"]) if (x["number"] or "").isdigit() else 0)):
        sd = rak.get(v["isbn13"], "")
        if sd:
            rk_pairs.append((v["number"], sd))
    rk = [sd for _, sd in rk_pairs]
    rk_distinct = len(set(rk))
    rk_ms = [rak_mon(sd) for _, sd in rk_pairs]
    rk_ms_ok = [x for x in rk_ms if x is not None]
    rk_spread = (max(rk_ms_ok) - min(rk_ms_ok)) if len(rk_ms_ok) >= 2 else 0
    # 楽天日付が巻番号順に「非減少」か = 本物の連続刊行の形をしているか
    seq = [x for x in rk_ms if x is not None]
    rk_mono = len(seq) >= 3 and all(seq[i] <= seq[i + 1] for i in range(len(seq) - 1))
    # 楽天が「重版/新装の日付」を返している疑い
    #  ① 散り方が刊行ペースとして非現実的 ② 本番日付から7年以上ズレた所に居る
    rk_off = 0
    if rk_ms_ok and cm is not None:
        rk_ms_sorted = sorted(rk_ms_ok)
        rk_off = rk_ms_sorted[len(rk_ms_sorted) // 2] - cm
    rk_too_wide = rk_spread > max(24, n * 18) or abs(rk_off) > 84
    rk_col = ""
    if rk:
        rk_col = "{}種/{}件/散{}ヶ月".format(rk_distinct, len(rk), rk_spread)
        if rk_too_wide:
            rk_col += "/本番との中央ズレ{}ヶ月 ※楽天が重版・新装の日付を返している疑い(証拠として弱い)".format(rk_off)
        elif rk_distinct >= 2 and rk_spread >= 3:
            rk_col += " ★楽天はバラける=本番の同一日が偽"
        elif rk_spread < 3:
            rk_col += " (楽天も実質同日=一挙刊行の可能性)"
    rk_detail = " ".join("{}:{}".format(nu, sd) for nu, sd in rk_pairs[:14])

    # ---- ISBN近傍による裏取り ----
    nbr_n = nbr_same = nbr_inside = 0
    nbr_titles = nbr_titles_flat = 0
    nbr_span = 0
    local_rate = None
    implied_months = None
    serial_width = 0
    if len(sers) >= 2 and len(set(p for p, _ in sers)) == 1 and cm is not None:
        pref = sers[0][0]
        lo_s = min(x[1] for x in sers)
        hi_s = max(x[1] for x in sers)
        serial_width = hi_s - lo_s + 1
        nb = neighbourhood(pref, lo_s, hi_s, c["slug"])
        nbr_n = len(nb)
        # 塊のシリアルの「間」に他作品が挟まっているか。
        # 挟まっていない = そのレンジはこのシリーズ専用の予約ブロック(=証明不可)。
        nbr_inside = sum(1 for x in nb if lo_s < x[0] < hi_s)
        if nbr_n >= 4:
            # 近傍の**他作品が、自分の巻を1日にまとめているか**。
            # まとめている作品が多数派 = そのレーベルは「1タイトル丸ごと同日出荷」する
            # 体質(集英社 Personal you / マンガショップ 等)= この塊も正当の可能性が高い。
            per = collections.defaultdict(set)
            for _s, _m, _sl in nb:
                per[_sl].add(_m)
            multi = {k: v for k, v in per.items() if len([1 for x in nb if x[2] == k]) >= 2}
            nbr_titles = len(multi)
            nbr_titles_flat = sum(1 for v in multi.values() if len(v) == 1)
            nms = [x[1] for x in nb]
            nbr_same = sum(1 for x in nms if x == cm)
            nbr_span = max(nms) - min(nms)
            if nbr_span >= 3:
                # 近傍の払い出し速度 (serial / 月)。頑健化のため両端でなく5-95%点を使う。
                pair = sorted(zip(nms, [x[0] for x in nb]))
                k = max(1, len(pair) // 20)
                m_lo, s_lo = pair[k - 1]
                m_hi, s_hi = pair[-k]
                if m_hi > m_lo and s_hi > s_lo:
                    local_rate = (s_hi - s_lo) / (m_hi - m_lo)
                    if local_rate > 0:
                        implied_months = round((hi_s - lo_s) / local_rate, 1)
    # 近傍の過半が塊と同じ日 = その日はレーベルの一斉出荷日 = 正当の強い傍証
    nbr_flat = (nbr_n >= 5 and nbr_same / nbr_n >= 0.6)
    # レーベル体質: 近傍の複数巻タイトルの6割以上が「全巻同日」
    label_ships_whole = (nbr_titles >= 4 and nbr_titles_flat / nbr_titles >= 0.5)
    # ★ISBN証明の前提: 塊のシリアルが「連番の予約ブロック」でないこと。
    #   出版社はシリーズ用にシリアルをまとめて予約するので、幅≒巻数の連番塊は
    #   何ヶ月かけて出しても連番になる = 払い出し速度からは何も言えない。
    #   幅が巻数の3倍以上に散っている時だけ「時間をかけて採番された」と言える。
    #   さらに、塊のシリアルの「間」に他作品が3つ以上挟まっていることを要求する。
    #   挟まっていなければそのレンジはシリーズ専用の予約ブロック
    #   (サザエさん朝日文庫: 全45巻分のISBNを巻番号順に予約し、実際は月4冊ずつ配本。
    #    シリアル幅は広いが払い出し速度からは何も言えない)。
    #   幅が桁違い(>20000)の塊は そもそも同一レーベルの連続採番ではない
    #   (別出版社/別レーベルの混入 = 版混在family の領域)ので証明に使わない。
    isbn_proof_ok = (max(3 * n, n + 6) <= serial_width <= 20000) and nbr_inside >= 3

    # ---- 分類 ----
    # ★最優先 = 楽天との衝突。本番が「全部同じ日」と言い、楽天が巻ごとに違う日を返すなら、
    #   「同一日」の方が作り物(= 一括登録)。バラけた日付は捏造されない。
    #   ただし散りすぎ(rk_too_wide)は楽天が重版日付を返しているだけなので証拠にしない。
    rk_staggered = ((not rk_too_wide) and rk_distinct >= 3 and rk_spread >= 4 and rk_mono)
    if (nbr_flat or label_ships_whole) and not rk_staggered:
        # ★近傍(同出版者記号の他作品)も同じ日に固まっている = レーベルの一斉出荷日。
        #   マンガショップ/ソノラマコミック文庫創刊/集英社Personal you 等はこれ。正当。
        kind, sev = "PUBLISHER_BATCH", "LOW"
    elif rk_staggered:
        # 楽天側が「巻順に単調増加する本物の刊行列」を示している = 最強
        kind, sev = "RAKUTEN_STAGGERED", "BROKEN"
    elif implied_months is not None and implied_months >= 9 and nbr_n >= 8 and isbn_proof_ok:
        # ★ISBNシリアルの払い出し速度から、この塊の本は実際には9ヶ月以上かけて
        #   登録されたことが判る。それが1点の日付になっている = 偽日付の直接証明。
        kind, sev = "ISBN_SPREAD_PROOF", "BROKEN"
    elif pre_serial:
        kind, sev = "PRE_SERIAL", "BROKEN"
    elif (not rk_too_wide) and rk_distinct >= 3 and rk_spread >= 6:
        kind, sev = "RAKUTEN_CONFLICT", "BROKEN"
    elif future and n >= 3:
        kind, sev = "FUTURE", "HIGH"
    elif (not rk_too_wide) and rk_distinct >= 2 and rk_spread >= 3:
        kind, sev = "RAKUTEN_CONFLICT", "HIGH"
    elif implied_months is not None and implied_months >= 4 and nbr_n >= 8 and isbn_proof_ok:
        kind, sev = "ISBN_SPREAD", "HIGH"
    elif rk_too_wide:
        kind, sev = "RAKUTEN_WIDE", "MED"
    elif frac >= 0.999 and n >= 5 and (serial_years or 0) >= 3:
        kind, sev = "FLAT_RUN", "HIGH"
    elif ev_n >= 3 and not contiguous:
        kind, sev = "EVENT_BULK", "HIGH"
    elif frac >= 0.999 and n >= 4:
        kind, sev = "FLAT_RUN", "MED"
    elif frac < 0.999 and span_m >= 12:
        kind, sev = "PARTIAL_BULK", "MED"
    else:
        kind, sev = "SMALL_BATCH", "LOW"

    # ★版自身が「毎回n冊まとめ配本」なら、その大きさの塊は正常
    #   (ちばてつや全集 = 1997年に毎月3冊ずつ21巻を配本。19-21巻が同月なのは正常)
    if n <= c["ed_batch"] and sev in ("BROKEN", "HIGH", "MED") and not kind.startswith("RAKUTEN")             and kind != "PRE_SERIAL":
        sev = "LOW"
        kind = "ED_REGULAR_BATCH"

    # ★12-31 / 01-01 は「年しか判らない本」に機械で付けられた placeholder。
    placeholder = d.endswith("-12-31") or d.endswith("-01-01")
    if placeholder and sev == "LOW" and kind not in ("PUBLISHER_BATCH",):
        sev, kind = "MED", "PLACEHOLDER_DATE"
    elif placeholder and sev in ("MED",):
        kind += "+placeholder日付(12-31/01-01)"

    # 粗い日付("YYYY"だけ)は元から日単位が無いだけ = 一括登録とは別物
    if g == "year" and sev in ("HIGH", "MED") and not kind.startswith("RAKUTEN"):
        sev = "LOW"
        kind += "(年のみ)"

    hint = []
    if contiguous:
        hint.append("ISBN連番(弱い証拠=採番ブロック予約でも連番になる)")
    if LEGIT_RE.search((r0["title"] or "") + (r0["ed_imprint"] or "")):
        hint.append("学習/全集/BOX語")
    if r0["ed_type"] in REISSUE_TYPES:
        hint.append("再版種別")
    if len(rk) >= 3 and rk_spread < 3:
        hint.append("楽天も実質同日")
    if nbr_flat:
        hint.append("近傍{}件中{}件が同日=レーベル一斉出荷".format(nbr_n, nbr_same))
    if label_ships_whole:
        hint.append("近傍の複数巻作品{}件中{}件が全巻同日=レーベル体質".format(nbr_titles, nbr_titles_flat))

    out.append({
        "severity": sev, "kind": kind, "slug": c["slug"], "title": r0["title"],
        "ed_idx": c["eidx"], "ed_type": r0["ed_type"], "ed_imprint": r0["ed_imprint"],
        "ed_publisher": r0["ed_publisher"], "date": d, "gran": g,
        "n": n, "ed_vols": c["ed_n"], "frac": round(frac, 2), "ed_batch": c["ed_batch"],
        "vols": ("{}-{}".format(nums[0], nums[-1]) + ("" if consecutive else "(飛)")) if nums else "",
        "cadence_mo": ("" if cad is None else round(cad, 1)),
        "cad_src": cad_src, "span_months": span_m,
        "serial_years": serial_years or "", "year_started": r0["year_started"],
        "year_ended": r0["year_ended"],
        "event_slugs": ev_n, "isbn_block": isbn_blk,
        "nbr_n": nbr_n, "nbr_same": nbr_same, "nbr_inside": nbr_inside, "nbr_span_mo": nbr_span,
        "nbr_titles": nbr_titles, "nbr_titles_flat": nbr_titles_flat,
        "serial_width": serial_width, "isbn_proof_ok": 1 if isbn_proof_ok else 0,
        "local_rate": ("" if local_rate is None else round(local_rate, 2)),
        "implied_months": ("" if implied_months is None else implied_months),
        "rakuten": rk_col, "rk_distinct": rk_distinct, "rk_spread_mo": rk_spread,
        "rk_offset_mo": rk_off,
        "rk_mono": 1 if rk_mono else 0, "rakuten_dates": rk_detail,
        "legit_hint": " / ".join(hint),
    })

SEV_ORDER = {"BROKEN": 0, "HIGH": 1, "MED": 2, "LOW": 3}
out.sort(key=lambda r: (SEV_ORDER[r["severity"]], -r["n"], -float(r["span_months"])))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
cols = ["severity", "kind", "slug", "title", "ed_idx", "ed_type", "ed_imprint", "ed_publisher",
        "date", "gran", "n", "ed_vols", "frac", "ed_batch", "vols", "cadence_mo", "cad_src", "span_months",
        "serial_years", "year_started", "year_ended", "event_slugs", "isbn_block",
        "nbr_n", "nbr_same", "nbr_inside", "nbr_titles", "nbr_titles_flat", "nbr_span_mo",
        "serial_width", "isbn_proof_ok",
        "local_rate", "implied_months", "rakuten",
        "rk_distinct", "rk_spread_mo", "rk_offset_mo", "rk_mono", "rakuten_dates",
        "legit_hint"]
with open(OUT, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", extrasaction="ignore")
    w.writeheader()
    for r in out:
        w.writerow(r)

sev_c = collections.Counter(r["severity"] for r in out)
kind_c = collections.Counter(r["kind"] for r in out)
print("\n出力: " + OUT)
print("塊 {:,} / 対象巻 {:,} / 頁 {:,}".format(
    len(out), sum(r["n"] for r in out), len(set(r["slug"] for r in out))))
print("重症度:", dict(sev_c))
print("型:", dict(kind_c))
print("\n== 上位35 ==")
for r in out[:35]:
    print("  [{}/{}] {} ed{}({}/{}) {} n={}/{} vols={} span={}mo ev={} isbn={} | {} {}".format(
        r["severity"], r["kind"], r["slug"], r["ed_idx"], r["ed_type"], r["ed_imprint"][:18],
        r["date"], r["n"], r["ed_vols"], r["vols"], r["span_months"], r["event_slugs"],
        r["isbn_block"], r["rakuten"], r["legit_hint"]))

print("\n== 一括登録イベント候補 (imprint x date に 3シリーズ以上の塊) ==")
big = sorted(((len(v), k) for k, v in ev.items() if len(v) >= 3), reverse=True)
for cnt, k in big[:20]:
    print("  {}\t{}\t{}シリーズ".format((k[0][:34] or "(imprint空)"), k[1], cnt))
