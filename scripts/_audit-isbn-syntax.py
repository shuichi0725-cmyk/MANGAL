#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ISBN構文/チェックディジット監査 (family=isbn-syntax, 2026-08-29 新設)

★何を見るか
  isbn13 欄に入っている **値そのものが ISBN-13 として成立するか** だけを検査する。
  作品内容・巻構成・日付・重複は一切見ない。判定はすべて外部照会ゼロで完結する。
    CHECKDIGIT_BAD  13桁978/979だがチェックディジットが合わない = **実在しえない番号**(確定破損)
    DOUBLE_PREFIX   '978'/'979' の直後にまた '9784' が来る = 既に13桁のISBNに ISBN-10→13 変換を
                    二重適用した痕跡(確定破損)。★頭10桁で切られた値に to13() を掛けると
                    '978' + (元ISBNの頭9桁) + 再計算した検算桁 になり、**検算は通ってしまう**ので
                    チェックディジットでは絶対に捕まらない。構造で名指しするしかない。
                    副作用が凶悪で、元ISBNの頭9桁が同じ巻は**全部同じ値に潰れる**
                    (= 1つのISBNを十数巻が共有し、書影・在庫・ストア照合が全滅する)。
    JAN_CODE        13桁だが 45x/49x で始まる = 書籍JANでない **JANコード/インストアマーキング**。
                    値としては本物(ダイソー100円コミック等はISBNを持たずJANのみ)だが、
                    ISBN欄に入っている限り ISBN として引く全経路(書影/楽天/NDL)で必ず外れる。
    PREFIX_BAD      13桁だが 978/979/45x/49x のいずれでもない = 出所不明の数値
    ISBN10_IN_FIELD 10桁 = ISBN-10 を13桁欄に流用(ISBN-10検算OKなら確度最高、suggestに13桁を出す)
    SHIFT_FIXABLE   12桁で、先頭に '9'/'97'/'978' を補うと検算が通る = ゼロ落ち/桁ずれ
    LEN12/LEN_OTHER 桁数が13でない
    NONDIGIT        数字以外を含む / HYPHENATED 区切り文字が残っている
    CC_FOREIGN      ★構文は完全に正当だが 978-4(日本) 以外の国コード。**担当外=報告のみ**。

★なぜ既存検出器で足りないか(重複範囲を明示)
  - `_audit-foreign-editions.py` = 非9784を見るが目的は「外国語版をdropする」ことで、
    latin題 かつ 全ISBN非9784 かつ 複数巻 の三条件を要求する。**日本語題の作品に紛れた
    壊れた非9784値**(銀牙伝説Weedの 9789784537100 型)は条件を満たさず素通りする。
    本検出器は逆に「値の形」だけを見るので題も巻数も問わない。★正当な外国版(978-979=
    インドネシア語版はだしのゲン 等)は CC_FOREIGN として**報告のみ**にし、drop判断は向こうに委ねる。
  - `_audit-isbn-dup-internal.py` = 同一頁内の同ISBN重複。DOUBLE_PREFIX が**結果として**
    重複を生んだ場合だけ重なる(実際 銀牙伝説Weed は両方に出る)。**1巻しか壊れていない場合**や
    **壊れた値が重複していない場合**は向こうでは検出できない。
  - `_audit-missing-isbn.py` / `_audit-isbn-loss.py` = ISBNが「無い」ことを見る。
    「有るが値が壊れている」は見ていない(むしろ有るので健全に数えられてしまう)。
  - `_audit-publisher-vs-isbn.py` = ISBN出版者記号と出版社の食い違い。値が構文的に正しい前提。

★既知の偽陽性
  - CC_FOREIGN は原則すべて正当(978-979=インドネシア, 978-9xx 等)。担当外なので深追いしない。
  - 979-8 は Amazon KDP(個人出版)の正規ブロック。**日本語の個人出版漫画**が正当に持つ
    (ロイド/箱庭のザンテ/天涯のカロン/夫のみた幽霊 で実確認)。壊れではない。
  - 978-978 は **ナイジェリア**の正規グループなので、DOUBLE_PREFIX は '9784' が続く場合に
    限定している(9789782462916=ナイジェリア書 を誤検出しないため)。
  - ★不採用にした規則: 「9784+桁が0で埋まった値=ダミー」。9784800000002 は
    マッグガーデン(登録者記号8000)の**実在ISBN**(楽天で 殲鬼戦記ももたま7巻 と確認)で、
    登録者記号が 8000 の社は本文記号が 0000 から始まるため 0 が並ぶのは正常。初版で試して
    偽陽性と判明したので削除した。同じ罠を踏まないこと。
  - JAN_CODE は「値は本物・欄が違う」型。値を捏造扱いして消すと実在の商品情報が失われる。

★是正先(本検出器は検出のみ。データを一切変更しない)
  - layer=seed:edition-canonical/<SRC slug>.yml  → ★**ここが後勝ち**なので、種4や
    edition-overrides を直しても無効。canonical 本体の isbn13 を直す。
  - layer=seed2 (.cache/db-v2.sqlite)            → 種1(MADB metadata101)由来。per-case seed で上書き。
  - layer=production のみに在る値                 → promote 側の生成物を疑う。
  - ★恒久策: 反映ゲート(_reflect-targeted.py の検証)に本検出器の judge() を入れ、
    壊れたISBNを含む seed が push される前に止める。現状パイプラインに ISBN の
    チェックディジット検証は**一箇所も無い**(promote/reflect を grep で確認済)。

入力: .cache/volume-flat.tsv(本番全巻) / data/seeds/**(著者が書く層) / .cache/db-v2.sqlite(種2)
出力: docs/production-diagnostics/isbn-syntax.tsv
使い方:
  python scripts/_audit-isbn-syntax.py            # 全層
  python scripts/_audit-isbn-syntax.py --prod-only
"""
import csv
import io
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, ".cache", "volume-flat.tsv")
DB = os.path.join(ROOT, ".cache", "db-v2.sqlite")
SEEDS = os.path.join(ROOT, "data", "seeds")
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "isbn-syntax.tsv")

COLS = ["kind", "severity", "layer", "slug", "title", "ed_idx", "ed_type", "ed_imprint",
        "number", "isbn_raw", "suggest", "release_date", "has_cover", "is_version",
        "n_same_value", "detail"]

SEV = {"CHECKDIGIT_BAD": "確実な破損", "DOUBLE_PREFIX": "確実な破損",
       "NONDIGIT": "確実な破損", "LEN_OTHER": "確実な破損",
       "ISBN10_IN_FIELD": "要確認", "SHIFT_FIXABLE": "要確認", "LEN12": "要確認",
       "HYPHENATED": "要確認", "JAN_CODE": "要確認", "PREFIX_BAD": "要確認",
       "CC_FOREIGN": "担当外(報告のみ)", "KDP_979_8": "正当(報告のみ)"}
ORDER = {"DOUBLE_PREFIX": 0, "CHECKDIGIT_BAD": 1, "PREFIX_BAD": 2, "JAN_CODE": 3,
         "ISBN10_IN_FIELD": 4, "SHIFT_FIXABLE": 5, "LEN12": 6, "LEN_OTHER": 7,
         "NONDIGIT": 8, "HYPHENATED": 9, "CC_FOREIGN": 10, "KDP_979_8": 11}
# 国コード早見(CC_FOREIGN の説明用)
CC = {"9780": "英米", "9781": "英", "9782": "仏", "9783": "独", "9785": "露",
      "9786": "その他", "9787": "中", "9788": "西/伊/丁", "9789": "蘭/韓/尼/尼他",
      "9791": "仏(979)", "9798": "米Amazon KDP(個人出版)"}


def cd13(s12):
    """先頭12桁から ISBN-13 チェックディジットを算出。"""
    t = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(s12))
    return (10 - t % 10) % 10


def valid13(s):
    return len(s) == 13 and s.isdigit() and cd13(s[:12]) == int(s[12])


def valid10(s):
    """ISBN-10 検算(末尾 X 許容)。"""
    if len(s) != 10:
        return False
    t = 0
    for i, c in enumerate(s):
        if i == 9 and c in "Xx":
            v = 10
        elif c.isdigit():
            v = int(c)
        else:
            return False
        t += v * (10 - i)
    return t % 11 == 0


def to13(s10):
    core = "978" + s10[:9]
    return core + str(cd13(core))


def explain_bad_cd(s):
    """検算NGの13桁が、どんな単純誤りで説明できるかを返す(是正の手掛かり)。"""
    kinds = []
    for i in range(12):  # 隣接2桁の入れ替え(転置エラー)
        t = list(s)
        t[i], t[i + 1] = t[i + 1], t[i]
        if valid13("".join(t)):
            kinds.append("transpose@%d" % i)
            break
    pos = [i for i in range(12)
           if any(d != s[i] and valid13(s[:i] + d + s[i + 1:]) for d in "0123456789")]
    if pos:
        kinds.append("1digit@" + ",".join(str(p) for p in pos[:3]) + ("+" if len(pos) > 3 else ""))
    return ";".join(kinds) if kinds else "-"


def judge(s):
    """ISBN文字列を判定して (kind, detail, suggest) を返す。kind=None なら正当。
    ★反映ゲートから import して使えるよう、副作用なしの純関数にしてある。"""
    s = (s or "").strip()
    if not s:
        return None, "", ""
    compact = s.replace("-", "").replace(" ", "")
    if s != compact and compact.isdigit():
        return "HYPHENATED", "区切り文字が残っている", compact
    if not s.isdigit() and not (len(s) == 10 and valid10(s)):
        return "NONDIGIT", "数字以外を含む", ""
    if len(s) == 10:
        if valid10(s):
            return "ISBN10_IN_FIELD", "10桁(ISBN-10検算OK)=13桁欄への流用", to13(s)
        return "ISBN10_IN_FIELD", "10桁だがISBN-10検算もNG", ""
    if len(s) == 12:
        for pre in ("9", "97", "978"):
            cand = pre[:13 - len(s)] + s
            if valid13(cand):
                return "SHIFT_FIXABLE", "12桁: 先頭に'%s'を補うと検算OK" % pre[:13 - len(s)], cand
        if valid13(s + str(cd13(s))):
            return "LEN12", "12桁: 検算桁が落ちている", s + str(cd13(s))
        return "LEN12", "12桁", ""
    if len(s) != 13:
        return "LEN_OTHER", "%d桁" % len(s), ""
    if s[:3] in ("978", "979") and s[3:7] == "9784":
        # ★978/979 の直後にまた日本ISBNの頭(9784)。978-978=ナイジェリアと区別するため 9784 限定。
        return ("DOUBLE_PREFIX",
                "二重接頭辞: '978'+'%s'(=元ISBN13の頭9桁'%s'に to13 を再適用)。検算は通るが実在しない"
                % (s[3:13], s[3:12]),
                "元ISBNは %s… で始まる13桁(下4桁不明=要外部照会)" % s[3:12])
    if s[:2] in ("45", "49"):
        return "JAN_CODE", "書籍JANでないJANコード(%s…)。値は本物でもISBNとしては引けない" % s[:3], ""
    if not (s.startswith("978") or s.startswith("979")):
        return "PREFIX_BAD", "先頭3桁=%s%s" % (s[:3], "(検算はOK)" if valid13(s) else "(検算もNG)"), ""
    if not valid13(s):
        correct = s[:12] + str(cd13(s[:12]))
        return "CHECKDIGIT_BAD", "検算NG 正しい検算桁=%s 説明=%s" % (correct[12], explain_bad_cd(s)), correct
    if s[:4] == "9798":
        return ("KDP_979_8",
                "979-8 = Amazon KDP(個人出版)の正規ブロック。★日本語の個人出版漫画が正当に持つので"
                "「非9784=外国版」で落とさないこと(書影が付かないのはKDP本が楽天に無いため)", "")
    if not s.startswith("9784"):
        return "CC_FOREIGN", "国コード %s (%s)" % (s[:4], CC.get(s[:4], "?")), ""
    return None, "", ""


def scan_production(rows_out, stat):
    with io.open(SRC, encoding="utf-8", newline="") as f:
        recs = list(csv.DictReader(f, delimiter="\t"))
    stat["prod_vols"] = len(recs)
    stat["prod_isbn"] = sum(1 for r in recs if (r.get("isbn13") or "").strip())
    for r in recs:
        s = (r.get("isbn13") or "").strip()
        if not s:
            continue
        kind, detail, sug = judge(s)
        if not kind:
            CORPUS.add(s)
            continue
        rows_out.append({
            "kind": kind, "severity": SEV.get(kind, "?"), "layer": "production",
            "slug": r["slug"], "title": r["title"], "ed_idx": r["ed_idx"],
            "ed_type": r["ed_type"], "ed_imprint": r["ed_imprint"], "number": r["number"],
            "isbn_raw": s, "suggest": sug, "release_date": r["release_date"],
            "has_cover": r["has_cover"], "is_version": r["is_version"],
            "n_same_value": "", "detail": detail,
        })


SKIP_SEED = re.compile(r"^(anomaly-|audit-|needs-|resolve-|_raw-|.*-changelog)")
ISBN_KEY = re.compile(r'isbn(?:13)?["\']?\s*:\s*["\']?([0-9Xx\-]{8,20})')


def scan_seeds(rows_out, stat):
    """人が(または蒸留が)ISBNを**書き込む**層。ここで止めれば本番に流れない。"""
    n = 0
    for dp, dn, fn in os.walk(SEEDS):
        for f in fn:
            if not f.endswith((".yml", ".yaml", ".json", ".jsonl")):
                continue
            if SKIP_SEED.match(f):
                continue
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, ROOT).replace("\\", "/")
            try:
                txt = io.open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            for m in ISBN_KEY.finditer(txt):
                v = m.group(1).strip().strip("\"'")
                n += 1
                kind, detail, sug = judge(v)
                if not kind or kind in ("CC_FOREIGN", "KDP_979_8"):
                    continue  # seed層では外国版は判断材料にならない
                line = txt.count("\n", 0, m.start()) + 1
                rows_out.append({
                    "kind": kind, "severity": SEV.get(kind, "?"), "layer": "seed:" + rel,
                    "slug": os.path.splitext(f)[0], "title": "", "ed_idx": "", "ed_type": "",
                    "ed_imprint": "", "number": "L%d" % line, "isbn_raw": v, "suggest": sug,
                    "release_date": "", "has_cover": "", "is_version": "",
                    "n_same_value": "", "detail": detail,
                })
    stat["seed_isbn"] = n


def scan_seed2(rows_out, stat):
    if not os.path.exists(DB):
        return
    con = sqlite3.connect(DB)
    con.text_factory = lambda b: b.decode("utf-8", "replace")
    q = ("SELECT v.isbn13, s.title, e.imprint, v.number, v.release_date "
         "FROM volumes v JOIN editions e ON v.edition_id=e.id JOIN series s ON e.series_id=s.id "
         "WHERE v.isbn13 IS NOT NULL AND v.isbn13<>''")
    n = 0
    for i, t, im, num, rd in con.execute(q):
        n += 1
        kind, detail, sug = judge(str(i))
        if not kind:
            CORPUS.add(str(i))
            continue
        if kind in ("CC_FOREIGN", "KDP_979_8"):
            continue
        rows_out.append({
            "kind": kind, "severity": SEV.get(kind, "?"), "layer": "seed2",
            "slug": "", "title": t, "ed_idx": "", "ed_type": "", "ed_imprint": im or "",
            "number": num, "isbn_raw": str(i), "suggest": sug, "release_date": rd or "",
            "has_cover": "", "is_version": "", "n_same_value": "", "detail": detail,
        })
    stat["seed2_isbn"] = n
    con.close()


CORPUS = set()  # 全層で見つかった「構文的に正当な」ISBNの集合(近傍探索用)


def main():
    prod_only = "--prod-only" in sys.argv
    rows = []
    stat = {}
    scan_production(rows, stat)
    if not prod_only:
        scan_seeds(rows, stat)
        scan_seed2(rows, stat)

    # ★CHECKDIGIT_BAD は「検算桁を直す」より「1桁の打ち間違いを直す」が正解のことが多い。
    # 全層で実在する正当ISBNの集合と突き合わせ、1桁違い/隣接転置で当たる**実在の値**を出す。
    if CORPUS:
        for r in rows:
            if r["kind"] != "CHECKDIGIT_BAD":
                continue
            s = r["isbn_raw"]
            near = []
            for i in range(13):
                for d in "0123456789":
                    if d == s[i]:
                        continue
                    c = s[:i] + d + s[i + 1:]
                    if c in CORPUS:
                        near.append(c)
            for i in range(12):
                t2 = list(s)
                t2[i], t2[i + 1] = t2[i + 1], t2[i]
                c = "".join(t2)
                if c in CORPUS:
                    near.append(c)
            if near:
                near = sorted(set(near))
                r["suggest"] = ",".join(near[:3])
                r["detail"] += " ★実在する近傍ISBN=%s(検算桁を直すのでなくこちらが正解の可能性)" % near[0]

    # 同じ壊れた値を何巻が共有しているか(DOUBLE_PREFIX の凶悪さはここに出る)
    share = Counter(r["isbn_raw"] for r in rows if r["layer"] == "production")
    for r in rows:
        r["n_same_value"] = share.get(r["isbn_raw"], "") if r["layer"] == "production" else ""

    def nn(v):
        try:
            return int(v)
        except Exception:
            return -1

    rows.sort(key=lambda x: (ORDER.get(x["kind"], 99), x["layer"], x["slug"],
                             nn(x["ed_idx"]), nn(x["number"])))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, delimiter="\t", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)

    prod = [r for r in rows if r["layer"] == "production"]
    real = [r for r in prod if r["kind"] not in ("CC_FOREIGN", "KDP_979_8")]
    print("本番: 総巻=%d / isbn13あり=%d" % (stat.get("prod_vols", 0), stat.get("prod_isbn", 0)))
    if not prod_only:
        print("seed層 isbn出現=%d / 種2 isbn=%d" % (stat.get("seed_isbn", 0), stat.get("seed2_isbn", 0)))
    print("--- kind別 (層 x 件数) ---")
    tab = defaultdict(Counter)
    for r in rows:
        tab[r["kind"]]["seed" if r["layer"].startswith("seed:") else r["layer"]] += 1
    for k in sorted(tab, key=lambda x: ORDER.get(x, 99)):
        c = tab[k]
        print("  %-16s %-14s production=%-5d seed=%-4d seed2=%-4d"
              % (k, SEV.get(k, ""), c.get("production", 0), c.get("seed", 0), c.get("seed2", 0)))
    print("--- 本番の集計 ---")
    print("  担当外(CC_FOREIGN)を除く flag巻数 = %d / flag頁数 = %d"
          % (len(real), len({r["slug"] for r in real})))
    print("  うち書影欠落 = %d" % sum(1 for r in real if r["has_cover"] == "0"))
    print("  CC_FOREIGN(=_audit-foreign-editions.py 担当) = %d巻"
          % sum(1 for r in prod if r["kind"] == "CC_FOREIGN"))
    print("  KDP_979_8(正当・個人出版) = %d巻"
          % sum(1 for r in prod if r["kind"] == "KDP_979_8"))
    print("-> %s" % OUT)


if __name__ == "__main__":
    main()
