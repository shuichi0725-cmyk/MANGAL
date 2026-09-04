#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""予約ハーベストの分類 (= 2026-07-06 ユーザ設計の3分類+例外)

入力: .cache/preorders/preorders-latest.jsonl
分類:
  skip     既にページに載っているISBN
  ①zokkan  続巻: 題base+著者が既存ページと一致 → 種4自動追加の対象
  ②new1a   新作1巻・作者は索引に既存 → previewページ生成対象
  ③new1b   新作1巻・作者も新規 → previewページ生成対象(著者ヨミも楽天から)
  ex_mid   例外: 巻番号2以上なのにページ無し(取りこぼし) → 全巻回収フロー対象
出力: .cache/preorders/classified.json + docs/production-diagnostics/preorder-triage.tsv

★2026-09-02 恒久修正(日次蒸留で実踏した取り逃し/混入の型):
  - 特装版/限定版は**続巻でも skip**(種4に入れない)。通常版と同巻番号で二重化していた(ゆるゆり25/大室家9/コナン109 等11件)。
  - 引用符“”‘’を norm で除去(チェリー勇者と“せい”なる剣 10 が頁題と不一致→ex_mid に漏れた)。
  - 著者正規化 norm_author=末尾の♂♀☆★を剥ぐ(たかし♂ 型で著者ゲートが外れた)。
  - ③次マッチ=副題付き続巻。頁題が harvest 題の**先頭セグメント**(空白/ダッシュ/波ダッシュ/コロン、段落用の長音符「ー」で区切る)
    に一致 + 著者overlap + ★巻連続(頁max+1..+3)。ちいかわ なんか小さくてかわいいやつ(9)/捨てられた妃 めでたく…4/
    半グレ-六本木 摩天楼のレクイエム-16/漫画 ゆうえんち -バキ外伝-11 型。同じ書き出しのスピンオフ
    (僕の心のヤバイやつ ラブコメディが始まらない 2)は巻連続ゲートで落ちて ex_mid(全巻回収)に残る。
"""
import json, os, re, sys, unicodedata
from _idx_authors import au_name  # ★索引v2 authorsパック対応(2026-07-14)
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def norm(t):
    t = unicodedata.normalize("NFKC", str(t or ""))
    return re.sub(r"[\s　・!！?？:：〜~\-＆&。、．.『』「」“”‘’\"']", "", t).lower()


def norm_author(a):
    """著者名の正規化: norm + 末尾の性別/装飾記号(たかし♂ 型)を剥ぐ(2026-09-02)。"""
    return re.sub(r"[♂♀☆★]+$", "", norm(a))


# ★特装版/限定版(2026-09-02): 続巻でも種4に入れない。通常版と同巻番号で二重化する(特装版混入11件の型)。
SPECIAL_ED = re.compile(r"特装版|限定版|初回限定|豪華版|特別版|特典付|小冊子付|ドラマCD|CD付|DVD付|Blu-?ray|OAD|アクリル|しおり付|カードセット付|ポストカード|クリアスタンド|キーホルダー|フィギュア付", re.I)


def head_prefixes(base):
    """副題付き題の先頭セグメント候補(長い順)。区切り=空白/ダッシュ/波ダッシュ/コロン、および長音符「ー」が
    段落ダッシュとして使われた型(半グレー六本木=直後が非カナ)。題全体そのものは含めない(それは①②で照合済)。"""
    b = unicodedata.normalize("NFKC", str(base or "")).strip()
    cuts = {m.start() for m in re.finditer(r"[\s　]+|[-‐−–—~〜:：]|ー(?=[^ァ-ヶーｦ-ﾟ])", b)}
    out = []
    nb = norm(b)
    for i in sorted(cuts, reverse=True):
        pre = b[:i].strip(" 　-‐−–—~〜:：")
        npre = norm(pre)
        if len(npre) >= 2 and npre != nb and pre not in out:
            out.append(pre)
    return out


def norm_strip(t):
    """★設計台帳(型1 new_volume)準拠: 特装版/【】/〜サブタイトル〜/版名を剥がして正規化。
    ①zokkanの題完全一致が表記揺れ(特装版・編・サブ)で外れ④に漏れる問題の対処(2026-07-08)。"""
    t = unicodedata.normalize("NFKC", str(t or ""))
    t = re.sub(r"【[^】]*】", "", t)
    t = re.sub(r"[〜~][^〜~]*[〜~]", "", t)          # 〜サブタイトル〜
    t = re.sub(r"(特装版|限定版|愛蔵版|新装版|完全版|豪華版|特別版|通常版)", "", t)
    t = re.sub(r"[　\s]*[-ー]\s*[^-ー（(]{1,12}編\s*$", "", t)  # 末尾「-〇〇編」
    return re.sub(r"[\s　・!！?？:：〜~\-＆&。、．.『』「」]", "", t).lower()


def norm_loose(t):
    """★緩和正規化(④次マッチ専用・2026-09-04)。norm より強く畳むので**単独では使わない**=
    「候補が1件」+「巻連続(頁max+1..+3)」ゲートと必ず併用する。畳むのは実踏した3型だけ:
      - ルビ注記のカナ括弧を除去   旗(フラグ)を叩き折る ⇔ 旗を叩き折る
      - 角括弧の揺れを除去          [Heaven's Feel] ⇔ 〈Heaven's Feel〉
      - 長音符ーを除去              ハンドレッドノートーホークアイズー ⇔ ハンドレッドノート-ホークアイズ-
        (楽天が段落ダッシュに「ー」を使う型。カナ語中のーも一緒に落ちるので緩い=上のゲートが要る)"""
    t = unicodedata.normalize("NFKC", str(t or ""))
    t = re.sub(r"[（(][ぁ-んァ-ヶー]{1,12}[)）]", "", t)      # ルビ注記(数字の巻表記は落ちない)
    t = re.sub(r"[〈〉《》\[\]<>【】]", "", t)                 # 角括弧の揺れ
    return norm(t).replace("ー", "")


def auth_is_publisher(r):
    """★楽天の author が出版社名になっている(=著者未登録のplaceholder)か。2026-09-04 廻天のアルバス型。
    これを著者集合として扱うと①の著者一致ゲートが必ず外れ、続巻が④(途中巻)へ落ちて頁が更新されない。
    判定は「著者名が全部 publisher と同じ」に限定(=だろう運転をしない)。"""
    auths = [x.strip() for x in re.split(r"[/,、;；]", str(r.get("author") or "")) if x.strip()]
    pub = norm(r.get("publisher"))
    return bool(auths) and bool(pub) and all(norm(a) == pub for a in auths)


# ★scope外ゲート(2026-07-06 ユーザ指摘=特装版/アンソロ/N巻誤1巻化): これらは新作1巻(new1a/b)にしない
import re as _re
SCOPE_BAN = _re.compile(r"特装版|限定版|初回限定|豪華版|特別版|特典付|小冊子付|ドラマCD|CD付き?|DVD付|Blu-?ray|OAD|アンソロジ|総集編|選集|傑作|名作選|セレクション|新装版|愛蔵版|完全版|画集|イラスト集|ファンブック|設定資料|ガイドブック|公式ガイド|コミックガイド|データブック|ビジュアルブック|原画|ぬりえ|ムック|フィギュア付|BOXセット|ボックス|スターターセット|スペシャルプライス|語辞典|第?\s*[2-9２-９][0-9０-９]*\s*巻|第[二三四五六七八九十]+[集部]|(?:II|Ⅱ|III|Ⅲ|IV|Ⅳ|V|Ⅴ|VI|Ⅵ|VII|Ⅶ)\s*$|シーズン\s*[2-9]|[2-9]nd\s|3rd\s|第\d+号|別冊|【楽天ブックス限定特典】", _re.I)

VOLP = re.compile(r"[（(]\s*(\d{1,3})\s*[)）]\s*$|\s+(\d{1,3})\s*$|第\s*(\d{1,3})\s*巻\s*$")

from _preorder_title_lib import split_title as _split_title

def split_vol(title):
    """★分離器(2026-07-06): base正規化題と巻数。vol_suspect(直結数字)は巻2+扱いで安全側。"""
    r = _split_title(title)
    vol = r["vol"]
    if vol is None and r.get("vol_suspect") and r["vol_suspect"] >= 2:
        vol = r["vol_suspect"]  # ★安全側=巻扱い。真偽は同base他巻の存在(題名調査)で上流が判断可能
    if vol is None and r["part"] in ("中", "下"):
        vol = 2
    return norm(r["base"]), vol   # ★norm に統一(2026-09-02: 別コピーの正規表現が引用符“”を落とさず頁題と不一致になっていた)

# 既存資産
iidx = json.load(open(f"{ROOT}/.cache/isbn-page-index.json", encoding="utf-8"))
idx = json.load(open(f"{ROOT}/data/manga-list-index.json", encoding="utf-8"))
f = idx["f"]
si, ti, ai = f.index("slug"), f.index("title"), f.index("authors")
mvi = f.index("max_edition_volumes") if "max_edition_volumes" in f else None
tvi = f.index("total_volumes") if "total_volumes" in f else None
page_by_title = {}
page_by_stripped = {}   # ★設計台帳準拠の②次索引(特装版/サブ剥がし)
page_by_loose = {}      # ★④次索引(緩和正規化。巻連続ゲート必須) 2026-09-04
known_authors = set()
for r in idx["d"]:
    page_by_title.setdefault(norm(r[ti]), []).append(r)
    page_by_stripped.setdefault(norm_strip(r[ti]), []).append(r)
    page_by_loose.setdefault(norm_loose(r[ti]), []).append(r)
    for a in (r[ai] or []):
        known_authors.add(norm_author(au_name(a)))

def author_names(s):
    return [x for x in re.split(r"[/,、;；]", str(s or "")) if x.strip()]

rows = [json.loads(l) for l in open(f"{ROOT}/.cache/preorders/preorders-latest.jsonl", encoding="utf-8")]
out = {"skip": [], "zokkan": [], "new1a": [], "new1b": [], "ex_mid": []}
for r in rows:
    if r["isbn"] in iidx:
        out["skip"].append(r); continue
    base, vol = split_vol(r["title"])
    r["_base"], r["_vol"] = base, vol
    # ★特装版/限定版は続巻でも skip(2026-09-02): 通常版ISBNが別に来る(同巻番号の二重化を防ぐ)
    if SPECIAL_ED.search(str(r.get("title") or "")):
        r["reason"] = "特装版/限定版(続巻でも非掲載=通常版ISBNを待つ)"
        out["skip"].append(r); continue
    cands = page_by_title.get(base) or []
    # 著者一致ゲート(題だけの同題別作を弾く)
    r_auth = {norm_author(a) for a in author_names(r.get("author"))}
    match = None
    for c in cands:
        p_auth = {norm_author(au_name(a)) for a in (c[ai] or [])}
        if r_auth & p_auth or not r_auth:
            match = c; break
    if match:
        r["_slug"] = match[si]
        out["zokkan"].append(r); continue
    # ★設計台帳(型1 new_volume)②次マッチ: 特装版/【】/サブ剥がした正規化題+著者集合overlap。
    #   ①の完全一致が表記揺れで外れ④に漏れる問題の恒久対処(2026-07-08 ユーザ指摘)。著者一致必須で同題別作を弾く。
    if r_auth:
        sb = norm_strip(_split_title(r["title"])["base"])
        for c in page_by_stripped.get(sb, []):
            if r_auth & {norm_author(au_name(a)) for a in (c[ai] or [])}:
                match = c; break
        if match:
            r["_slug"] = match[si]
            out["zokkan"].append(r); continue
    # ★③次マッチ(2026-09-02): 副題付き続巻。頁題が先頭セグメントに一致 + 著者overlap + 巻連続(頁max+1..+3)。
    #   vol>=2 のみ(1巻/単巻の先頭一致は新シリーズ/スピンオフの可能性=新作扱いのまま)。
    if r_auth and vol is not None and vol >= 2 and mvi is not None:
        hit, hit_mx = None, None
        for pre in head_prefixes(_split_title(r["title"])["base"]):
            for c in (page_by_title.get(norm(pre)) or []) + (page_by_stripped.get(norm_strip(pre)) or []):
                if not (r_auth & {norm_author(au_name(a)) for a in (c[ai] or [])}):
                    continue
                try:
                    mx = max(int(c[mvi] or 0), int(c[tvi] or 0) if tvi is not None else 0)
                except Exception:
                    mx = 0
                if mx >= 1 and mx + 1 <= vol <= mx + 3:
                    hit, hit_mx = c, mx; break
            if hit:
                break
        if hit:
            r["_slug"] = hit[si]
            r["reason"] = f"③先頭セグメント一致(頁max{hit_mx}→巻{vol})"
            out["zokkan"].append(r); continue
    # ★④次マッチ(2026-09-04): ①〜③が「題の表記揺れ」「著者=出版社placeholder」で外れた続巻を拾う。
    #   緩和キーは畳みが強いので、★候補1件 かつ ★巻連続(頁max+1..+3) を必須ゲートにし同題別作の誤結線を防ぐ。
    #   著者は overlap があるか、楽天placeholder(著者=出版社名)のときだけ免除する。
    if mvi is not None and vol is not None and vol >= 2:
        _pl = auth_is_publisher(r)
        _lc = page_by_loose.get(norm_loose(_split_title(r["title"])["base"]), [])
        if len(_lc) == 1:
            c = _lc[0]
            p_auth = {norm_author(au_name(a)) for a in (c[ai] or [])}
            if (r_auth & p_auth) or _pl or not r_auth:
                try:
                    mx = max(int(c[mvi] or 0), int(c[tvi] or 0) if tvi is not None else 0)
                except Exception:
                    mx = 0
                if mx >= 1 and mx + 1 <= vol <= mx + 3:
                    r["_slug"] = c[si]
                    _why = "著者=出版社placeholder免除" if (_pl and not (r_auth & p_auth)) else "題の表記揺れ"
                    r["reason"] = f"④緩和一致({_why}, 頁max{mx}→巻{vol})"
                    out["zokkan"].append(r); continue
    if vol is not None and vol >= 2:
        out["ex_mid"].append(r); continue
    # ★裸数字N>=2末尾=続巻(2026-07-06 VOLSTRIP事故クラス): 題の一部数字(レベル99/U149=直前が英数字)は除く
    _bm = _re.search(r"[^A-Za-z0-9]\s*([2-9]|[1-9][0-9]{1,2})\s*$", str(r.get("title") or ""))  # 3桁対応(鬼平128漏れ 2026-07-06)
    if _bm:
        r["reason"] = f"裸数字末尾{_bm.group(1)}=続巻疑い(新作1巻にしない)"
        out["skip"].append(r); continue
    # ★巻表記が末尾以外に居る続巻の検出(2026-07-06 ユーザ発見=悪役令嬢99その六/アンゴルモア(13)博多編):
    #   題中間の(N) or ヨミ末尾ソノ漢数字/ダイNカン → 新作1巻にしない(skip=人判 or 次回title照合)
    _t_mid = _re.search(r"[（(]\s*([2-9]|[1-9][0-9])\s*[)）]", str(r.get("title") or ""))
    _k_end = _re.search(r"(ソノ(?:ニ|サン|ヨン|ゴ|ロク|ナナ|ハチ|キュウ|ジュウ)|ダイ[ニサンヨンゴロクナナハチキュウジュウ]+カン)\s*$", str(r.get("titleKana") or ""))
    if _t_mid or _k_end:
        r["reason"] = "巻表記が中間/ヨミのみ(続巻疑い=新作1巻にしない)"
        out["skip"].append(r); continue
    # ★コンビニ本レーベル(2026-07-06 ユーザ指摘): seriesName/レーベルで判定(題では分からない)
    _imp = str(r.get("seriesName") or "") + " " + str(r.get("label") or "")
    if _re.search(r"集英社リミックス|講談社プラチナコミックス|my\s*first\s*big|マイファーストビッグ|コンビニ|廉価|ジャンプ\s*リミックス|アンコール刊行|トップコミックスW|SPコミックスLEAD|(?:^|\s)Gコミックス", _imp, _re.I):
        r["reason"] = "コンビニ本レーベル"
        out["skip"].append(r); continue
    # ★scope外(特装版/アンソロ/セット/ガイド/N巻誤検出)は新作1巻にしない(2026-07-06)
    if SCOPE_BAN.search(str(r.get("title") or "")):
        r["reason"] = "scope外(特装/アンソロ/セット/再編/巻表記)"
        out["skip"].append(r); continue
    # 新作1巻(vol=1 or 単巻)
    if r_auth & known_authors:
        out["new1a"].append(r)
    else:
        out["new1b"].append(r)

json.dump(out, open(f"{ROOT}/.cache/preorders/classified.json", "w", encoding="utf-8"), ensure_ascii=False)
with open(f"{ROOT}/docs/production-diagnostics/preorder-triage.tsv", "w", encoding="utf-8") as fo:
    fo.write("class\tisbn\tym\ttitle\tauthor\tpublisher\tslug\treason\n")
    for k, lst in out.items():
        for r in lst:
            if k == "skip" and not r.get("reason"):
                continue   # ISBN既掲載の skip は簿に出さない。reason 付き skip(裸数字/特装版/scope外)は残す(2026-09-02)
            fo.write(f"{k}\t{r['isbn']}\t{r.get('ym')}\t{str(r['title'])[:40]}\t{str(r.get('author'))[:24]}\t{str(r.get('publisher'))[:16]}\t{r.get('_slug','')}\t{r.get('reason','')}\n")
print("分類:", {k: len(v) for k, v in out.items()})
print("→ .cache/preorders/classified.json + docs/production-diagnostics/preorder-triage.tsv")
