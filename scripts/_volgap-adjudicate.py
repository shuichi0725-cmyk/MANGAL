# -*- coding: utf-8 -*-
"""【巻抜け充填 裁定器】候補(楽天ローカル / NDL)に 追加3ゲートを当てて 適用リストを確定する。

前段が出す tier(ACCEPT/REVIEW/REVIEW_TOKEN/REJECT_EDITION/EXISTS/DROPPED/NOHIT)に対し、
版元prefixが引けない版(頁の既存巻にISBNが1本も無い)で効く追加ゲートを当てる:

 G6 版元名一致  : 候補の publisherName と 頁の版の publisher が一致するか
   → 曙出版の版に小学館ISBN(ダメおやじ) / サンケイ版に講談社ISBN(柔道一直線) /
     少年画報社キング・コミックスに小学館ISBN(怪物くん) / 1957年初出版に1991年アース出版局(赤胴鈴之助)
     を機械で落とす。 版元prefixが引ける版では既に G2 が同じ働きをしている
 G7 ISBN一意   : 同じISBNが2つ以上のターゲット(別版/別頁)に提案されていたら全部保留
   → ジャイアント台風で KCスペシャル版と ヒット・コミック版の両方に同じ9784061014640が出た
 G8 同レーベル重複: 同じ頁の**同じレーベル(imprint)**の別版が既にその巻番号を持っていたら保留
   → エースをねらえ!/東大一直線 のような「1本の刊行runが2つの版タブに割れている」頁(ARMS型)。
     片方に足すともう片方と二重表示になる。 割れ自体を先に直すのが筋なので巻は足さない

出力: docs/production-diagnostics/volgap-apply.tsv (decision=APPLY/HOLD/DROP)
使用: python scripts/_volgap-adjudicate.py [--in .cache/volgap-local-fill-v2.json] [--source rakuten-local]
"""
import os
import sys
import re
import json
from collections import Counter, defaultdict


def nisbn(x):
    return re.sub(r"[^0-9X]", "", str(x or "").upper())

import yaml

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "manga.v2")
IN = (sys.argv[sys.argv.index("--in") + 1] if "--in" in sys.argv
      else os.path.join(ROOT, ".cache", "volgap-local-fill-v2.json"))
SOURCE = sys.argv[sys.argv.index("--source") + 1] if "--source" in sys.argv else "rakuten-local"
OUT = (sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv
       else os.path.join(ROOT, "docs", "production-diagnostics", "volgap-apply.tsv"))

_PUBNORM = re.compile(r"[\s　\-−ー・,、.。()（）]|株式会社|有限会社|出版社$")
# 発売元/発行元の対(取次・レーベル運営が別会社の正当な組み合わせ)
# ★頁の題自体が掲載対象外(CLAUDE.md「MANGAL 掲載対象」)の語。巻を足す対象にしない
OUT_OF_SCOPE = ["ハンドブック", "キャラクターブック", "名鑑", "ガイドブック", "ファンブック",
                "設定資料集", "公式読本", "大百科", "解体新書"]
PUB_ALIAS = [
    {"星雲社", "アルファポリス"}, {"星雲社", "宙出版"}, {"日販アイ・ピー・エス", "ジーオーティー"},
    {"トーハン", "パブフル"}, {"サンクチュアリ出版", "サンクチュアリパブリッシング"},
]


def pnorm(s):
    return _PUBNORM.sub("", str(s or ""))


def pub_match(a, b):
    a, b = pnorm(a), pnorm(b)
    UNK = ("不明", "―", "-", "None")
    if not a or not b or a in UNK or b in UNK:
        return None            # 判定不能(片側でも不明なら断定しない)
    if a == b or a in b or b in a:
        return True
    for grp in PUB_ALIAS:
        g = {pnorm(x) for x in grp}
        if any(a == x or a in x or x in a for x in g) and any(b == x or b in x or x in b for x in g):
            return True
    return False


def norm_label(s):
    return re.sub(r"[\s　()（）]", "", str(s or ""))


# ★per-case 裁定(頁の版元が「不明」でG6が判定できない版。 2026-09-07 に1件ずつ実データを見て決めた)
#   キー = (SRC stem, edition index) / 値 = (decision, 理由)
OVERRIDE = {
    ("wild-7", 5): ("APPLY", "版のレーベル名『トクマコミックス・デラックス』が版元(徳間書店)を名指しし、"
                             "候補ISBNは全て 978-4-19-787xxxx(徳間)・1987年・巻番号と単調 = 同一run"),
    ("akadou-suzunosuke", 1): ("DROP", "版は『初出単行本(1957-59)』。候補はアース出版局1991年の復刻 = 別版"),
    ("dameoyaji", 0): ("DROP", "版のレーベルは Akebono-Comics(曙出版)。候補は小学館 = 別社の版"),
    ("dameoyaji", 2): ("DROP", "版のレーベルは AkeBono Comics(曙出版)。候補は小学館 = 別社の版"),
    ("jaiantotaifuu", 3): ("DROP", "版は『ヒット・コミック』(少年画報社系)。候補は講談社KCで、"
                                   "同ISBNが同頁の KCスペシャル版(講談社)に日付まで整合する = そちらが正"),
}


def main():
    rows = json.load(open(IN, encoding="utf-8"))
    cand = [r for r in rows if r["tier"] in ("ACCEPT", "REVIEW", "REVIEW_TOKEN")]
    print("裁定対象 {} 巻 (ACCEPT {} / REVIEW {} / REVIEW_TOKEN {})".format(
        len(cand), *[sum(1 for r in cand if r["tier"] == t)
                     for t in ("ACCEPT", "REVIEW", "REVIEW_TOKEN")]))

    # --- 頁の版構成(G8用) ---
    pageinfo = {}
    for stem in {r["stem"] for r in cand}:
        d = yaml.safe_load(open(os.path.join(SRC, stem + ".yml"), encoding="utf-8")) or {}
        eds = []
        for e in (d.get("editions") or []):
            nums = set()
            for vs in [e.get("volumes") or []] + [vv.get("volumes") or [] for vv in (e.get("versions") or [])]:
                for v in vs:
                    if v.get("number") is not None:
                        nums.add(v["number"])
            isbns = set()
            for vs in [e.get("volumes") or []] + [vv.get("volumes") or [] for vv in (e.get("versions") or [])]:
                for v in vs:
                    if v.get("isbn13"):
                        isbns.add(nisbn(v["isbn13"]))
            dates = {}
            for vs in [e.get("volumes") or []] + [vv.get("volumes") or [] for vv in (e.get("versions") or [])]:
                for v in vs:
                    if v.get("number") is not None and v.get("release_date"):
                        dates[v["number"]] = str(v["release_date"])
            eds.append({"type": e.get("type") or "standard", "label": e.get("label") or "",
                        "imprint": e.get("imprint") or "", "publisher": e.get("publisher") or "",
                        "nums": nums, "dates": dates, "isbns": isbns})
        pageinfo[stem] = {"eds": eds, "title": d.get("title", "")}

    out = []
    for r in cand:
        pi = pageinfo.get(r["stem"]) or {"eds": [], "title": ""}
        eds, ptitle = pi["eds"], pi["title"]
        ei = int(r["ei"])
        me = eds[ei] if ei < len(eds) else {}
        g6 = pub_match(r.get("rak_publisher"), me.get("publisher"))
        # G8: 同じ頁の同レーベルの別版が既にこの巻番号を持つ。
        #   ★ただし ISBN連番で位置が確定している時(g_isbn=o)は通す(あぶれもん= 754259<754266<754273)。
        #   止めるのは「隣の巻にISBNが無く帯を錨に取れない」頁だけ(エースをねらえ!/東大一直線)。
        myimp = norm_label(me.get("imprint") or me.get("label"))
        g8 = True
        if r.get("g_isbn") != "o":
            for j, e in enumerate(eds):
                if j == ei or not myimp:
                    continue
                if norm_label(e.get("imprint") or e.get("label")) == myimp and int(r["number"]) in e["nums"]:
                    g8 = False
                    break
        # G8c: 対象の版が**ISBNを1本も持たず**、同じ頁の**別のISBN無し版**が既にその巻番号を
        #   持つ = MADBのレーベル表記ゆれで1本の刊行runが2版に割れている(ぼくの動物園日記=
        #   「ジャンプ・コミックス」と「Jump comics」)。 足すと同じ本が二重に出る。
        #   ★片方がISBNを持つ頁(ワイルド7= 徳間書店版2001 と デラックス版1987)は別版が正当なので対象外。
        if g8 and not (me.get("isbns") or set()):
            for j, e in enumerate(eds):
                if j == ei or e.get("isbns"):
                    continue
                if int(r["number"]) in e["nums"]:
                    g8 = False
                    break
        # G8b: 同じ頁の別版に **同じ巻番号 かつ 同じ発売日** が在る = 同一の本を二重に載せることになる
        #   (プラモ狂四郎: KCデラックス版 v5=1990-05-17 と コミックボンボンデラックス版 v5 が同じ本)
        if g8 and r.get("date"):
            for j, e in enumerate(eds):
                if j == ei:
                    continue
                dd = e["dates"].get(int(r["number"]))
                if dd and dd[:10] == r["date"][:10] and len(r["date"]) >= 7 and len(dd) >= 7:
                    g8 = False
                    break

        dec, why = "APPLY", r["why"]
        ov = OVERRIDE.get((r["stem"], int(r["ei"])))
        if any(w in ptitle for w in OUT_OF_SCOPE):
            dec, why = "DROP", "頁自体が掲載対象外(キャラクターブック/ガイド類)= 巻を足す前に頁のdropを判断する"
        elif ov:
            dec, why = ov
        elif not g8:
            dec, why = "HOLD", "同じ頁の別版が既にこの巻を持つ=刊行run分裂頁(G8/G8b/G8c)"
        elif r["tier"] == "ACCEPT":
            dec = "APPLY"
        elif r["g_pub"] == "?" and g6 is False:
            dec, why = "DROP", "版元名が別(頁={} / 候補={})=別社の版(G6)".format(
                me.get("publisher"), r.get("rak_publisher"))
        elif r["g_pub"] == "?" and g6 is True:
            dec, why = "APPLY", "版元名一致+ISBN/日付整合(頁側にISBN無しのためprefixは不能)(G6)"
        elif r["tier"] == "REVIEW_TOKEN":
            dec, why = ("APPLY", "楽天題に巻番号は無いが版元o+ISBN連番o+日付o+著者o") if (
                r["g_pub"] == "o" and r["g_isbn"] == "o" and r["g_date"] == "o" and r["g_author"] == "o"
            ) else ("HOLD", r["why"])
        else:
            dec, why = "HOLD", r["why"]
        out.append({**r, "decision": dec, "g6": ("o" if g6 else ("x" if g6 is False else "?")),
                    "g7": "", "g8": ("o" if g8 else "x"),
                    "decision_why": why, "source": SOURCE})

    # --- G7: 同じISBNが2つ以上のターゲットに APPLY で提案されたら、証拠の多い方だけ残す ---
    byisbn = defaultdict(list)
    for r in out:
        if r["decision"] == "APPLY" and r["isbn"]:
            byisbn[r["isbn"]].append(r)
    for isbn, rs in byisbn.items():
        if len(rs) < 2:
            for r in rs:
                r["g7"] = "o"
            continue
        def oc(r):
            return sum(1 for k in ("g_pub", "g_isbn", "g_date", "g_author", "g6") if r.get(k) == "o")
        best = max(rs, key=oc)
        tie = [r for r in rs if oc(r) == oc(best)]
        for r in rs:
            if len(tie) > 1 or r is not best:
                r["decision"], r["g7"] = "HOLD", "x"
                r["decision_why"] = "同じISBNが複数の版に提案(G7)" + (
                    "= 証拠同点で全部保留" if len(tie) > 1 else "= 証拠の多い版を採用しこちらは保留")
            else:
                r["g7"] = "o"

    order = {"APPLY": 0, "HOLD": 1, "DROP": 2}
    out.sort(key=lambda r: (order[r["decision"]], r["stem"], int(r["number"])))
    cols = ["decision", "tier", "stem", "title", "route", "ei", "etype", "label", "imprint",
            "number", "kind", "isbn", "date", "rak_title", "rak_author", "rak_publisher",
            "publisher", "g_pub", "g_isbn", "g_date", "g_author", "g_token", "g6", "g7", "g8",
            "prev_num", "prev_isbn", "next_num", "next_isbn", "decision_why", "source", "cover"]
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(cols) + "\n")
        for r in out:
            f.write("\t".join(str(r.get(c, "")).replace("\t", " ") for c in cols) + "\n")
    js = OUT.replace("docs/production-diagnostics", ".cache").replace("\\docs\\production-diagnostics", "\\.cache")
    js = os.path.join(ROOT, ".cache", os.path.basename(OUT).replace(".tsv", ".json"))
    json.dump(out, open(js, "w", encoding="utf-8"), ensure_ascii=False)
    c = Counter(r["decision"] for r in out)
    print("=== 裁定 ===")
    for k in ("APPLY", "HOLD", "DROP"):
        print("  {:6} {:4} 巻 / {} 頁".format(k, c.get(k, 0),
                                              len({r["stem"] for r in out if r["decision"] == k})))
    print("APPLY の経路:", dict(Counter(r["route"] for r in out if r["decision"] == "APPLY")))
    print("→ " + OUT)


if __name__ == "__main__":
    main()
