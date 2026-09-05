#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""予約ドラフト整形の共通ライブラリ(2026-07-09 全面作り直し)。

今日のユーザ指摘8点への恒久対処:
  1. 〜副題〜 / ～副題～ を副題として分離(slug/kanaに入れない)
  2. slug=分かち書き(pykakasi語境界 or 楽天titleKanaのスペース)でハイフン区切り
  3. title_kana=カタカナのみ(ひらがな→カタカナ変換、漢字残る=捏造→None返し=hold)
  4. slug空→None(hold)。"2026"だけのゴミslug禁止
  5. 英語はそのまま(STRAY等・pykakasiがローマ字化しない英字は保持)
  6. 末尾@COMIC / (仮) / 巻番号 を題からもkanaからも除去
  7. genreは楽天caption経由(enrich)=ここでは空。demographic=subgenre写像
  8. pykakasi(汎用装置)を使う。手書きK2Rでなく。

使い方: from _preorder_draft_lib import clean_title, clean_kana, make_slug
"""
import re
import unicodedata

try:
    import pykakasi
    _KKS = pykakasi.kakasi()
except Exception:
    _KKS = None

# ★末尾の巻表示(2026-08-08 大幅拡張。それまで取りこぼしていた型をユーザに次々指摘された):
#   旧: (N) / 第N巻 / 空白+N / かな漢字の直後のN  だけ
#   追加: **(全N)/(全N巻)/(N巻)**(温泉シャーク(全1)・Mother(全1)・ツノカクシ(全1)・エドゼニ(1巻)) /
#         **ラテン・記号の直後の裸数字**(THE COMIC10 / ズバババァーン!!1) /
#         **上下中・前後編**(ムジナの城（上）・サムライトルーパー 上)。
#   ★巻表示は題ではないので必ず剥がす。剥がし忘れると「よけいな文字」として表示に出る。
_VOL_TAIL = re.compile(
    r"(?:[（(]\s*全?\s*\d{1,3}\s*巻?\s*[)）]"          # (1) (全1) (1巻) (全1巻)
    r"|[（(]\s*第?\s*[一二三四五六七八九十百]+\s*巻\s*[)）]"  # ★漢数字の巻表示(一巻)(第三巻) 2026-09-04
    r"|第\s*\d{1,3}\s*巻"                               # 第1巻
    r"|[\s　]+全?\d{1,3}"                               # 空白+1 / 空白+全1
    r"|(?<=[ぁ-んァ-ヶ一-鿿])\d{1,3}"                   # かな漢字の直後の裸数字(既存)
    r"|[\s　]*[（(](?:(?:上|下|中)巻?|前編|後編)[)）]"     # ★括弧付きの上下中(巻付き可)・前後編
    r"|[\s　]+(?:(?:上|下|中)巻|前編|後編)"                # ★空白+上下中巻・前後編
    r"|[\s　]+(?:上|下|中)"                              # ★空白+上下中(裸)
    r")\s*$")
# ★**ラテン/記号の直後の裸数字は剥がさない**(2026-08-08 検討して却下)。
#   「THE COMIC10」型は剥がしたいが、同じ規則が「ワイルド7」「AKIRA1」型の**題に含まれる数字**を壊す。
#   数字の剥離は本質的に曖昧なので、**曖昧な型は簿(出荷前レビュー)に回して人が裁く**方針にする。
#   ★なお既存の「かな漢字の直後の裸数字」も「ワイルド7」→「ワイルド」と壊す既知の穴だが、
#   長年の挙動なので今回は触らない(変えると別の回帰が出る)。新規題に数字が付く作品は簿で拾うこと。
_SUB = re.compile(r"[\s　]*[〜～\-][^〜～]*?[〜～]\s*$")   # 〜副題〜 / ～副題～
_ATCOMIC = re.compile(r"(?:[@＠]\s*comic|[\s　]+THE\s+COMIC)\s*$", re.I)  # ★「〜 THE COMIC」尾も剥離(ユーザ裁定 2026-07-15)
_PROV = re.compile(r"[（(]\s*仮\s*[)）]")


_SCOPE_OUT = re.compile(r"めくり|カレンダー|ぬりえ|塗り絵|写真集|画集|イラスト集|ファンブック|設定資料|ガイドブック|公式ガイド|データブック|ビジュアルブック|原画集|ムック|フィギュア|カードゲーム|トレカ|グッズ|下敷き|ノート|手帳|大事典|大百科|大図鑑|名鑑|(?:^|\s)artbook", re.I)  # ★大事典型=関連書(ドラえもんひみつ道具大事典すり抜け 2026-07-15)


def scope_out(title):
    """漫画でない(カレンダー/画集/グッズ等)=Trueなら掲載対象外。"""
    return bool(_SCOPE_OUT.search(str(title or "")))


# ★評論/研究書ゲート(2026-09-04 手塚SFの世界型)。漫画作品名を含む題は _SCOPE_OUT を素通りするので
#   題でなく **caption の語彙** で見る。①コミックレーベル(seriesName)が無い ②評論の語がある
#   ③caption が自分を漫画だと名乗っていない、の3条件AND。
#   ★③が要る: ②だけだと「グルメコミックエッセイ」「夕暮宇宙船短編集(あとがき/解説付き)」など
#   本物の漫画まで拾う(2026-09-04 実測で2件誤検出→③を足して0件に)。
#   実測: 楽天予約2,823件中3件のみ発火(手塚SF評論/地球の歩き方Dr.STONE/手塚マンガで憲法九条を読む)= 全て真陽性。
#   ★deny でなく hold(人が裁定)にする [[never_delete_because_broken]]。
_CRITICISM_CAPTION = re.compile(
    r"読み解く|読み解き|論じ|考察|評論|研究書|入門の決定版|にせまる一冊|に迫る一冊|作品解説|評伝|の全貌に迫")
_SELF_DECLARED_MANGA = re.compile(r"コミック|漫画|マンガ|まんが|画・|作画")


def looks_like_criticism(rec):
    """★評論/研究書の疑い(=hold にして人が裁く)。deny はしない。
    rec = 楽天harvestの1レコード。実例: 『アトム』と『火の鳥』手塚SFの世界(鳥影社・レーベル無し・
    caption に「読み解く」「作品解説を超えた」)。本番66k頁で鳥影社の漫画は0件だった。"""
    if str(rec.get("seriesName") or "").strip():
        return False                      # コミックレーベルが付いている=漫画側として扱う
    cap = str(rec.get("caption") or rec.get("itemCaption") or "")
    if not cap or not _CRITICISM_CAPTION.search(cap):
        return False
    return not _SELF_DECLARED_MANGA.search(cap)   # 自分を漫画だと名乗る紹介文は除外


def clean_title(title):
    """→ (base, subtitle, provisional). provisional=True なら (仮)=hold対象。"""
    t = unicodedata.normalize("NFKC", str(title or "")).strip()
    prov = bool(_PROV.search(t))
    t = _PROV.sub("", t).strip()
    sub = None
    # ★末尾の [巻番号 / @COMIC / 〜副題〜] を順不同で安定するまでループ除去(@COMIC後に(N)型に対応)
    for _ in range(5):
        t0 = t
        m = _SUB.search(t)
        if m:
            sub = m.group().strip(" 　〜～-")
            t = t[:m.start()].strip()
        t = _VOL_TAIL.sub("", t).strip()      # 末尾巻番号 (N)/第N巻/裸N
        t = _ATCOMIC.sub("", t).strip()       # @COMIC
        # ★題中の巻数+副題型(2026-07-14 アメと傷2型): 「base N 副題文」→ base+副題に分離
        #   (巻数は捨てる=巻番号はISBN側が正。baseが数字で終わる題(20世紀少年等)は対象外)
        m2 = re.match(r"^(.{2,}?)[\s　]*[（(]?(\d{1,2})[)）]?[\s　]+(.{4,})$", t)
        if m2 and sub is None and not re.search(r"\d$", m2.group(1).strip()):
            t = m2.group(1).strip()
            sub = m2.group(3).strip()
        if t == t0:
            break
    t = re.sub(r"[\s　]+$", "", t)
    return t, sub, prov


def _hira2kata(s):
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)


_ATCOMIC_KANA = re.compile(r"(?:アット|ザ)コミック\s*$")  # ★ザコミック=THE COMICの読み尾(2026-07-15)
_VOL_KANA = re.compile(r"(?:ダイ)?[イチニサンヨンゴロクナナハチキュウジュウゼロ第]+カン\s*$")


def _to_kata_reading(text):
    """漢字/かな混じり→カタカナ読み(pykakasi)。副題読みの差し引き用。"""
    if not text or not _KKS:
        return ""
    r = "".join(p["hira"] for p in _KKS.convert(str(text)))
    r = _hira2kata(r)
    return re.sub(r"[^ァ-ヶー]", "", r)


_KANA_NUM_TAIL = re.compile(
    r"^(イチ|ニ|サン|ヨン|ゴ|ロク|ナナ|ハチ|キュウ|ジュウ(イチ|ニ|サン|ヨン|ゴ|ロク|ナナ|ハチ|キュウ)?|"
    r"ジョウ|ゲ|チュウ|(ザ)?コミック(イチ|ニ|サン|ヨン|ゴ)?)$")

_slug_device = None
def _device():
    global _slug_device
    if _slug_device is None:
        try:
            from _slug_kana_lib import make_slug as _impl
            _slug_device = _impl
        except Exception:
            _slug_device = False
    return _slug_device or None


_DIGIT_READ = {"0": "zero", "1": "ichi", "2": "ni", "3": "san", "4": "yon", "5": "go",
               "6": "roku", "7": "nana", "8": "hachi", "9": "kyuu", "10": "juu"}


def _letters(s):
    """比較用正規化(等値判定専用): 記号除去+小文字。数字→音読み展開(slug数字keep vs ヨミのイチニ差吸収)。
    助詞ゆらぎ(は=wa/ha・を=o/wo・へ=e/he)は両辺同写像で潰す(比較にのみ使い表示には使わない)。"""
    t = re.sub(r"[^a-z0-9]", "", str(s or "").lower())
    t = re.sub(r"10|\d", lambda m: _DIGIT_READ.get(m.group(), m.group()), t)
    return t.replace("wo", "o").replace("ha", "wa").replace("he", "e")


def kana_tail_trim(base, kana):
    """★2026-07-14(1,029ドラフト裁定の学び): 楽天titleKanaは巻タイトル由来のため
    末尾に裸の巻数読み(アカルイミライ「ニ」型)が乗ることがある。
    基底題の装置読みに一致する接頭辞+残尾が数読み → 接頭辞に自動トリム。該当なしはそのまま返す。"""
    dev = _device()
    if not (dev and base and kana):
        return kana
    try:
        tgt = _letters(dev(base))
    except Exception:
        return kana
    # ★第2の照合先(2026-09-04 Code;OSINT型): 題にラテンが混じると装置読みが一致せずトリムが
    #   不発になる。題からカタカナだけを抜いた文字列との**完全一致**なら安全にトリムできる
    #   (推測でなく題に実在するカタカナとの一致なので捏造にならない)。
    tgt_kata = re.sub(r"[^ァ-ヶー]", "", unicodedata.normalize("NFKC", str(base)))
    if len(tgt_kata) < 3:
        tgt_kata = None
    if not tgt or _letters(dev(kana)) == tgt:
        return kana
    for i in range(len(kana) - 1, max(2, len(kana) // 2) - 1, -1):
        tail = kana[i:]
        if not _KANA_NUM_TAIL.match(tail):
            continue
        if tgt_kata and kana[:i] == tgt_kata:
            return kana[:i]
        try:
            if _letters(dev(kana[:i])) == tgt:
                return kana[:i]
        except Exception:
            return kana
    return kana


def _kana_dict_reading(base, kana):
    """★辞書英語化の差でヨミ一致ゲートが誤flagしないための第2読み(2026-09-04 #介護ロボット型)。
    janome はヨミ側の長いカタカナ連を1語(未知語)として扱うため katakana-english.yml の変換が効かず、
    題側だけ英語綴り(robot)・ヨミ側はカナ転写(robotto)になって「不一致」に見える。
    ★題に**実在する**辞書見出し語だけをヨミ側にも空白で切り出し、同じ装置に通して比べる
    (推測で語を足さない=捏造にならない)。該当語が無ければ None。"""
    try:
        from _slug_kana_lib import KEYS as _KEYS, make_slug as _dev
    except Exception:
        return None
    b, k = str(base or ""), str(kana or "")
    keys = [x for x in _KEYS if x and len(x) >= 2 and x in b]   # 題に実在する見出し語だけ
    if not keys:
        return None
    # ★左から最長一致で1回だけ走査する(2026-09-04)。単純な replace の繰り返しだと
    #   部分一致キーが既に切った語の内側をさらに割る(シャーロック→シャー+ロック / ホームズ→ホーム+ズ)。
    out, i = [], 0
    while i < len(k):
        for x in keys:                   # _KEYS は長い順
            if k.startswith(x, i):
                out.append(" " + x + " ")
                i += len(x)
                break
        else:
            out.append(k[i])
            i += 1
    seg = re.sub(r"[\s　]+", " ", "".join(out)).strip()
    if seg == k:
        return None
    try:
        return _dev(seg)
    except Exception:
        return None


def slug_kana_gate(base, kana, slug, out_tsv="docs/production-diagnostics/slug-gate-pending.tsv"):
    """★ヨミ一致ゲート(2026-07-14): 装置が題から読んだ綴りとヨミから読んだ綴りが不一致
    (剣聖→ken-hijiri型の漢字誤読リスク)なら pending tsv に1行残す(fail-open=生成は止めない)。
    戻り値 True=一致/False=flag済み。"""
    dev = _device()
    if not (dev and base and kana and slug):
        return True
    try:
        if _letters(slug) == _letters(dev(kana)):
            return True
        # ★辞書英語化の差は誤flagにしない(2026-09-04): 題に在る辞書語でヨミを切って比べ直す
        _alt = _kana_dict_reading(base, kana)
        if _alt and _letters(slug) == _letters(_alt):
            return True
    except Exception:
        return True
    try:
        import os
        os.makedirs(os.path.dirname(out_tsv), exist_ok=True)
        # ★追記dedup(2026-09-05): 同じ頁を何度検査しても行が積み上がり、簿が膨らんで
        #   誰も読まなくなっていた(実測 346行中143行が重複)。既存と同じ行は書かない。
        _row = f"{slug}\t{base}\t{kana}"
        if os.path.exists(out_tsv):
            with open(out_tsv, encoding="utf-8") as _f:
                if any(ln.rstrip("\r\n") == _row for ln in _f):
                    return False
        with open(out_tsv, "a", encoding="utf-8") as f:
            f.write(_row + "\n")
    except Exception:
        pass
    return False


def clean_kana(kana, subtitle=None, base=None):
    """楽天titleKana→カタカナのみ基底読み。漢字残る/空/汚染=None(hold=捏造回避)。
    ★楽天kanaの空白=語境界(副題境界でない)なので空白は除去して連結。
    ★副題は「副題読み(pykakasi)を末尾から差し引く」で除去(空白前取りは誤り=リターンズ事故)。
    末尾@COMIC読み(アットコミック)/巻読み(ダイN/Nカン)/(N)/裸数字も除去。
    ★base付きで呼ぶと裸の巻数読み尾(アカルイミライニ型)も装置照合で自動トリム(2026-07-14)。"""
    if not kana:
        return None
    k = unicodedata.normalize("NFKC", str(kana)).strip()
    k = _hira2kata(k)
    # ★カナに挟まれた波ダッシュ=長音符の装飾表記(と〜ふのあわこ→ト〜フノアワコ 2026-09-04)。
    #   ヨミ欄でカナとカナの間に来る〜/～は長音以外に意味を持てないので「ー」へ正規化する。
    #   (カナ以外に挟まれた〜は範囲記号のことがあるので触らない)
    k = re.sub(r"(?<=[ァ-ヶー])[〜～](?=[ァ-ヶー])", "ー", k)
    k = re.sub(r"[\s　（）()・:：!！?？、。,\.]+", "", k)   # 空白=語境界→除去・記号除去
    # 末尾の @COMIC読み/巻読み/裸数字 をループ除去
    for _ in range(4):
        k2 = _ATCOMIC_KANA.sub("", k)
        k2 = _VOL_KANA.sub("", k2)
        k2 = re.sub(r"\d+$", "", k2)
        if k2 == k:
            break
        k = k2
    # ★副題の読みを末尾から差し引く(pykakasi読みでfuzzy suffix)
    if subtitle:
        sr = _to_kata_reading(subtitle)
        if sr and len(sr) >= 3 and k.endswith(sr):
            k = k[:-len(sr)]
        elif sr and len(sr) >= 5 and sr[:len(sr) * 3 // 4] in k:  # 部分一致(読みズレ許容)
            k = k[:k.index(sr[:len(sr) * 3 // 4])]
    for _ in range(3):
        k2 = _VOL_KANA.sub("", _ATCOMIC_KANA.sub("", k))
        k2 = re.sub(r"\d+$", "", k2)
        if k2 == k:
            break
        k = k2
    if re.search(r"[一-鿿]", k):                # 漢字残り=楽天ヨミ無し→hold
        return None
    if "アットコミック" in k:                     # 差し引けなかった@COMIC=汚染→hold
        return None
    # ★安全網(捏造回避): 副題読みの差し引きは pykakasi 読みズレで失敗しうる。
    #   基底題ヨミは通常32字以下。超過=副題連結が残った疑い→hold(NDL照合キューへ)。
    #   ★長題誤holdの是正(2026-07-10 不貞の子=基底40字なろう系): 基底題の機械読み長と
    #     整合する(比0.6〜1.5)なら本物の長題として通す(副題汚染なら読み長より大きく膨らむ)。
    if len(k) > 32:
        br = _to_kata_reading(base) if base else None
        if not (br and 0.6 <= len(k) / max(1, len(br)) <= 1.5):
            return None
    if not re.search(r"[ァ-ヶー]", k) and not re.search(r"[A-Za-z0-9]", k):
        return None
    if base:
        k = kana_tail_trim(base, k)   # ★裸巻数読み尾の自動トリム(2026-07-14)
    return k or None


# カタカナ英単語→英語綴り(明白なもののみ・slug用)。グレーはヘボン。
_KATA_EN = {
    "ストレイ": "stray", "ラブ": "love", "ワン": "one", "スター": "star",
    "バス": "bus", "ドラゴン": "dragon", "ナイト": "night", "クイーン": "queen",
    "キング": "king", "ワールド": "world", "ゲーム": "game", "スクール": "school",
}


def _romaji_word(w):
    """カタカナ語1つ→ローマ字。明白英単語は英語綴り。"""
    if re.fullmatch(r"[A-Za-z0-9]+", w):
        return w.lower()
    if w in _KATA_EN:
        return _KATA_EN[w]
    if _KKS:
        return "".join(p["hepburn"] for p in _KKS.convert(w))
    return ""


def real_cover_and_date(isbn, covers_dict=None, live_fn=None, env=None, need_date=False):
    """書影+salesDate(ISO)を同一API応答から取る(★1API全フィールド捕捉。2026-07-11:
    回収先行巻の発売日が種2未収載の時、cover照会と同じ応答のsalesDateを捨てていた穴を封鎖)。
    ★書影は構築禁止(2026-07-09): cabinetパス/サフィックス/拡張子はISBNから推測不可=実URLのみ。"""
    if not isbn:
        return None, None
    cov = None
    if covers_dict:
        u = covers_dict.get(isbn)
        if u and "noimage" not in u:
            cov = u
    date = None
    if (cov is None or need_date) and live_fn and env:
        try:
            items = live_fn(env, isbn=isbn) or []
            if items:
                it = items[0]
                if cov is None:
                    img = str(it.get("largeImageUrl") or it.get("mediumImageUrl") or "")
                    if img and "noimage" not in img:
                        cov = img
                m = re.search(r"(\d{4})年(\d{1,2})月(?:(\d{1,2})日)?", str(it.get("salesDate") or ""))
                if m:
                    date = f"{m.group(1)}-{int(m.group(2)):02d}" + (f"-{int(m.group(3)):02d}" if m.group(3) else "")
        except Exception:
            pass
    return cov, date


def real_cover(isbn, covers_dict=None, live_fn=None, env=None):
    """後方互換wrapper。新規コードは real_cover_and_date を使う。"""
    return real_cover_and_date(isbn, covers_dict, live_fn, env)[0]


def kata_pending_log(base, slug, frags, out_tsv="docs/production-diagnostics/slug-katakana-pending.tsv"):
    """★カタカナ語ヘボンfallbackの簿記(2026-07-14 ユーザ要望=自動で決められない箇所を言ってくれ):
    katakana-english.yml に掛からずカナ転写した断片を保留簿へ(既存行はskip=追記dedup)。fail-open。"""
    try:
        import os
        os.makedirs(os.path.dirname(out_tsv), exist_ok=True)
        seen = set()
        if os.path.exists(out_tsv):
            with open(out_tsv, encoding="utf-8") as f:
                seen = {ln.split("\t")[0] + "\t" + ln.split("\t")[1] for ln in f if ln.count("\t") >= 2}
        with open(out_tsv, "a", encoding="utf-8") as f:
            for fr in frags:
                key = f"{fr}\t{base}"
                if key in seen:
                    continue
                f.write(f"{fr}\t{base}\t{slug or ''}\n")
                seen.add(key)
    except Exception:
        pass


def make_slug(base, kana_raw=None, existing=None):
    """slug生成。★正規装置 _slug_kana_lib(janome分かち+katakana-english.yml貪欲辞書変換+ヘボン)に委譲
    (2026-07-09 ユーザ指摘=英語綴り辞書を使え)。clean base題(副題/巻/@COMIC除去済)を渡す。
    英語綴り(summer-blend/duel-masters/beauty-pop)・助詞は→wa/を→o・長音保持。空/短すぎ/衝突=None(hold)。"""
    try:
        from _slug_kana_lib import make_slug as _slug_impl, FALLBACK
        slug = _slug_impl(base)
        # ★辞書に掛からなかったカタカナ語=自動で決められない箇所を保留簿へ(fail-open。ユーザ報告用 2026-07-14)
        if FALLBACK:
            kata_pending_log(base, slug, FALLBACK)
    except Exception:
        # fallback: pykakasi(辞書無し)。装置が使えない時のみ
        slug = ""
        if _KKS:
            parts = []
            for p in _KKS.convert(base):
                orig = p["orig"].strip()
                h = p["hepburn"].strip()
                parts.append(orig.lower() if re.fullmatch(r"[A-Za-z0-9]+", orig) else h)
            slug = re.sub(r"-+", "-", "-".join(x for x in parts if x).lower()).strip("-")
    slug = re.sub(r"[^a-z0-9-]+", "-", str(slug).lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    slug = re.sub(r"(?<=[a-z])-?\d{1,3}$", "", slug).strip("-")  # 末尾巻番号(stray5→stray)。rx等英字suffixは保持
    if len(slug) < 2:
        return None                             # ゴミslug(2026化)禁止=hold
    # ★無ハイフン連結ガード(2026-07-27 ユーザ発見=princeofghost): 題に語境界(空白/全角空白/
    #   中黒/&/×)があるのに slug が10字以上ハイフン0本 = 装置バグか題の異常。生成せずhold
    #   (旧装置期に全角スペース題が連結された型の再発防止)。
    #   ★2026-08-09 拡張(ココロメイクコスメティカ型): 題に見える区切りが無くても、**長いカタカナ連**は
    #   語境界が在るのに janome が1語(未知語)扱いして丸ごと連結する。辞書に載っていない長カタカナ題は
    #   自動で決められない ⇒ 生成せず hold して人に回す(偽hold > 偽採用)。短い一語(ツノカクシ等)は通す。
    _kata_run = max((len(m) for m in re.findall(r"[ァ-ヶー]+", str(base))), default=0)
    if len(slug) >= 10 and "-" not in slug and (re.search(r"[\s　・&×]", str(base)) or _kata_run >= 8):
        return None
    # ★長題は語境界で切る(2026-07-20: 機械70字cutが語中切断「tsukaretemashit」型を44件量産した対策)。
    #   切った後の尻に残る助詞トークンも剥がす(「-sekai-o」型)。完全slugは触らない。
    if len(slug) > 70:
        cut = slug[:70]
        if "-" in cut[1:]:
            cut = cut[:cut.rfind("-")]
        _PART = r"-(?:no|o|wa|ni|de|to|ga|e|mo|kara|made|niwa|noni|node|yori|toka|kedo)$"
        while re.search(_PART, cut):
            cut = re.sub(_PART, "", cut)
        slug = cut.rstrip("-")
        if len(slug) < 2:
            return None
    # ★ヨミ基点への自動是正(2026-08-08 新設。それまでは「誤読をflagするだけ」で直していなかった)
    #   根因= slug を **漢字題から**作っていた。確定ヨミ(楽天titleKana)を持っているのに、
    #   それは事後照合に使うだけで生成には渡していなかったため、装置の漢字誤読がそのまま出た。
    #   実害(2026-08-08 日次蒸留・28件をユーザ指摘後に手で直した):
    #     堕天使ちゃん→chan-(堕天使が丸ごと欠落) / 魔導士→ma-shirubeshi / 聖巡→kiyoshijun /
    #     包丁人味平→houchoujinmi-taira / 日の名残り→nichi- / 酔拳→yoiken / 転生剣豪→tensei-(テンショウが正)
    #   ★方針= 題基点を第一候補のまま残し(ラテン混じり題「BanG Dream!」等の綴りを活かすため)、
    #     **ゲートが不一致を出した時だけヨミ基点で作り直す**。ヨミは純カタカナで捏造ゲート済みなので
    #     誤読が構造的に起きない。作り直しても不一致なら従来どおり pending 簿に残す(fail-open)。
    if kana_raw:
        _k = _hira2kata(re.sub(r"[\s　]+", "", str(kana_raw)))
        if not slug_kana_gate(base, _k, slug):
            _fix = None
            try:
                from _slug_kana_lib import make_slug as _slug_impl2
                # ★カタカナ列は janome が1語(未知語)として扱い語境界が消える=slugが全部連結になる。
                #   題側に**ひらがなの助詞**が見えているので、その並び順でヨミを割って境界を復元する
                #   (ヒノナゴリ→ヒ ノ ナゴリ / ダテンシチャンハガンバレナイ→ダテンシチャン ハ ガンバレナイ)。
                #   左から順にマッチさせるので、ヨミ中に同じカナが複数あっても題の出現順に従う。
                _P = {"の": "ノ", "は": "ハ", "を": "ヲ", "に": "ニ", "と": "ト",
                      "で": "デ", "が": "ガ", "も": "モ", "へ": "ヘ"}
                _seq = [_P[c] for c in str(base) if c in _P]
                _seg, _rest = [], _k
                for _p in _seq:
                    _i = _rest.find(_p, 1)          # 先頭の1文字目は助詞にしない
                    if _i <= 0:
                        continue
                    _seg.append(_rest[:_i]); _seg.append(_p); _rest = _rest[_i + 1:]
                _seg.append(_rest)
                _src = " ".join(x for x in _seg if x) if len(_seg) > 1 else _k
                _fix = _slug_impl2(_src)
            except Exception:
                _fix = None
            if _fix:
                _fix = re.sub(r"[^a-z0-9-]+", "-", str(_fix).lower()).strip("-")
                _fix = re.sub(r"-+", "-", _fix)
                _fix = re.sub(r"(?<=[a-z])-?\d{1,3}$", "", _fix).strip("-")
                # ★助詞のヘボン標準化(CLAUDE.md slug規則2): は=wa / を=o / へ=e。
                #   ヨミ経由だと ハ→ha, ヲ→wo になるので綴りを揃える。
                _fix = re.sub(r"(^|-)ha(-|$)", r"\1wa\2", _fix)
                _fix = re.sub(r"(^|-)wo(-|$)", r"\1o\2", _fix)
                _fix = re.sub(r"(^|-)he(-|$)", r"\1e\2", _fix)
                # ★自動採用は「題にラテン文字が無い」時だけ(2026-08-08)。
                #   ラテン混じり題はヨミ経由で綴りが劣化する(「THE COMIC」→ザコミック→zakomikku /
                #   「BanG Dream!」→バンドリ…)。その場合は題基点を残し、候補は下の簿に併記して人が裁く。
                _has_latin = bool(re.search(r"[A-Za-z]", str(base)))
                # ★2026-08-24 根治(ユーザ発見SLUG_MUSH30件): _fix側にも題側と同じ長さガードを通す
                #   (それまでヨミ再構成slugは70字カット・語境界検査を素通りして80字塊が出荷されていた)。
                if len(_fix) > 70:
                    _cut = _fix[:70]
                    if "-" in _cut[1:]:
                        _cut = _cut[:_cut.rfind("-")]
                    _fix = _cut.rstrip("-")
                if len(_fix) >= 2 and not _has_latin and (existing is None or _fix not in existing):
                    slug = _fix
                elif _fix != slug:
                    # 採用しない場合も**候補を簿に残す**=次に人が直す時の答えを添える
                    try:
                        import os as _os
                        _tsv = "docs/production-diagnostics/slug-kana-candidate.tsv"
                        _os.makedirs(_os.path.dirname(_tsv), exist_ok=True)
                        with open(_tsv, "a", encoding="utf-8") as _f:
                            _f.write(f"{slug}\t{_fix}\t{base}\t{_k}\n")
                    except Exception:
                        pass
    # ★無分割塊ガード最終形(2026-08-24 SLUG_MUSH根治): 全体無ハイフンだけでなく、
    #   **ハイフン無しrunが15字以上**なら語境界消失(janome未知語連結)=自動で決められない→hold。
    #   (isekairakurakumujintouraifu…型=先頭33字塊が後半のハイフンで旧ガードをすり抜けた)
    if max((len(x) for x in slug.split("-")), default=0) >= 15:
        return None
    if existing is not None and slug in existing:
        return None                             # 衝突=hold(-2026で誤魔化さない)
    return slug
