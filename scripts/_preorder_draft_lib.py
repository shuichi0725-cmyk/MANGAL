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


_ATCOMIC_KANA = re.compile(r"アットコミック\s*$")
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
    if not tgt or _letters(dev(kana)) == tgt:
        return kana
    for i in range(len(kana) - 1, max(2, len(kana) // 2) - 1, -1):
        tail = kana[i:]
        if not _KANA_NUM_TAIL.match(tail):
            continue
        try:
            if _letters(dev(kana[:i])) == tgt:
                return kana[:i]
        except Exception:
            return kana
    return kana


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
    except Exception:
        return True
    try:
        import os
        os.makedirs(os.path.dirname(out_tsv), exist_ok=True)
        with open(out_tsv, "a", encoding="utf-8") as f:
            f.write(f"{slug}\t{base}\t{kana}\n")
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
    slug = slug[:70]
    if existing is not None and slug in existing:
        return None                             # 衝突=hold(-2026で誤魔化さない)
    if kana_raw:
        slug_kana_gate(base, _hira2kata(re.sub(r"[\s　]+", "", str(kana_raw))), slug)  # ★誤読flag(fail-open)
    return slug
