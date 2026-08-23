#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日次蒸留ドラフトの出荷前レビュー・ワークリスト生成 (= 2026-07-20 新設)

背景: 2026-07-20、日次蒸留86ドラフト中49件に問題(誤読slug/途中切り/未変換カタカナ/
既存作続巻の誤ドラフト化/非漫画すり抜け)。誤読・未変換は生成器が pending TSV に自動簿記
していたのに、実行が簿を消化せず preview へ push した=プロセス漏れ。
「判断力」でなく「消さないと push できない決定的ワークリスト」で塞ぐ。

このスクリプトは .preview-data/manga の**予約ドラフト(_preorder_draft 持ち)**を走査し、
機械で疑える点を1本のTSVに束ねる。exit 1 = 未裁定行あり(= push 禁止の合図)。

検知5種:
  CONTINUATION 題から巻マーカー(漢数字巻/上下/篇)を剥いた基底が**本番既存作と一致**
               (=既存頁の続巻を新規ドラフト化した疑い。千年狐十四/KATANA23型)→種4転送候補【最優先】
  NONMANGA     imprint が図鑑/絵本/写真集等 or 題が再編集本パターン(キャラクターリミックス等)【最優先】
  MISREAD      slug-gate-pending.tsv に載る かつ 題に漢字を含む(漢字誤読疑い。剣聖→ken-hijiri型)。
               英語/仮名のみの題は誤読しようがない=偽陽性なので除外
  KATA_UNCONV  slug-katakana-pending.tsv に載る かつ slug に4字以上のヘボン塊が残る(未変換カタカナ=wandaringu型)。
               造語(negaccho/hitonaa)は英語綴りが無いのが正=除外
  LONG_CHECK   slug が70字cap近く(len>=64)。語境界cut済でも意味の切れ目か目視(大半は正当な長題)

出力: docs/production-diagnostics/preorder-review.tsv
使い方: python scripts/_preorder-review.py [--src .preview-data/manga]
裁定後: 直した/除去した/問題なしと判断した行を消して再実行 → 0件で push可。
"""
import argparse, glob, io, json, os, re, sys, unicodedata
sys.stdout.reconfigure(encoding="utf-8")
import yaml
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "production-diagnostics", "preorder-review.tsv")
IDX = os.path.join(ROOT, "data", "manga-list-index.json")

# 既存作続巻の疑い: 題末尾の**巻番号**マーカーだけ剥いて基底題を得る。
# ★章/部 は剥がさない(第二章=新シリーズ立て=別頁が正。TOUGH第二章の誤検知 2026-07-20)。
#   巻(十四巻/23)・上下巻・(N) のみを続巻マーカーとみなす。
_KANNUM = "〇一二三四五六七八九十百千壱弐参零"
_VOLTAIL = re.compile(
    r"[\s　]*(?:第?\s*[0-9０-９" + _KANNUM + r"]{1,4}\s*巻?|[上中下][巻篇]?|"
    r"[（(][0-9０-９" + _KANNUM + r"]{1,4}[)）])[\s　]*$")
_SUBTAIL = re.compile(r"[\s　]*[〜～\-][^〜～]*[〜～]\s*$")   # 〜副題〜
# 非漫画: imprint / 題
_NONMANGA_IMPRINT = re.compile(r"図鑑|ずかん|絵本|写真集|画集|フォトブック|ムック|カレンダー|設定資料")
_NONMANGA_TITLE = re.compile(r"キャラクターリミックス|リミックス版|傑作選|傑作集|総集編|名場面|アンソロジー|ベストセレクション|公式ファンブック|設定資料")


def base_title(t):
    t = str(t or "").strip()
    for _ in range(4):
        t0 = t
        t = _SUBTAIL.sub("", t).strip()
        t = _VOLTAIL.sub("", t).strip()
        if t == t0:
            break
    return t


# ★強い正規化(2026-08-08 新設・姫騎士型): 既存頁の題とドラフト題の**表記差**を全部吸収して突合する。
#   base_title() は副題/巻を剥ぐだけなので、下記の差で完全一致を外し**続巻を新作として別頁化**していた:
#     ・全角/半角の記号差(「姫騎士がクラスメート**！**」↔ 既存頁「…**!**」)
#     ・コミカライズ表記(「 THE COMIC」「＠COMIC」「コミカライズ」)
#     ・巻数が題末尾に直結(「THE COMIC**10**」)
#   実害: 『姫騎士がクラスメート!』全9巻が既存なのに、10巻を1巻とする別頁を作った(ユーザ指摘)。
def hard_norm(t):
    t = unicodedata.normalize("NFKC", str(t or ""))
    t = re.sub(r"(THE\s*COMIC|@\s*COMIC|＠\s*COMIC|コミカライズ)", "", t, flags=re.I)
    t = re.sub(r"[0-9]+\s*$", "", t)
    t = re.sub(r"[\s　・!！?？:：〜~\-＆&。、．.,（）()【】\[\]『』「」]", "", t)
    return t.lower()


def _load_cont_fp():
    """同名別作品と裁定済みの組(=再フラグしない)。data/seeds/continuation-false-positive.tsv"""
    out = set()
    p = os.path.join(ROOT, "data", "seeds", "continuation-false-positive.tsv")
    if os.path.exists(p):
        for i, ln in enumerate(io.open(p, encoding="utf-8")):
            if i == 0 or not ln.strip():
                continue
            c = ln.rstrip().split(chr(9))
            if len(c) >= 2:
                out.add((c[0], c[1]))
    return out


_CONT_FP = _load_cont_fp()


def load_pending(name, col):
    p = os.path.join(ROOT, "docs", "production-diagnostics", name)
    out = set()
    if os.path.exists(p):
        for ln in io.open(p, encoding="utf-8"):
            parts = ln.rstrip("\n").split("\t")
            if len(parts) > col and parts[col]:
                out.add(parts[col])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=".preview-data/manga")
    a = ap.parse_args()

    # 本番既存の基底題集合(続巻検知の照合先)
    prod_bases = {}
    prod_hard = {}
    if os.path.exists(IDX):
        d = json.load(io.open(IDX, encoding="utf-8"))
        ti = d["f"].index("title"); si = d["f"].index("slug")
        for r in d["d"]:
            prod_bases.setdefault(base_title(r[ti]), r[si])
            prod_hard.setdefault(hard_norm(r[ti]), r[si])

    misread = load_pending("slug-gate-pending.tsv", 0)      # col0=slug
    kata = load_pending("slug-katakana-pending.tsv", 2)     # col2=slug

    rows = []
    for p in sorted(glob.glob(os.path.join(ROOT, a.src, "*.yml"))):
        d = yaml.safe_load(io.open(p, encoding="utf-8"))
        if not d or not d.get("_preorder_draft"):
            continue   # 予約ドラフトのみ対象(巻抜けスイープ等の本番コピーは除外)
        slug = d.get("slug") or os.path.basename(p)[:-4]
        title = d.get("title") or ""
        imp = " ".join(str(e.get("imprint") or "") for e in (d.get("editions") or []))
        has_kanji = bool(re.search(r"[一-鿿]", title))
        # 4字以上のヘボン塊(母音で終わるモーラ連続)がslug尾に残る=未変換カタカナの兆候
        kata_blob = bool(re.search(r"[bcdfghjklmnpqrstvwz]?[aiueo](?:[bcdfghjkmnprstwz][aiueo]){2,}", slug))
        # CONTINUATION / NONMANGA = 最優先(誤ページそのもの)
        bt = base_title(title)
        # ★偽陽性簿は基底題ルートにも効かせる(2026-08-14): 従来は下の hard_norm ルートだけが
        #   _CONT_FP を見ており、こちらは裁定済みでも毎回再フラグしてゲートが下りなかった
        #   (貴族転生 〜外伝 14歳ノアの無双旅行〜 = 副題を落とすと基底題が本編と一致する外伝)。
        if bt and bt != title and bt in prod_bases and (slug, prod_bases[bt]) not in _CONT_FP:
            rows.append(("CONTINUATION", slug, f"基底題『{bt}』=既存 {prod_bases[bt]}(続巻誤生成疑い→種4転送)", title))
        _hn = hard_norm(title)
        if _hn and _hn in prod_hard and prod_hard[_hn] != slug and (slug, prod_hard[_hn]) not in _CONT_FP:
            rows.append(("CONTINUATION", slug,
                         f"★正規化題が既存頁と一致『{prod_hard[_hn]}』(記号差/THE COMIC/末尾巻数を吸収)=続巻の誤新作化疑い→種4転送",
                         title))
        if _NONMANGA_IMPRINT.search(imp) or _NONMANGA_TITLE.search(title):
            hit = (_NONMANGA_IMPRINT.search(imp) or _NONMANGA_TITLE.search(title)).group()
            rows.append(("NONMANGA", slug, f"非漫画/編集本疑い(hit={hit})→deny候補", title))
        # MISREAD = 漢字題のみ(英語/仮名題は誤読しようがない)
        if slug in misread and has_kanji:
            rows.append(("MISREAD", slug, "題読み≠slug(漢字誤読疑い)", title))
        # KATA_UNCONV = 未変換カナ塊が残る時のみ(造語で英語綴りが無いのは正)
        if slug in kata and kata_blob:
            rows.append(("KATA_UNCONV", slug, "辞書未収載カタカナ(未変換)", title))
        # ★SLUG_MUSH(2026-08-23 ユーザ発見30件=isekairakuraku型): 無分割塊(ハイフン無し15字超run)
        #   or 78字超(80capの語中切断痕)は機械検出できる実問題=ブロッキング。
        #   根因は「短縮前のフル楽天題からslug生成」= 是正は題の意味の切れ目で再命名(rename)。
        _maxrun = max((len(x) for x in slug.split("-")), default=0)
        if _maxrun >= 15 or len(slug) >= 78:
            rows.append(("SLUG_MUSH", slug, f"無分割塊(run={_maxrun})/語中切り(len={len(slug)})→題の切れ目でrename", title))
        elif len(slug) >= 64:
            rows.append(("LONG_CHECK", slug, f"len={len(slug)} cap近=意味の切れ目か目視", title))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("class\tslug\tdetail\ttitle\n")
        for r in sorted(rows):
            f.write("\t".join(str(x) for x in r) + "\n")
    from collections import Counter
    c = Counter(r[0] for r in rows)
    n_draft = sum(1 for p in glob.glob(os.path.join(ROOT, a.src, "*.yml"))
                  if (yaml.safe_load(io.open(p, encoding="utf-8")) or {}).get("_preorder_draft"))
    # ★LONG_CHECK は情報(語境界cut済=大半は正当な長題)。push阻止は実問題4種のみ。
    BLOCK = {"CONTINUATION", "NONMANGA", "MISREAD", "KATA_UNCONV", "SLUG_MUSH"}
    n_block = sum(1 for r in rows if r[0] in BLOCK)
    print(f"予約ドラフト {n_draft}頁 / 要裁定 {n_block}件(ブロッキング) + LONG_CHECK {c.get('LONG_CHECK', 0)}件(情報) {dict(c)}")
    print(f"→ {os.path.relpath(OUT, ROOT)}")
    if n_block:
        print("★ブロッキング未裁定あり=push禁止。各行を直す(rename/kana修正)/除去(deny・種4転送)/"
              "問題なしと判断→pending簿の該当slug行を消す。0件でpush可。")
        sys.exit(1)
    print(f"✅ 出荷レビュー通過(ブロッキング0)。LONG_CHECK {c.get('LONG_CHECK', 0)}件は目視推奨だがpush可。")


if __name__ == "__main__":
    main()
