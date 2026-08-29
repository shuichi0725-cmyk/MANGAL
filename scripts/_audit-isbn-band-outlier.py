#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""版の中で★孤立した ISBN 出版者記号(帯)★を持つ巻を洗う (= 版の途中に1〜2巻だけ他社の本が座っている)。

★何を見るか
  同一 (slug, edition) の中で、ISBN の出版者記号 (978-4-XXXX… ★可変長) が **多数派と違う巻**のうち、
  少数派が **1〜2巻だけ** のものを、位置で3つに分けて出す:
    ・散発 … 前にも後ろにも多数派の巻が居る = ★本命(版元移管では説明できない)
    ・先頭/末尾 … 移籍(TAIL)や前半別社(HEAD)で説明できることが多い = ★参考レーン
  実測: 散発は全DBで **40巻しかない**(= 稀な型)。 先頭/末尾は 1,296巻。

★なぜ既存検出器では足りないか (= 重複を承知の上での付加価値)
  - `_audit-edition-mix.py` … 同じ帯混在を TAIL/HEAD/SCATTERED に3分類する。 ★母集団はほぼ同じ。
    しかし **優先度を付けず、少数派が何の本なのかを見ない**(初回 SCATTERED 119 / TAIL 1,137 / HEAD 448 を
    人が全部読む必要があった)。 本script は少数派ISBNを楽天キャッシュで実題まで引き、
    「別作品」「別版」「社名違い」「日付逆行」を機械証拠として重ね、重症度で並べ替える。
  - `_audit-band-intruders.py`(激マン型) … **日付逆行を伴うもの限定**。 しかも帯を
    ★`isbn13[:7]` の**固定長**で切るため、2桁記号の大手(講談社06/集英社08/小学館09)は
    商品番号の1桁目まで帯に混ざり、同じ社の巻が別帯として割れる。 本script は登録グループ長ルールの
    **可変長**記号を使うので、大手内での偽の割れが起きない。
  - `_audit-publisher-vs-isbn.py` … 「当方の出版社名 vs ISBN記号」の食い違いは見るが、
    **版の中で1巻だけ浮いている**という位置情報を使わない。

★重ねる機械証拠
  PUBDIFF   … 少数派帯の社名(全DB多数決で自己教師)が多数派帯の社名と違う。 同社の別記号なら SAME_PUB=低優先。
  PAIRCOMMONn … ★この帯ペアが全DBの **n版で同居**している = 版元継承/共同刊行の常連(KADOKAWA04↔旧メディア
              ファクトリー8401、リブレ7997↔リブレ出版86263、エンターブレイン7577↔アスペクト7572 …)。
              社名文字列では拾えない企業承継を**データ自身に語らせる**ので、これが立つ行は1段格下げする。
  PAIRONLY  … 逆にそのペアがこの1版でしか起きていない = 一点物の混入疑い。
  SEQFILL   … ★多数派帯のISBN商品番号が **浮き巻のスロットを飛ばして連番** になっている
              (例 双葉社シャッター …81194[4巻] 空 81196[6巻] = 5巻の番号81195が予約済み)。
              = 押し出された真の巻が確かに在った証拠。 ★本来のISBNを逆算して「連番からの想定ISBN」列に出す。
              promote は1版1番号1巻に絞るので真巻は**消える**= 巻番号の重複としては現れない。これが代替signal。
  ANACHRONn … ★その帯が全DBで使われ始めた年より **n年も前**の発売日に付いている = その時点で
              まだ存在しない出版者記号 = ★混入の動かぬ証拠(シャッター1986年の巻に小池書院4-88315 等)。
              使い始め年は「3番目に古い年」で採る(最小値は汚染そのもので崩れるため)。
  BANDRAREn … ★その帯が全DBで n版(<=2)にしか出ない = 出版者記号として謎(ISBN誤り/一点物)。
              ★この場合 帯→社名の多数決は **監査対象の行自身**から学んでしまうので社名比較は信用しない
              (= 帯を「説明できない」側に入れる)。 ただし ★単独では C中止まり: 実測3件のうち2件は
              リム出版新社4-89800 / 増進会出版社4-915491 という **実在の後継記号**で正当だった。
  DATEBADNy … 前後の多数派巻に対し発売日が N年逆行(散発レーンのみ)。
  GAPNy     … 隣接する多数派巻から N年以上飛んでいる(先頭/末尾レーンのみ。 復刻・別版の接ぎ木signal)。
  OTHER_ED  … その帯が **同じ頁の別の版**の多数派帯 = 版の取り違え(頁内で座席を間違えた)。
  TITLEDIFF … 楽天の実題が頁題を含まない = ★別作品の疑い(最強)。
  EDWORD    … 楽天の実題/叢書に「完全版・愛蔵版・文庫・傑作選…」等の版名語があり、**この頁のこの版には無い**
              = 別版の巻が本編枠に座っている(ベルサイユのばら型)。
  RAKPUB    … 楽天の出版社が当方の版publisherと違う(外部からの独立裏取り)。

★既知の偽陽性型 (= 自動修正を絶対にしない理由)
  - 大手は**複数の出版者記号**を持つ(KADOKAWA=04 と 旧メディアファクトリー4-8401 等)。 社名が同じなら SAME_PUB。
  - 出版社移籍は先頭/末尾に固まるのが普通 = 参考レーンは大半が正当。
  - 共同出版・発売元/発行元違い(= `_audit-publisher-vs-isbn.py` の領域)。
  - 一部の巻だけ別レーベルで出た正当な例(記念版・限定版が本編の番号を持つ)。
  - 楽天題は表記ゆらぎが激しく、TITLEDIFF 単独では確定しない(必ず人が見る)。
  - ISBN が無い巻は判定対象外(1980年代以前は空が普通。 ★空を異常と扱わない)。
  - versions[](刷タブ)由来の巻は既定で除外。
  - ★巻番号の重複は検出できない(promote が1版1番号1巻に絞るため、押し出された真巻は**消える**)。
    「押し出し」の検出は巻抜け側(`_audit-volume-gaps.py` / volgap)と突き合わせて初めて分かる。

★初回実測 (2026-08-29): 散発40巻(A確実7 / B高7 / C中9 / D低17) + 参考レーン1,296巻(E高10 / F1,286)。
  ★SEQFILL が逆算した「本来のISBN」8件は **8件とも本番DBのどこにも存在しない** = 侵入巻が真の巻を
  押し出したのではなく、真の巻は最初から本番に無い(取りこぼし)。 是正は「混入除去 + 種4で真巻追加」の2手が要る。

出力: docs/production-diagnostics/isbn-band-outlier.tsv (read-only。 是正はしない)
是正先(参考): edition-canonical/*.yml で版再構築 / volume-exclude + 種4 で混入除去+真巻追加 /
              band-intruder-fix skill (NDL正史×楽天照合でスワップ)。

使い方:
  python scripts/_audit-isbn-band-outlier.py            (楽天キャッシュ1パスあり)
  python scripts/_audit-isbn-band-outlier.py --no-rakuten
"""
import argparse
import collections
import csv
import io
import itertools
import json
import os
import re
import sys
import unicodedata

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAT = os.path.join(ROOT, ".cache", "volume-flat.tsv")
RAKUTEN = os.path.join(ROOT, ".cache", "rakuten-isbn-delta.jsonl")
TITLEMAP = os.path.join(ROOT, ".cache", "isbn-title-map.json")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "isbn-band-outlier.tsv")

COLS = ["重症度", "位置", "証拠", "slug", "題", "版type", "版imprint", "版publisher",
        "版の巻数", "多数派帯", "多数派社名", "浮巻番号", "浮ISBN", "浮帯", "浮帯の社名",
        "浮巻発売日", "前後の多数派", "ズレ月", "連番からの想定ISBN", "楽天題", "楽天叢書", "楽天出版社"]

# 版名語 = 「別の版の巻」が本編枠に紛れた時に楽天題/叢書に出る語
ED_WORDS = ("完全版", "愛蔵版", "文庫", "新装版", "新装", "総集編", "傑作選", "傑作集",
            "大全集", "全集", "選集", "デラックス", "ワイド", "廉価", "コンビニ",
            "特装", "限定", "合本", "復刻", "普及版", "オンデマンド", "セレクション")


def jp_band(isbn13):
    """日本(978-4)ISBN の出版者記号(登録グループ長ルール・可変長2〜7桁)。
    ★固定長 slice は 2桁記号の大手(06 講談社 / 08 集英社 / 09 小学館)を誤分割する。
    `_promote-bulk-v2.py` / `_audit-edition-mix.py` と同じ規則。"""
    i = isbn13
    if len(i) != 13 or not i.startswith("9784"):
        return ""
    r = i[4:]
    if r[0] in "01":
        ln = 2
    elif r[0] in "23456":
        ln = 3
    elif "70" <= r[:2] <= "84":
        ln = 4
    elif "85" <= r[:2] <= "89":
        ln = 5
    elif "900" <= r[:3] <= "949":
        ln = 6
    else:
        ln = 7
    return i[4:4 + ln]


def isbn_ok(s):
    """13桁+チェックディジット。 typo ISBN を帯異常として数えないための門番。"""
    if len(s) != 13 or not s.isdigit():
        return False
    return sum(int(d) * (1 if n % 2 == 0 else 3) for n, d in enumerate(s)) % 10 == 0


def norm_pub(s):
    t = unicodedata.normalize("NFKC", s or "").lower()
    for w in ("株式会社", "(株)", "有限会社", "出版社", "・", "=", " ", "　"):
        t = t.replace(w, "")
    return t


_TITLE_DROP = re.compile(r"[\s0-9０-９()（）\[\]【】「」『』・･,，.。!！?？:：;；\-‐―ー~〜/／\\&＆'\"’”*＊+＋#＃@＠]")


def norm_title(s):
    """題の照合キー。 巻数・記号・空白を落として比較する(楽天題は表記ゆらぎが激しい)。"""
    t = unicodedata.normalize("NFKC", s or "").lower()
    t = re.sub(r"[（(【\[].*?[）)】\]]", "", t)
    return _TITLE_DROP.sub("", t)


def months(s):
    m = re.match(r"^(\d{4})-(\d{2})", s or "")
    if m:
        return int(m.group(1)) * 12 + int(m.group(2))
    m = re.match(r"^(\d{4})$", s or "")
    return int(m.group(1)) * 12 + 6 if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-vols", type=int, default=3,
                    help="この巻数未満の版は見ない(多数派が定義できない)")
    ap.add_argument("--max-outliers", type=int, default=2,
                    help="少数派がこれを超える版は『版そのものが2本』= 別問題(edition-run-split領域)として除外")
    ap.add_argument("--no-rakuten", action="store_true")
    a = ap.parse_args()

    print("[1/4] volume-flat.tsv 読込 ...", flush=True)
    eds = collections.defaultdict(list)
    band_pub = collections.defaultdict(collections.Counter)
    band_years = collections.defaultdict(list)
    n = 0
    with io.open(FLAT, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row.get("is_version") == "1":
                continue
            n += 1
            eds[(row["slug"], row["ed_idx"])].append(row)
            i = row["isbn13"]
            if isbn_ok(i):
                b = jp_band(i)
                if row["ed_publisher"]:
                    band_pub[b][row["ed_publisher"]] += 1
                m = re.match(r"^(\d{4})", row["release_date"] or "")
                if m:
                    band_years[b].append(int(m.group(1)))
    print("    %d巻 / %d版 / 帯 %d種" % (n, len(eds), len(band_pub)), flush=True)

    print("[2/4] 版ごとに浮き巻を判定 ...", flush=True)
    page_major = collections.defaultdict(set)   # 頁 → 各版の多数派帯(= OTHER_ED 証拠用)
    ed_major = {}
    pair_n = collections.Counter()              # 帯ペア → 同居した版の数(= 企業承継の自己教師)
    band_n = collections.Counter()              # 帯 → その帯が出る版の数
    for k, vols in eds.items():
        bs = collections.Counter(jp_band(v["isbn13"]) for v in vols if isbn_ok(v["isbn13"]))
        if bs:
            ed_major[k] = bs.most_common(1)[0][0]
            page_major[k[0]].add(ed_major[k])
        for b in bs:
            band_n[b] += 1
        for x, y in itertools.combinations(sorted(bs), 2):
            pair_n[(x, y)] += 1

    # 帯 → 代表社名(全DB多数決 = 自己教師)。
    # ★ただし **版数3未満の帯は信用しない**。 実踏(がらくた屋まん太 9784456111442):
    # 帯456 は全DBでその1巻だけしか無く、多数決が **監査対象の行自身**から社名を学んで
    # 「同社の別記号」と自己成就的に降格させていた(= 楽天にも存在しない謎のISBNだった)。
    bpub = {b: c.most_common(1)[0][0] for b, c in band_pub.items() if c and band_n.get(b, 0) >= 3}

    # 帯 → ★使い始め年(= その出版者記号が存在し始めた年)。
    # ★汚染行自身に引っ張られないよう **3番目に古い年** を採る(最小値は汚染で崩れる)。
    # これで「1986年の巻に 4-88315(小池書院2000年代の記号)が付いている」类の
    # ★時代的にあり得ないISBNを機械的に確定できる(= 混入の動かぬ証拠)。
    band_start = {}
    for b, ys in band_years.items():
        if len(ys) >= 5:
            band_start[b] = sorted(ys)[2]

    def pair_stat(x, y):
        """帯ペアの同居回数と ★リフト(= 少ない方の帯の版数で規格化)。
        ★生の回数だけでは大手同士(講談社06×小学館09 = 偶然の同居 5版)を
        「常連」と誤判定する。 実測: 承継ペアは比率 0.09～0.75
        (KADOKAWA04×メディアファクトリ8401=0.17 / リブレ7997×リブレ出版8 6263=0.13 /
        メディアワークス07×8402=0.13)、 偶然の同居は 0.001～0.014 で完全に分かれる。"""
        a_, b_ = sorted((x, y))
        p = pair_n[(a_, b_)]
        d = min(band_n.get(a_, 0), band_n.get(b_, 0)) or 1
        return p, p / d

    cand = []
    for key, vols in eds.items():
        slug, _ = key
        valid = [v for v in vols if isbn_ok(v["isbn13"])]
        if len(valid) < a.min_vols:
            continue
        bands = collections.Counter(jp_band(v["isbn13"]) for v in valid)
        if len(bands) < 2:
            continue
        maj, majn = bands.most_common(1)[0]
        out_vols = [v for v in valid if jp_band(v["isbn13"]) != maj]
        if not (1 <= len(out_vols) <= a.max_outliers):
            continue
        if majn < len(valid) - a.max_outliers:
            continue

        def num(v):
            try:
                return int(v["number"])
            except Exception:
                return None

        maj_nums = [(num(v), v) for v in valid if jp_band(v["isbn13"]) == maj and num(v) is not None]
        if not maj_nums:
            continue

        for ov in out_vols:
            k = num(ov)
            if k is None:
                continue
            lower = [t for t in maj_nums if t[0] < k]
            upper = [t for t in maj_nums if t[0] > k]
            if not lower and not upper:
                continue
            pos = "散発" if (lower and upper) else ("先頭" if not lower else "末尾")
            prev = max(lower, key=lambda t: t[0])[1] if lower else None
            nxt = min(upper, key=lambda t: t[0])[1] if upper else None
            # ★SEQFILL = 多数派帯のISBN商品番号が **浮き巻のスロットを飛ばして連続している**か。
            # 出版社は連続巻に連番の商品番号を振るので、例えば双葉社シャッターは
            # ...81194(4巻) 【空】 81196(6巻) となり、★5巻の番号 81195 が予約済みだと分かる。
            # = 押し出された真の巻が確かに存在した証拠 + ★本来のISBNを逆算できる(人が裁く材料)。
            # promote は1版1番号1巻に絞るので真巻は**消え**、巻番号の重複としては現れない。
            gap, want = "", ""
            if prev is not None and nxt is not None and num(prev) == k - 1 and num(nxt) == k + 1:
                w = len(maj)
                d = {}
                for x, v in maj_nums:
                    try:
                        d[x] = int(v["isbn13"][4 + w:12])
                    except Exception:
                        pass
                st = collections.Counter()
                for x in d:
                    if x + 1 in d and 0 < d[x + 1] - d[x] <= 10:
                        st[d[x + 1] - d[x]] += 1
                if st and k - 1 in d and k + 1 in d:
                    sstep, sn = st.most_common(1)[0]
                    if sn >= 2 and d[k + 1] - d[k - 1] == sstep * 2:
                        gap = "SEQFILL"
                        core = "9784" + maj + str(d[k - 1] + sstep).zfill(8 - w)
                        if len(core) == 12:
                            c = (10 - sum(int(x) * (1 if i % 2 == 0 else 3)
                                          for i, x in enumerate(core)) % 10) % 10
                            want = core + str(c)
            cand.append((key, valid, maj, majn, ov, k, pos, prev, nxt, gap, want))

    need_isbn = set(c[4]["isbn13"] for c in cand)
    print("    候補 %d 巻 (散発 %d / 先頭 %d / 末尾 %d) / 要照合ISBN %d"
          % (len(cand), sum(1 for c in cand if c[6] == "散発"),
             sum(1 for c in cand if c[6] == "先頭"),
             sum(1 for c in cand if c[6] == "末尾"), len(need_isbn)), flush=True)

    got = {}
    if not a.no_rakuten and os.path.exists(RAKUTEN) and need_isbn:
        print("[3/4] 楽天キャッシュ 1パス走査(実題/叢書/出版社) ...", flush=True)
        with io.open(RAKUTEN, encoding="utf-8", errors="replace") as f:
            for line in f:
                if line[10:23] not in need_isbn:
                    continue
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                it = o.get("item") or {}
                i = str(o.get("isbn") or "")
                if i in need_isbn and i not in got:
                    got[i] = (str(it.get("title") or "")[:60],
                              str(it.get("seriesName") or "")[:30],
                              str(it.get("publisherName") or "")[:24])
        print("    楽天ヒット %d/%d" % (len(got), len(need_isbn)), flush=True)
        if os.path.exists(TITLEMAP):
            tm = json.load(io.open(TITLEMAP, encoding="utf-8"))
            add = 0
            for i in need_isbn:
                if i not in got and i in tm:
                    got[i] = (str(tm[i])[:60], "", "")
                    add += 1
            print("    isbn-title-map で +%d" % add, flush=True)
    else:
        print("[3/4] 楽天照合 skip", flush=True)

    print("[4/4] 証拠を重ねて格付け ...", flush=True)
    rows, sev_n, ev_n = [], collections.Counter(), collections.Counter()
    for key, valid, maj, majn, ov, k, pos, prev, nxt, gap, want in cand:
        slug = key[0]
        ob = jp_band(ov["isbn13"])
        mp, op = bpub.get(maj, ""), bpub.get(ob, "")
        ev = []
        pubdiff_raw = bool(mp) and bool(op) and norm_pub(mp) != norm_pub(op)
        ev.append("PUBDIFF" if pubdiff_raw else ("SAME_PUB" if (mp and op) else "PUB不明"))
        oy = re.match(r"^(\d{4})", ov["release_date"] or "")
        if oy and ob in band_start and int(oy.group(1)) < band_start[ob] - 3:
            ev.append("ANACHRON%d" % (band_start[ob] - int(oy.group(1))))
        if band_n.get(ob, 0) <= 2:
            ev.append("BANDRARE%d" % band_n.get(ob, 0))   # 帯自体が全DBで極稀 = ISBN誤り/謎の版元
        pn, pr = pair_stat(maj, ob)
        paircommon = pn >= 3 and pr >= 0.05
        if paircommon:
            ev.append("PAIRCOMMON%d(%.0f%%)" % (pn, pr * 100))
        elif pn <= 1:
            ev.append("PAIRONLY")

        mo = months(ov["release_date"])
        mprev = months(prev["release_date"]) if prev is not None else None
        mnext = months(nxt["release_date"]) if nxt is not None else None
        dev = 0
        if mo is not None:
            if pos == "散発":
                if mprev is not None and mo < mprev:
                    dev = max(dev, mprev - mo)
                if mnext is not None and mo > mnext:
                    dev = max(dev, mo - mnext)
                if dev >= 12:
                    ev.append("DATEBAD%dy" % (dev // 12))
            else:
                near = mprev if mprev is not None else mnext
                if near is not None:
                    dev = abs(mo - near)
                    if dev >= 120:      # 隣接巻から10年以上 = 復刻/別版の接ぎ木signal
                        ev.append("GAP%dy" % (dev // 12))
        if gap:
            ev.append(gap)
        if ob in page_major[slug] and ob != ed_major.get(key):
            ev.append("OTHER_ED")

        rt, rs, rp = got.get(ov["isbn13"], ("", "", ""))
        page_t = norm_title(ov["title"])
        rak_t = norm_title(rt)
        if rt and page_t and rak_t and page_t not in rak_t and rak_t not in page_t:
            ev.append("TITLEDIFF")
        # 版名語は「この頁のこの版に無い語」だけが signal(完全版の頁で完全版は正当)
        mine = unicodedata.normalize("NFKC", " ".join(
            [ov["title"], ov["ed_imprint"], ov["ed_label"], ov["ed_type"]]))
        hit = [w for w in ED_WORDS if (w in rt or w in rs) and w not in mine]
        if hit:
            ev.append("EDWORD:" + "/".join(hit[:2]))
        if rp and ov["ed_publisher"] and norm_pub(rp) != norm_pub(ov["ed_publisher"]):
            ev.append("RAKPUB")

        # ★承継ペアなら「社名が違う」は説明が付いている = 帯は正当と見なす
        # ★「帯が説明できない」= 社名が違う(承継ペアを除く) or 帯自体が極稀
        pubdiff = (pubdiff_raw and not paircommon) or band_n.get(ob, 0) <= 2
        strong = sum(1 for e in ev if e.startswith(("DATEBAD", "GAP", "OTHER_ED", "TITLEDIFF", "EDWORD", "ANACHRON", "SEQFILL")))
        if pos == "散発":
            if not pubdiff:
                sev = "D低(同社/系列の別記号)"
            elif strong >= 2:
                sev = "A確実"
            elif strong == 1:
                sev = "B高"
            else:
                sev = "C中"
        else:
            sev = "E参考高(移籍で説明しにくい)" if (pubdiff and strong >= 2) else "F参考(先頭/末尾=移籍濃厚)"
        sev_n[sev] += 1
        for e in ev:
            ev_n[re.sub(r"(\d+y|\d+\(.*\)|\d+$|:.*)$", "", e)] += 1
        rows.append({
            "重症度": sev, "位置": pos, "証拠": "+".join(ev), "slug": slug, "題": ov["title"],
            "版type": ov["ed_type"], "版imprint": ov["ed_imprint"], "版publisher": ov["ed_publisher"],
            "版の巻数": str(len(valid)), "多数派帯": "978-4-%sx%d" % (maj, majn), "多数派社名": mp,
            "浮巻番号": str(k), "浮ISBN": ov["isbn13"], "浮帯": "978-4-" + ob, "浮帯の社名": op,
            "浮巻発売日": ov["release_date"],
            "前後の多数派": "%s→%s" % (
                ("%s巻%s" % (prev["number"], prev["release_date"][:7])) if prev is not None else "-",
                ("%s巻%s" % (nxt["number"], nxt["release_date"][:7])) if nxt is not None else "-"),
            "ズレ月": str(dev) if dev else "", "連番からの想定ISBN": want,
            "楽天題": rt, "楽天叢書": rs, "楽天出版社": rp})

    order = {"A確実": 0, "B高": 1, "C中": 2, "D低(同社/系列の別記号)": 3,
             "E参考高(移籍で説明しにくい)": 4, "F参考(先頭/末尾=移籍濃厚)": 5}
    rows.sort(key=lambda r: (order[r["重症度"]], -int(r["ズレ月"] or 0), r["slug"]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\t".join(COLS) + "\n")
        for r in rows:
            fh.write("\t".join(str(r[c]).replace("\t", " ").replace("\n", " ") for c in COLS) + "\n")
    print("\n該当 %d 巻 / %d 頁 → %s"
          % (len(rows), len(set(r["slug"] for r in rows)), os.path.relpath(OUT, ROOT)))
    for k in sorted(sev_n, key=lambda x: order[x]):
        print("   %s: %d" % (k, sev_n[k]))
    print("   証拠内訳:", dict(ev_n.most_common()))
    print("★自動修正しない。A→B→C の順に人が裁く。E/F は移籍で説明できるものが大半=参考。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
