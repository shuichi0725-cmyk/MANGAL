#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ISBN連番と巻番号の食い違い監査 (family = isbn-seq-vs-volume)。

■ 何を見るか
  日本の出版社は ISBN の「書名記号」(= 978-4-<出版者記号> の後ろ)を **登録順にほぼ
  単調増加で払い出す**。したがって *同じ出版者記号帯* の巻だけを取り出して巻番号順に
  並べれば、ISBN の数値もほぼ単調増加になるはずである。
  そこで「巻番号順に並べた書名記号の列」に対し **最長増加部分列(LIS)** を取り、
  LIS から漏れた巻 = ★列を壊している巻★ を逸脱巻として検出する。

■ なぜ要るか (= 既存検出器が見ていない角度)
  既存の日付系(_audit-date-disorder / _audit-vol-date-regression)は **発売日** を軸に
  見るため、★発売日が正しくて ISBN だけが間違っている★ 型を構造的に検出できない。
  実測でも逸脱巻の 96% は発売日が前後の巻と整合している(= 日付軸では無傷に見える)。
  ISBN は「その本が“いつ・どの棚で”登録されたか」の指紋なので、日付が綺麗に見える
  混入(特装版ISBNのすり替わり・別レーベル本の接ぎ木・誤ISBN)を独立に浮かせられる。

■ 分類 (= 列 `分類`)
  SPIKE_1     : 1巻だけが列を壊す。★本命(最も高確度)。
  SPIKE_N     : 2〜4巻が **互いに隣接せず** 単発で列を壊す(= 複数の単発混入)。
  HEAD_BLOCK  : 先頭側の連続ブロックが別帯 → 多くは出版社の払い出し帯の切替(正当)。
  TAIL_BLOCK  : 末尾側の連続ブロックが別帯 → 同上(版元移管/新体系への移行)。
  SCATTERED   : 壊れ方が広範 → 版混在(_audit-edition-mix の領域と重なる)。
  位置列 `位置` = 内部/先頭/末尾。★内部の SPIKE ほど強い(帯切替では説明できない)。

■ 優先度 (= 列 `優先度`。人はここを上から裁く)
  A  : SPIKE系 かつ 逸脱幅>=1000 かつ「別物が座っている」裏付けが1つ以上
       (楽天題に特装/限定/新装/外伝 等 or 発売日も逆行 or その帯はその年に使われていない
        or 楽天題が頁の題と別物)。★実測 100件・ほぼ真陽性。
  A2 : ISBNが隣接(差<=5)なのに巻番号順と逆で、日付も逆行 = ★巻番号の入れ替わり。
  B  : SPIKE系・逸脱大だが裏付け無し → ★下記の「並行払い出し帯」偽陽性が主。
  C  : SPIKE系・逸脱小(<1000) = 同時期払い出しの前後 = ほぼノイズ。
  D  : HEAD/TAIL_BLOCK・SCATTERED = 帯切替/版混在。

■ 既知の偽陽性型 (= 潰さずに列で見分けられるようにしてある)
  1. ★出版社の帯切替(最大の偽陽性源)。例=『バッテリー』角川 4-04-925xxx(2005-08)→
     4-04-104xxxx(2016-)。日付は単調増加なのに ISBN は大逆行する。→ HEAD/TAIL_BLOCK
     か、SPIKE でも `位置`=先頭/末尾 かつ `帯当年数` が大きい(= その帯はその年に現役)
     もので見分ける。
  2. ★★並行払い出し帯(= 優先度B の主因。2026-08-29 実踏)。1社が同時期に複数の帯を
     並行運用する。KADOKAWA は 4-04-1xxxxx と 4-04-81xxxx を同じ年に併用しており
     (ハイラのSP2 / フェイト・エクストラCCC5 = 楽天で正しい巻と確認済)、逸脱幅が
     70万でも正当。講談社(6-39xxxx / 6-3378xx / 6-51xxxx)・小学館・ぶんか社も同様。
     → `帯当年数`(その帯がその年に使われている冊数)が大きい行は疑ってかかる。
  3. ★同月同時発売の巻(上下巻・同日2冊)は払い出しが前後することがある。→ `逸脱幅` が
     小さい(数十〜数百)ものは実質ノイズ。`--min-dev` で切れる。
  4. ★特装版/限定版の帯(例: 小学館 978-4-09-94xxxx、小学館プラス・アンコミックス、
     講談社キャラクターズA)は年をまたいで使われるので「帯era差」では光らない。
     → 楽天キャッシュの題/叢書/判型を横に出して人が裁く。
     ※この型は既存の [[special_edition_fix_state]](種1 schema:version 権威)と**重なる**。
       本検出器は種1 version に依存しない独立signalなので、そちらの取りこぼし
       (残98件・新刊特装)を拾える位置づけ。実際 fantasista-stella は 8巻/10巻は
       variants に正しく畳まれているのに 9巻だけ特装ISBNが主枠に残っていた。
  5. 版type語(文庫/ワイド/新装…)が頁本来の版を指しているだけ → 頁の版type/imprintに
     同じ語があれば signal から外している(将棋の渡辺くん=ワイドKCで実測)。
  6. 楽天題との不一致は表記ゆれ(遙↔遥/RYU↔RYO/Candy・Candy↔キャンディ)で誤爆する →
     ルビ括弧除去+類似度0.55でしきい。英字題の頁は判定しない。
  7. ISBN-10→13 変換の名残・共同出版で帯が違う本 → 帯ごとに分けて評価しているので原則出ない。

■ 是正先 (= 本スクリプトは検出のみ。データは一切書き換えない)
  ・特装版ISBNのすり替わり → `data/seeds/special-edition-fix*.yml`(通常版主+variant併存)
  ・別作品/別レーベルの接ぎ木 → `edition-overrides.json` / `edition-canonical/*.yml`
  ・巻番号の誤りで列が壊れている → `volumes-supplement`(種4) or canonical で番号是正

入力 : .cache/volume-flat.tsv (本番全巻フラット。★69,210 yml は舐めない)
      .cache/rakuten-isbn-delta.jsonl / rakuten-isbn.jsonl (任意・1パスのみ)
出力 : docs/production-diagnostics/isbn-seq-vs-volume.tsv
使い方: python scripts/_audit-isbn-seq-vs-volume.py [--no-rakuten] [--min-dev 0]
月次 : 優先度A/A2 の**新規増加分**だけを見る(既存はper-caseで潰す台帳)。
"""
import argparse
import bisect
import collections
import csv
import json
import os
import statistics
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAT = os.path.join(ROOT, ".cache", "volume-flat.tsv")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "isbn-seq-vs-volume.tsv")
RAKUTEN = [os.path.join(ROOT, ".cache", "rakuten-isbn-delta.jsonl"),
           os.path.join(ROOT, ".cache", "rakuten-isbn.jsonl")]

# ★おまけ特装signal = 「通常版と別ISBNのおまけ付き版」を指す語。掲載中の版type
#   (standard/bunkobon/…)には決して現れないので、出れば無条件に「別物が座っている」証拠。
#   ★「小学館プラス・アンコミックス」「講談社キャラクターズA」は叢書名そのものが
#   おまけ付き版の受け皿なので語として入れてある(オレ様キングダム8/GIANT KILLING31で実測)。
OMAKE_WORDS = ("特装", "限定", "初回", "同梱", "ドラマcd", "dvd", "blu-ray",
               "小冊子", "アニメイト", "特別版", "缶バッジ", "アクリル",
               "プラス・アン", "プラスアン", "キャラクターズ")
# ★別フォーマットsignal = 版そのものを指す語。★その頁の版type/imprintが既に同じ語を
#   持つなら証拠にならない(将棋の渡辺くん=ワイドKCが本来の版、で実測した偽陽性)。
FORMAT_WORDS = ("新装", "完全版", "愛蔵", "文庫", "ワイド", "box", "総集",
                "別巻", "外伝", "番外")
ED_TYPE_JA = {"bunkobon": "文庫", "wideban": "ワイド", "kanzenban": "完全版",
              "shinsoban": "新装", "aizoban": "愛蔵"}

COLS = ["優先度", "分類", "位置", "slug", "題", "版idx", "版type", "imprint", "出版社",
        "ISBN帯", "版の巻数", "逸脱巻", "逸脱ISBN", "発売日", "前の正常ISBN",
        "次の正常ISBN", "逸脱幅", "日付整合", "帯era", "帯era差", "帯当年数",
        "楽天題", "楽天叢書", "楽天発売日", "楽天判型", "特装signal", "題不一致"]


def jp_pub_len(i):
    """978-4 の出版者記号長(可変長 2-7桁)。★固定長 slice は大手を誤分割する。"""
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
    return 4 + ln


def lis_keep(a):
    """狭義単調増加の最長増加部分列に残る index 集合を返す(O(n log n))。"""
    tails, tails_idx, prev = [], [], [-1] * len(a)
    for i, x in enumerate(a):
        j = bisect.bisect_left(tails, x)
        if j == len(tails):
            tails.append(x)
            tails_idx.append(i)
        else:
            tails[j] = x
            tails_idx[j] = i
        prev[i] = tails_idx[j - 1] if j > 0 else -1
    k = tails_idx[-1]
    keep = set()
    while k != -1:
        keep.add(k)
        k = prev[k]
    return keep


def year_of(d):
    return int(d[:4]) if len(d) >= 4 and d[:4].isdigit() else None


def _core(s):
    """題の照合キー: ★ルビ括弧を丸ごと落とす(聖闘士(セイント)星矢 型の偽不一致を殺す)
    → NFKC → ひら→カタ → 英小文字 → 記号/数字/空白を全部落とす。"""
    import re
    import unicodedata
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = re.sub(r"[(\[〔【][^)\]〕】]{0,12}[)\]〕】]", "", s)
    s = "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)
    return "".join(c for c in s if c.isalnum() and not c.isdigit())


def title_mismatch(page_title, rakuten_title):
    """★逸脱ISBNの実体(楽天題)が頁の題と別物か。別作品の接ぎ木を独立に裏付ける。
    ★既知偽陽性を潰してある:
      ・ルビ括弧 → _core で除去
      ・頁題が英字・楽天題が和文(Orfina↔オルフィーナ) → 英字のみの頁題は判定しない
      ・異体字/表記ゆれ(遙↔遥, RYU↔RYO, Candy・Candy↔キャンディ) → 類似度で吸収"""
    import difflib
    if not rakuten_title:
        return False
    a, b = _core(page_title), _core(rakuten_title)
    if len(a) < 3 or len(b) < 3 or a.isascii():
        return False
    if a in b or b in a:
        return False
    return difflib.SequenceMatcher(None, a, b).ratio() < 0.55


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-rakuten", action="store_true", help="楽天キャッシュ照合を省く")
    ap.add_argument("--min-dev", type=int, default=0,
                    help="逸脱幅がこれ未満の SPIKE を TSV から落とす(既定0=全件)")
    args = ap.parse_args()

    groups = collections.defaultdict(list)   # (slug, ed_idx, prefix) -> [巻]
    meta = {}                                # (slug, ed_idx) -> (題, type, imprint, 出版社)
    era = collections.defaultdict(list)      # (prefix, 帯先頭2桁) -> [年]

    n = 0
    with open(FLAT, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            n += 1
            if row["is_version"] == "1":
                continue          # 刷タブ由来のミラーは既知偽陽性なので除外
            isbn = row["isbn13"].strip()
            if len(isbn) != 13 or not isbn.startswith("9784"):
                continue          # 非9784 = _audit-foreign-editions の担当
            try:
                num = int(row["number"])
            except (TypeError, ValueError):
                continue
            if num < 1:
                continue          # 0巻/番外は後発刊行が普通 = 構造的偽陽性なので除外
            pl = jp_pub_len(isbn)
            code = isbn[pl:12]
            key = (row["slug"], row["ed_idx"], isbn[:pl])
            groups[key].append((num, int(code), row["release_date"], isbn, code))
            meta[(row["slug"], row["ed_idx"])] = (
                row["title"], row["ed_type"], row["ed_imprint"], row["ed_publisher"],
                row["ed_label"])
            y = year_of(row["release_date"])
            if y:
                era[(isbn[:pl], code[:2])].append(y)
    print("読込 {:,}行 / 帯グループ {:,}".format(n, len(groups)), flush=True)

    era_med = {k: statistics.median(v) for k, v in era.items() if len(v) >= 8}

    findings = []
    stat = collections.Counter()
    for key, vols in groups.items():
        slug, ed_idx, prefix = key
        nums = [v[0] for v in vols]
        if len(set(nums)) != len(nums):
            stat["skip_巻番号重複"] += 1     # ISBNダブリ/巻番号層の担当
            continue
        if len(vols) < 3:
            stat["skip_3巻未満"] += 1
            continue
        vols.sort()
        codes = [v[1] for v in vols]
        keep = lis_keep(codes)
        out = sorted(set(range(len(codes))) - keep)
        if not out:
            stat["OK"] += 1
            continue
        m = len(codes)
        if len(out) == 1:
            cls = "SPIKE_1"
        elif out == list(range(m - len(out), m)):
            cls = "TAIL_BLOCK"
        elif out == list(range(len(out))):
            cls = "HEAD_BLOCK"
        elif len(out) <= 4 and all(out[i + 1] - out[i] > 1 for i in range(len(out) - 1)):
            cls = "SPIKE_N"
        else:
            cls = "SCATTERED"
        stat[cls] += 1

        # 逸脱幅 = 前後の「正常」ISBN の範囲からどれだけ外れているか(最大)
        dev = 0
        for i in out:
            lo = max((codes[j] for j in keep if j < i), default=None)
            hi = min((codes[j] for j in keep if j > i), default=None)
            d = 0
            if lo is not None and codes[i] < lo:
                d = lo - codes[i]
            if hi is not None and codes[i] > hi:
                d = max(d, codes[i] - hi)
            dev = max(dev, d)
        i0 = out[0]
        lo0 = max((j for j in keep if j < i0), default=None)
        hi0 = min((j for j in keep if j > i0), default=None)
        # 位置 = 逸脱の塊が版の端に接しているか。★端に接するものは「払い出し帯の切替」で
        # 説明が付く(= 偽陽性型1)ので弱い。内部の逸脱は帯切替では説明できない=強い。
        if min(out) == 0:
            pos = "先頭"
        elif max(out) == m - 1:
            pos = "末尾"
        else:
            pos = "内部"

        # 日付整合 = 逸脱巻の発売日が前後の巻と矛盾していないか
        ds = [v[2][:7] for v in vols]
        dprev = max((ds[j] for j in range(i0) if ds[j]), default="")
        dnext = min((ds[j] for j in range(i0 + 1, m) if ds[j]), default="")
        if not ds[i0]:
            dok = "日付なし"
        elif (not dprev or ds[i0] >= dprev) and (not dnext or ds[i0] <= dnext):
            dok = "整合"
        else:
            dok = "★日付も逆行"

        blk = vols[i0][4][:2]
        med = era_med.get((prefix, blk))
        y = year_of(vols[i0][2])
        edelta = "" if (med is None or y is None) else str(int(abs(y - med)))
        # 帯当年数 = その帯(出版者記号×書名記号先頭2桁)が「逸脱巻の発売年±1」に
        # 実際に使われている本の数。★0 なら「その年その帯は生きていない」= 強い。
        # 逆に多ければ ★並行運用帯★(KADOKAWA 4-04-1xxxxx と 4-04-81xxxx 等)なので弱い。
        yrs = era.get((prefix, blk), ())
        live = "" if y is None else str(sum(1 for v in yrs if abs(v - y) <= 1))

        t, et, im, pub, lab = meta[(slug, ed_idx)]
        findings.append({
            "分類": cls, "位置": pos, "slug": slug, "題": t, "版idx": ed_idx,
            "版type": et, "imprint": im, "出版社": pub, "ISBN帯": prefix,
            "ed_label": lab,
            "版の巻数": m,
            "逸脱巻": ",".join(str(vols[i][0]) for i in out),
            "逸脱ISBN": ",".join(vols[i][3] for i in out[:4]),
            "発売日": vols[i0][2],
            "前の正常ISBN": vols[lo0][3] if lo0 is not None else "",
            "次の正常ISBN": vols[hi0][3] if hi0 is not None else "",
            "逸脱幅": dev, "日付整合": dok,
            "帯era": "" if med is None else str(int(med)), "帯era差": edelta,
            "帯当年数": live,
            "_isbn": vols[i0][3],
        })

    if args.min_dev:
        findings = [f for f in findings
                    if not f["分類"].startswith("SPIKE") or f["逸脱幅"] >= args.min_dev]

    # ---- 楽天キャッシュ 1パスで逸脱ISBNの実体(題/叢書/判型)を引く ----
    want = {f["_isbn"] for f in findings}
    got = {}
    if not args.no_rakuten:
        for path in RAKUTEN:
            if not os.path.exists(path) or len(got) >= len(want):
                continue
            print("楽天キャッシュ走査 {} ...".format(os.path.basename(path)), flush=True)
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    if len(line) < 30:
                        continue
                    p = line.find('"isbn": "')
                    if p < 0:
                        continue
                    isbn = line[p + 9:p + 22]
                    if isbn not in want or isbn in got:
                        continue
                    try:
                        it = json.loads(line).get("item") or {}
                    except Exception:
                        continue
                    got[isbn] = (it.get("title", ""), it.get("seriesName", ""),
                                 it.get("salesDate", ""), it.get("size", ""))
            print("  → {}/{} 件ヒット".format(len(got), len(want)), flush=True)

    for f in findings:
        t, s, d, sz = got.get(f["_isbn"], ("", "", "", ""))
        f["楽天題"], f["楽天叢書"], f["楽天発売日"], f["楽天判型"] = t, s, d, sz
        blob = (t + " " + s).lower()
        own = (f["版type"] + " " + f["ed_label"] + " " + f["imprint"]).lower()
        own += " " + ED_TYPE_JA.get(f["版type"], "")
        sig = [w for w in OMAKE_WORDS if w in blob]
        sig += [w for w in FORMAT_WORDS if w in blob and w not in own]
        f["特装signal"] = ",".join(sig)
        f["題不一致"] = "★別題" if title_mismatch(f["題"], t) else ""
        del f["_isbn"]
        del f["ed_label"]

    # ---- 優先度 (= 人が上から裁くための順) ----
    #  A : SPIKE系で逸脱が大きく、かつ「別物が座っている」裏付けsignalが1つ以上ある
    #      (楽天題が特装/限定/新装 or 発売日も逆行 or その帯はその年に使われていない)
    #  A2: ISBNが隣接(差<=5)なのに巻番号順と逆で、日付も逆行 = ★巻番号の入れ替わり
    #      (背景カタログ4/5型。逸脱幅は小さいが確度は高い)
    #  B : SPIKE系・逸脱大だが裏付けが無い → ★出版社の並行払い出し帯の疑い(要裏取り)
    #  C : SPIKE系・逸脱小 = 同時期の払い出し前後 = ほぼノイズ
    #  D : HEAD/TAIL_BLOCK・SCATTERED = 帯切替/版混在。既存検出器の領域と重なる
    for f in findings:
        spike = f["分類"].startswith("SPIKE")
        big = f["逸脱幅"] >= 1000
        live0 = f["帯当年数"] == "0"
        proof = (bool(f["特装signal"]) or f["日付整合"] == "★日付も逆行"
                 or live0 or f["題不一致"] == "★別題")
        if spike and f["逸脱幅"] <= 5 and f["日付整合"] == "★日付も逆行":
            f["優先度"] = "A2"
        elif spike and big and proof:
            f["優先度"] = "A"
        elif spike and big:
            f["優先度"] = "B"
        elif spike:
            f["優先度"] = "C"
        else:
            f["優先度"] = "D"

    order = {"SPIKE_1": 0, "SPIKE_N": 1, "SCATTERED": 2, "TAIL_BLOCK": 3, "HEAD_BLOCK": 4}
    pri = {"A": 0, "A2": 1, "B": 2, "C": 3, "D": 4}
    pos_order = {"内部": 0, "先頭": 1, "末尾": 1}
    findings.sort(key=lambda f: (pri[f["優先度"]], order[f["分類"]],
                                 pos_order.get(f["位置"], 9), -f["逸脱幅"]))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, delimiter="\t", lineterminator="\n")
        w.writeheader()
        for r in findings:
            w.writerow(r)

    print("\n出力: {}  ({:,}行)".format(OUT, len(findings)))
    for k, v in sorted(stat.items(), key=lambda kv: -kv[1]):
        print("  {:16s} {:,}".format(k, v))
    print("\n--- 分類 × 位置 ---")
    c2 = collections.Counter((f["分類"], f["位置"]) for f in findings)
    for k, v in sorted(c2.items()):
        print("  {:11s} {:3s} {:,}".format(k[0], k[1], v))
    print("\n--- 優先度 ---")
    for k, v in sorted(collections.Counter(f["優先度"] for f in findings).items()):
        print("  {:3s} {:,}".format(k, v))
    print("\n--- SPIKE(内部) の逸脱幅帯 ---")
    sp = [f for f in findings if f["分類"].startswith("SPIKE") and f["位置"] == "内部"]
    for th in (0, 300, 1000, 5000, 20000, 100000):
        a = sum(1 for f in sp if f["逸脱幅"] >= th)
        b = sum(1 for f in sp if f["逸脱幅"] >= th and f["特装signal"])
        print("  逸脱幅>={:<7} {:,} (うち特装signal有 {:,})".format(th, a, b))


if __name__ == "__main__":
    main()
