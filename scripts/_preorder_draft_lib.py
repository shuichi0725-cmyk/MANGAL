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

_VOL_TAIL = re.compile(r"(?:[（(]\s*\d{1,3}\s*[)）]|第\s*\d{1,3}\s*巻|[\s　]+\d{1,3}|(?<=[ぁ-んァ-ヶ一-鿿])\d{1,3})\s*$")
_SUB = re.compile(r"[\s　]*[〜～\-][^〜～]*?[〜～]\s*$")   # 〜副題〜 / ～副題～
_ATCOMIC = re.compile(r"[@＠]\s*comic\s*$", re.I)
_PROV = re.compile(r"[（(]\s*仮\s*[)）]")


_SCOPE_OUT = re.compile(r"めくり|カレンダー|ぬりえ|塗り絵|写真集|画集|イラスト集|ファンブック|設定資料|ガイドブック|公式ガイド|データブック|ビジュアルブック|原画集|ムック|フィギュア|カードゲーム|トレカ|グッズ|下敷き|ノート|手帳|(?:^|\s)artbook", re.I)


def scope_out(title):
    """漫画でない(カレンダー/画集/グッズ等)=Trueなら掲載対象外。"""
    return bool(_SCOPE_OUT.search(str(title or "")))


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
        if t == t0:
            break
    t = re.sub(r"[\s　]+$", "", t)
    return t, sub, prov


def _hira2kata(s):
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)


_ATCOMIC_KANA = re.compile(r"アットコミック\s*$")
_VOL_KANA = re.compile(r"(?:ダイ)?[イチニサンヨンゴロクナナハチキュウジュウゼロ第]+カン\s*$")


def _to_kata_reading(text):
    """漢字/かな混じり→カタカナ読み(pykakasi)。副題読みの差し引き用。"""
    if not text or not _KKS:
        return ""
    r = "".join(p["hira"] for p in _KKS.convert(str(text)))
    r = _hira2kata(r)
    return re.sub(r"[^ァ-ヶー]", "", r)


def clean_kana(kana, subtitle=None, base=None):
    """楽天titleKana→カタカナのみ基底読み。漢字残る/空/汚染=None(hold=捏造回避)。
    ★楽天kanaの空白=語境界(副題境界でない)なので空白は除去して連結。
    ★副題は「副題読み(pykakasi)を末尾から差し引く」で除去(空白前取りは誤り=リターンズ事故)。
    末尾@COMIC読み(アットコミック)/巻読み(ダイN/Nカン)/(N)/裸数字も除去。"""
    if not kana:
        return None
    k = unicodedata.normalize("NFKC", str(kana)).strip()
    k = _hira2kata(k)
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


def make_slug(base, kana_raw=None, existing=None):
    """slug生成。★正規装置 _slug_kana_lib(janome分かち+katakana-english.yml貪欲辞書変換+ヘボン)に委譲
    (2026-07-09 ユーザ指摘=英語綴り辞書を使え)。clean base題(副題/巻/@COMIC除去済)を渡す。
    英語綴り(summer-blend/duel-masters/beauty-pop)・助詞は→wa/を→o・長音保持。空/短すぎ/衝突=None(hold)。"""
    try:
        from _slug_kana_lib import make_slug as _slug_impl
        slug = _slug_impl(base)
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
    slug = slug[:70]
    if existing is not None and slug in existing:
        return None                             # 衝突=hold(-2026で誤魔化さない)
    return slug
