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
import sys as _sys_h
if any(_a in ("-h", "--help") for _a in _sys_h.argv[1:]):   # ★--help で本体を走らせない(2026-10-03 apply-zokkan を誤実行し touched を空で上書き)
    print(__doc__ or "(no doc)"); _sys_h.exit(0)
import json, os, re, sys, unicodedata
from _idx_authors import au_name  # ★索引v2 authorsパック対応(2026-07-14)
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def norm(t):
    t = unicodedata.normalize("NFKC", str(t or ""))
    return re.sub(r"[\s　・!！?？:：〜~\-＆&。、．.『』「」“”‘’\"']", "", t).lower()


def norm_author(a):
    """著者名の正規化: norm + 末尾の性別/装飾記号(たかし♂ 型)を剥ぐ(2026-09-02)。
    ★括弧書き(スタジオ/レーベル注記)も剥ぐ(2026-10-06): 楽天は「孟倫（SDwing）」「Stonehead(AKEO STUDIO)」
      「希羅月(Comicloft)」と書き、頁は「孟倫」「Stonehead」= 著者が合わず既存頁の続巻が途中巻(ex_mid)に落ちていた
      (僕のカノジョ先生18・末っ子皇女殿下10 等10冊)。"""
    a = re.sub(r"[（(][^）)]*[）)]", "", str(a or ""))
    a = re.sub(r"(?:ほか|他)\s*$", "", a)   # ★「三条陸ほか」型(2026-10-08 風都探偵21): 末尾の「ほか」は名前ではない
    return re.sub(r"[♂♀☆★]+$", "", norm(a))


def auth_truncated(r):
    """★楽天の著者欄が「…ほか」で切れている(=載っていない著者がいる)か。2026-10-08 風都探偵（21）型:
    楽天「石ノ森章太郎/三条陸ほか」・頁は作画の「佐藤まさき」だけ= 重なりが無いのは別作品の証拠にならない。
    ④次マッチ(候補1件+巻連続ゲート付き)でだけ著者一致を免除する。"""
    return bool(re.search(r"(?:ほか|他)\s*$", str(r.get("author") or "")))


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
    t = re.sub(r"(?:@\s*COMIC|THE\s+COMIC)\s*$", "", t.strip(), flags=re.I)   # ★@COMIC尾(2026-10-08 最弱テイマー…＠COMIC 第9巻 型)
    return norm(t).replace("ー", "")


def author_similar(a, b):
    """★著者名の表記ゆれ(2026-10-08): 常盤ギヨ⇔常盤魚 / saku⇔saku漫画家 / 和田フミ江⇔和田フミエ。
    楽天とMADBで同じ人の書き方が違う。一致・前方一致・共通の先頭2字以上(短い方の長さ-2以上)を「似ている」とする。
    ★これ単独では使わない= 題の候補1件+巻連続ゲート(⑤次マッチ)と必ず組む(同姓の別人を拾いうる緩さなので)。"""
    if not a or not b:
        return False
    if a == b:
        return True
    s, l = sorted((a, b), key=len)
    if len(s) >= 2 and l.startswith(s):
        return True
    cp = len(os.path.commonprefix([a, b]))
    return cp >= 2 and cp >= len(s) - 2


def auth_is_publisher(r):
    """★楽天の author が出版社名になっている(=著者未登録のplaceholder)か。2026-09-04 廻天のアルバス型。
    これを著者集合として扱うと①の著者一致ゲートが必ず外れ、続巻が④(途中巻)へ落ちて頁が更新されない。
    判定は「著者名が全部 publisher と同じ」に限定(=だろう運転をしない)。"""
    auths = [x.strip() for x in re.split(r"[/／,、;；]", str(r.get("author") or "")) if x.strip()]
    pub = norm(r.get("publisher"))
    return bool(auths) and bool(pub) and all(norm(a) == pub for a in auths)


# ★scope外ゲート(2026-07-06 ユーザ指摘=特装版/アンソロ/N巻誤1巻化): これらは新作1巻(new1a/b)にしない
import re as _re
SCOPE_BAN = _re.compile(r"特装版|限定版|初回限定|豪華版|特別版|特典付|小冊子付|ドラマCD|CD付き?|DVD付|Blu-?ray|OAD|アンソロジ|総集編|選集|傑作|名作選|セレクション|新装版|愛蔵版|完全版|画集|イラスト集|ファンブック|設定資料|ガイドブック|公式ガイド|コミックガイド|データブック|ビジュアルブック|原画|ぬりえ|ムック|フィギュア付|BOXセット|ボックス|スターターセット|スペシャルプライス|語辞典|第?\s*[2-9２-９][0-9０-９]*\s*巻|第[二三四五六七八九十]+[集部]|(?:II|Ⅱ|III|Ⅲ|IV|Ⅳ|V|Ⅴ|VI|Ⅵ|VII|Ⅶ)\s*$|シーズン\s*[2-9]|[2-9]nd\s|3rd\s|第\d+号|別冊|【楽天ブックス限定特典】", _re.I)

VOLP = re.compile(r"[（(]\s*(\d{1,3})\s*[)）]\s*$|\s+(\d{1,3})\s*$|第\s*(\d{1,3})\s*巻\s*$")
# ★版違いの語(2026-10-08): 途中巻ゲートと新作の SCOPE_BAN の両方で使う。Perfect Edition=完全版の英語表記(エロイカ型)。
EDITION_VARIANT = _re.compile(r"新装版|愛蔵版|完全版|復刻版|オリジナル版|Perfect\s*Edition|パーフェクト[・\s]?エディション", _re.I)
# ★オリジナル版(2026-10-08 手塚治虫 ミッシング・ピーシズ 地球を呑む[オリジナル版] = 既存頁『地球を呑む』の別版)

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
    return [x for x in re.split(r"[/／,、;；]", str(s or "")) if x.strip()]

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
        _tr = auth_truncated(r)
        _lc = page_by_loose.get(norm_loose(_split_title(r["title"])["base"]), [])
        if len(_lc) == 1:
            c = _lc[0]
            p_auth = {norm_author(au_name(a)) for a in (c[ai] or [])}
            if (r_auth & p_auth) or _pl or _tr or not r_auth:
                try:
                    mx = max(int(c[mvi] or 0), int(c[tvi] or 0) if tvi is not None else 0)
                except Exception:
                    mx = 0
                if mx >= 1 and mx + 1 <= vol <= mx + 3:
                    r["_slug"] = c[si]
                    _why = ("著者=出版社placeholder免除" if (_pl and not (r_auth & p_auth))
                            else "著者欄が「ほか」で切れている=免除" if (_tr and not (r_auth & p_auth)) else "題の表記揺れ")
                    r["reason"] = f"④緩和一致({_why}, 頁max{mx}→巻{vol})"
                    out["zokkan"].append(r); continue
    # ★⑤次マッチ(2026-10-08): 著者名の表記ゆれで①〜④が外れた続巻(織田ちゃんと明智くん9=常盤ギヨ⇔常盤魚 /
    #   キミに恋する三姉妹10=saku⇔saku漫画家 / 婚活とミシン4=和田フミ江⇔和田フミエ)。題(全体 or 先頭セグメント)が
    #   緩和キーで頁と一致し、著者が「似ている」候補が★ちょうど1件 かつ ★巻連続(頁max+1..+3) の時だけ。
    if mvi is not None and vol is not None and vol >= 2 and r_auth:
        _b0 = _split_title(r["title"])["base"]
        _cands = {}
        for _k in [norm_loose(_b0)] + [norm_loose(p) for p in head_prefixes(_b0)]:
            for c in page_by_loose.get(_k, []):
                _cands[c[si]] = c
        _hits = []
        for c in _cands.values():
            p_auth = {norm_author(au_name(a)) for a in (c[ai] or [])}
            if not any(author_similar(x, y) for x in r_auth for y in p_auth):
                continue
            try:
                mx = max(int(c[mvi] or 0), int(c[tvi] or 0) if tvi is not None else 0)
            except Exception:
                mx = 0
            if mx >= 1 and mx + 1 <= vol <= mx + 3:
                _hits.append((c, mx))
        if len(_hits) == 1:
            c, mx = _hits[0]
            r["_slug"] = c[si]
            r["reason"] = f"⑤著者表記ゆれ一致(頁著者={'/'.join(au_name(a) for a in (c[ai] or []))}, 頁max{mx}→巻{vol})"
            out["zokkan"].append(r); continue
    if vol is not None and vol >= 2:
        # ★版違いの途中巻(2026-10-08 佐武と市捕物控〈完全版〉（3）/ エロイカより愛をこめて Perfect Edition 2..8 型):
        #   既存頁の別版(タブ)の可能性が高い。途中巻回収(gen-midfill)に回すと「〈完全版〉」付きの別頁を新しく作ってしまう
        #   (版は同じ頁のタブ= CLAUDE.md 表示sort仕様)。続巻判定(①〜④)で頁が見つからなかった版違いだけ保留簿へ。
        if EDITION_VARIANT.search(str(r.get("title") or "")):
            r["reason"] = "版違い(完全版/新装版/愛蔵版/Perfect Edition等)の途中巻=既存頁の版タブ候補→人裁定(別頁を作らない)"
            out["skip"].append(r); continue
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
    #   2026-09-14 追加: ポケットワイド(リイド社SPコミックス=ゴルゴ13テーマ別再録。2026-09-02裁定でgolgo-13-shorty等drop済)
    #   / Coinsアクション(双葉社コンビニ版。2026-09-07にクレヨンしんちゃんパニック!をdeny済)。
    #   ★このゲートは続巻判定(上の①〜④)より後なので、既存頁の続巻は従来どおりzokkanに流れる=新規頁化だけを止める。
    _imp = str(r.get("seriesName") or "") + " " + str(r.get("label") or "")
    if _re.search(r"集英社リミックス|講談社プラチナコミックス|my\s*first\s*big|マイファーストビッグ|コンビニ|廉価|ジャンプ\s*リミックス|アンコール刊行|トップコミックスW|SPコミックスLEAD|(?:^|\s)Gコミックス|ポケットワイド|Coins\s*アクション", _imp, _re.I):
        r["reason"] = "コンビニ本レーベル"
        out["skip"].append(r); continue
    # ★scope外(特装版/アンソロ/セット/ガイド/N巻誤検出)は新作1巻にしない(2026-07-06)
    if SCOPE_BAN.search(str(r.get("title") or "")) or EDITION_VARIANT.search(str(r.get("title") or "")):
        r["reason"] = "scope外(特装/アンソロ/セット/再編/版違い/巻表記)"
        out["skip"].append(r); continue
    # 新作1巻(vol=1 or 単巻)
    if r_auth & known_authors:
        out["new1a"].append(r)
    else:
        out["new1b"].append(r)

# ★続巻経路の非漫画ゲート(2026-10-08 ドラミちゃん かわいいポスターコレクション2 型): scope外の語(ポスター本/画集/ガイド等)は
#   新作経路(生成器)でしか見ておらず、③先頭セグメント一致で頁『ドラミちゃん』(1巻)の2巻として種4へ入るところだった。
#   ★語が**頁題にも在る**時は題の一部なので止めない(ハンドレッドノート型=「ノート」が作品名)。harvest題だけに在る時だけ skip。
from _preorder_draft_lib import scope_out as _scope_out
_title_by_slug = {r[si]: r[ti] for r in idx["d"]}
_keep_z = []
for r in out["zokkan"]:
    if _scope_out(r.get("title")) and not _scope_out(_title_by_slug.get(r.get("_slug"), "")):
        r["reason"] = f"scope外(非漫画=頁題に無い語)の続巻疑い slug={r.get('_slug')}"
        out["skip"].append(r)
    else:
        _keep_z.append(r)
out["zokkan"] = _keep_z

# ★再投入行(2026-10-06 _preorder-increment.py が付ける _requeue)は「既存頁の続巻」と判定された時だけ適用に回す。
#   新作(new1a/new1b)・途中巻(ex_mid)に落ちた行は過去に見送った分 = ここでドラフト生成に渡すと backlog を毎回「新規」に
#   水増しする(previewは今回分のみの規則)。 → requeue_hold に退避して簿にだけ出す(生成器は読まない)。
out["requeue_hold"] = []
for k in ("new1a", "new1b", "ex_mid"):
    keep = []
    for r in out[k]:
        if r.get("_requeue"):
            r["reason"] = f"再投入={k}(続巻でない=保留見直しの流れで扱う)"
            out["requeue_hold"].append(r)
        else:
            keep.append(r)
    out[k] = keep
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
