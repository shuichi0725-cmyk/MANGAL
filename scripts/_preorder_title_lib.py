# -*- coding: utf-8 -*-
"""予約タイトル分離器 (= 2026-07-06 ユーザ裁定「タイトル/巻数/副題の分離器がいる」)

楽天の生タイトルを {base(題), vol(巻数|None), subtitle(副題), clean(表示題=base+副題)} に分解する。
巻数の出現位置パターン(実測で全部踏んだ):
  A. 末尾: 「題 (N)」「題 第N巻」「題 N」
  B. 中間: 「題(N) 〜副題〜」「題 N 〜副題〜」   ← 三ツ星レシピ型/魔王のアトリエ型
  C. かな数詞: 「題 その六」(題側は途切れも)      ← 悪役令嬢99型(ヨミ照合で検出)
  D. 上下巻: 「題 上/下」「題(上)」             ← vol=1/2相当(ペア統合は呼び出し側)
検出しないもの: 題の一部の数字(レベル99/U149/After20=直前が英数字)。
★2026-09-02 追加(日次蒸留で続巻が skip に落ちた型):
  A2. 閉じ記号直後の裸数字「〜副題〜9」「』3」= 巻数(確定)。副題の閉じの後に数字だけが続くのは巻数しかない。
  A3. 英字語+空白+裸数字「GOLD RUSH　8」「S-WITCH　2」= suspect(vol_suspect)。題の一部(Area 88型)かもしれないので
      確定せず、分類器が suspect>=2 を巻扱いにして頁一致(著者+題)/全巻回収で確定する既存の安全網に乗せる。
"""
import re
import unicodedata

_KANJI_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_SUB_OPEN = r"[〜~\-−ー―《〈「『]"

def _kanji_int(g):
    """漢数字(一〜九十九)→int。読めなければ None。巻表示の解釈だけに使う。"""
    g = str(g or "")
    if not g or any(c not in _KANJI_NUM for c in g):
        return None
    if "十" not in g:
        return _KANJI_NUM.get(g) if len(g) == 1 else None
    i = g.index("十")
    tens = _KANJI_NUM[g[i - 1]] if i > 0 else 1
    ones = _KANJI_NUM[g[i + 1]] if i + 1 < len(g) else 0
    if i > 1 or len(g) - i > 2:
        return None
    n = tens * 10 + ones
    return n if 1 <= n <= 99 else None


# ★B0m の巻表記(2026-09-24 当世幻想博物誌（巻ノ1）型): 巻ノN/巻之N/其ノN(漢数字可)・(第N集)/(N集)/第N集・
#   (v.N)・(N(副題))。どれも既存規則に当たらず vol=None → 既刊作品の続巻が**新作1巻として別頁化**されうる。
#   充填・照合側(_rakuten_match_lib.parse_vol)は同日に是正済み = ここは取り込み側の対。
_KN = r"\d{1,3}|[一二三四五六七八九十]{1,4}"
_B0M = (
    re.compile(r"^(.*?)[\s　]*[（(]?\s*[巻其][ノの之]\s*(" + _KN + r")\s*(?:[（(](?P<sub>[^()（）]*)[)）])?\s*[)）]?[\s　]*$"),
    re.compile(r"^(.*?)[\s　]*[（(]\s*第?\s*(\d{1,3})\s*集\s*(?:[（(](?P<sub>[^()（）]*)[)）])?\s*[)）]?[\s　]*$"),
    re.compile(r"^(.*?)[\s　]+第\s*(" + _KN + r")\s*集[\s　]*$"),
    re.compile(r"^(.*?)[\s　]*[（(]\s*[vV]\.\s*(\d{1,3})\s*[)）][\s　]*$"),
    re.compile(r"^(.*?)[\s　]*[（(]\s*第?\s*(\d{1,3})\s*巻?\s*[（(](?P<sub>[^()（）]*)[)）]\s*[)）][\s　]*$"),
)

_ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def _roman_int(t):
    """ローマ数字→int。不正な並びは None(=巻数として採らない)。"""
    t = str(t or "").upper()
    if not t or any(c not in _ROMAN for c in t):
        return None
    n, prev = 0, 0
    for c in reversed(t):
        v = _ROMAN[c]
        n = n - v if v < prev else n + v
        prev = max(prev, v)
    return n or None


def _nfkc(t):
    return unicodedata.normalize("NFKC", str(t or "")).strip()

def split_title(raw):
    """→ dict(base, vol, part, subtitle, clean, matched)
    vol: int|None / part: '上'|'中'|'下'|None / clean: 巻数表記を除いた表示題"""
    t = _nfkc(raw)
    base, vol, part, sub = t, None, None, ""
    matched = None

    # D. 上下巻(末尾)
    m = re.search(r"^(.*?)[\s　]*[（(]?([上中下])[)）]?(?:巻)?[\s　]*(?:[（(]完[)）])?$", t)
    if m and m.group(1).strip() and len(m.group(1)) >= 3 and re.search(r"[\s　（(]$", t[:m.end(1) + 1] + " "):
        # 「〜屋上」等の誤爆防止: 上下の直前が空白/括弧のときだけ
        pre = t[: len(m.group(1))]
        if re.search(r"[\s　]$", t[: t.rfind(m.group(2))]) or re.search(r"[（(]" + m.group(2), t):
            base, part = m.group(1).strip(), m.group(2)
            matched = "jouge"
            return {"base": base, "vol": {"上": 1, "中": 2, "下": None}.get(part), "part": part,
                    "subtitle": "", "clean": base, "matched": matched}

    # B0. 括弧+巻語: 題(1巻)/(全1巻) (2026-07-07 ユーザ発見)。全N巻=完結情報(zen=True)
    m = re.search(r"^(.*?)[\s　]*[（(]\s*(全\s*)?(\d{1,3})\s*巻\s*[)）][\s　]*(.*)$", t)
    if m and m.group(1).strip():
        base = m.group(1).strip(); vol = int(m.group(3)); sub = (m.group(4) or "").strip()
        clean = (base + ("　" + sub if sub else "")).strip()
        return {"base": base, "vol": vol, "part": None, "subtitle": sub, "clean": clean,
                "matched": "paren_kan", "vol_suspect": None, "zen": bool(m.group(2))}
    # B0k. ★漢数字の巻表示(2026-09-04 寿司銀捕物帖（三巻）型): 題(一巻)/(第三巻)/第三巻/(全五巻)。
    #   B0 は算用数字しか見ておらず、C' は空白区切りの裸漢数字だけだったので、この形は
    #   どの規則にも当たらず vol=None → **3巻の本が新作1巻として登録されかける**事故になった。
    m = re.search(r"^(.*?)[\s　]*(?:[（(]\s*)?(全\s*)?第?\s*([一二三四五六七八九十]{1,4})\s*巻\s*(?:[)）])?[\s　]*$", t)
    if m and m.group(1).strip() and _kanji_int(m.group(3)):
        base = m.group(1).strip()
        return {"base": base, "vol": _kanji_int(m.group(3)), "part": None, "subtitle": "",
                "clean": base, "matched": "kanji_kan", "vol_suspect": None, "zen": bool(m.group(2))}

    # B0m. ★巻ノN/巻之N/其ノN・第N集/(N集)・(v.N)・(N(副題))(上の _B0M の注記)。
    for _rx in _B0M:
        m = _rx.search(t)
        if m and m.group(1).strip():
            n = m.group(2)
            v = int(n) if n.isdigit() else _kanji_int(n)
            if v and 1 <= v <= 999:
                base = m.group(1).strip()
                sub = (m.groupdict().get("sub") or "").strip()
                clean = (base + ("　" + sub if sub else "")).strip()
                return {"base": base, "vol": v, "part": None, "subtitle": sub, "clean": clean,
                        "matched": "marker_ext", "vol_suspect": None}
    # B0r. ★括弧付きローマ数字の巻表示 (= 2026-09-14 部長の夜テク…(Ⅻ) 型)。
    #   全角合字 Ⅻ/Ⅺ は NFKC で "XII"/"XI" のラテン文字になるため、数字を要求する B0/B/A0 の
    #   どれにも当たらず vol=None → **12巻の本が新作1巻としてドラフト化**されかけた(既存頁は1-11巻在り)。
    #   ★1文字(I/V/X/L/C)は題の装飾のことがあるので確定せず suspect に落とす。
    m = re.search(r"^(.*?)[\s　]*[（(]\s*((?=[IVXLC]{1,6}\s*[)）])M{0,3}(?:CM|CD|D?C{0,3})"
                  r"(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3}))\s*[)）][\s　]*$", t)
    if m and m.group(1).strip() and m.group(2):
        n = _roman_int(m.group(2))
        if n and 1 <= n <= 99:
            base = m.group(1).strip()
            if len(m.group(2)) >= 2:
                return {"base": base, "vol": n, "part": None, "subtitle": "", "clean": base,
                        "matched": "paren_roman", "vol_suspect": None}
            return {"base": base, "vol": None, "part": None, "subtitle": "", "clean": t,
                    "matched": None, "vol_suspect": n}

    # B. 中間括弧: 題(N) 副題
    m = re.match(r"^(.{3,}?)[\s　]*[（(]\s*(\d{1,3})\s*[)）][\s　]*(\S.*)$", t)
    if m:
        base, vol, sub = m.group(1).strip(), int(m.group(2)), m.group(3).strip()
        sub = re.sub(r"^[（(]完[)）][\s　]*", "", sub)
        matched = "mid_paren"
    else:
        # B''. 直結数字+副題(アメと傷2 副題 型 2026-07-06): suspect(題の一部数字かもなので確定しない。
        #   呼び出し側が「同base他巻の存在(楽天/キャッシュ/既存頁)」で確定する=ユーザ提案の題名調査)
        m = re.match(r"^(.{2,}?[ぁ-ん一-龯ァ-ヶー])([2-9]|[1-9][0-9])[\s　](\S.*)$", t)
        if m:
            return {"base": m.group(1).strip(), "vol": None, "part": None, "subtitle": m.group(3).strip(),
                    "clean": t, "matched": None, "vol_suspect": int(m.group(2))}
        # B'. 中間裸数字(前後空白): 題 N 副題
        m = re.match(r"^(.{3,}?[^A-Za-z0-9])[\s　](\d{1,3})[\s　](\S.*)$", t)
        if m and not re.match(r"^[0-9]", m.group(3)):
            base, vol, sub = m.group(1).strip(), int(m.group(2)), m.group(3).strip()
            matched = "mid_bare"
        else:
            # A0. 末尾 括弧付き(N)/第N巻/N巻 = 英字末尾でも常に巻数(RX(1)/Returns(1)型 2026-07-07)。
            m = re.search(r"^(.*?)(?:[\s　]*[（(]\s*(\d{1,3})\s*[)）]|[\s　]*第\s*(\d{1,3})\s*巻|[\s　]*(\d{1,3})\s*巻)[\s　]*(?:[（(]完[)）])?$", t)
            if m and m.group(1).strip():
                n = next((g for g in m.groups()[1:] if g and g.strip().isdigit()), None)
                if n is not None:
                    base, vol = m.group(1).strip(), int(n)
                    matched = "tail"
            # A0v. ★「VOLUME N」/「VOL.N」末尾(痛覚探偵 通天寺ナツメ […] VOLUME 2 TWO 型 2026-09-14):
            #   VOLUME/VOL は巻を指す語なので確定。後ろに英単語の数詞(ONE/TWO/…)が続く表記も吸収する。
            #   ★これが無いと「VOLUME 2」の本が vol=None のまま新作1巻としてドラフト化される
            #   (=単巻先行登録の事故。実際 2026-09-14 に1巻既刊の作品が2巻で新規頁化されかけた)。
            if matched is None:
                m = re.search(r"^(.*?)[\s　]*(?:VOLUME|VOL\.?)[\s　]*(\d{1,3})"
                              r"(?:[\s　]+(?:ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|ELEVEN|TWELVE))?"
                              r"[\s　]*$", t, re.I)
                if m and m.group(1).strip():
                    base, vol = m.group(1).strip(), int(m.group(2))
                    matched = "tail_volume_word"
            # A0w. ★「NN.巻題」末尾(ワンス・アポン・ア・ディスティニー 01.These / 02.Antithese 型
            #   2026-09-19 ユーザ指摘): ゼロ詰め2桁 + ピリオド + 巻題、という分冊表記。
            #   これが読めないと同一作品の2巻が「別々の新作1巻」として2頁に割れる
            #   (実害= 屋号『ワンス・アポン・ア・ディスティニー』が同日発売なのに2頁になっていた)。
            #   ★ゼロ詰め(01/02…)を必須にする= 「1.5」「Vol.2」等の他形式や、題中の
            #   小数・章番号(『3.月の…』型)を巻と誤読しないため。巻題は subtitle へ逃がす。
            if matched is None:
                m = re.search(r"^(.{2,}?)[\s　]+(0\d|[1-9]\d)\.[\s　]*([A-Za-z][\w\-'’\. ]{1,40})[\s　]*$", t)
                if m and m.group(1).strip():
                    base, vol = m.group(1).strip(), int(m.group(2))
                    sub = m.group(2) + "." + m.group(3).strip()
                    matched = "tail_numdot_label"
            # A. 末尾 スペース区切り裸N (=英字末尾は題の一部かもなのでガード=レベル99保護)
            if matched is None:
                m = re.search(r"^(.*?)[\s　]+(\d{1,3})[\s　]*(?:[（(]完[)）])?$", t)
                if m and m.group(1).strip() and not re.search(r"[A-Za-z0-9]$", m.group(1).rstrip()):
                    base, vol = m.group(1).strip(), int(m.group(2))
                    matched = "tail"
            # A2. 閉じ記号直後の裸数字(〜副題〜9 / 』3 型 2026-09-02): 副題の閉じの後の数字は巻数しかない=確定
            if matched is None:
                m = re.search(r"^(.{3,}?[〜~」』】〉》])(\d{1,3})[\s　]*$", t)
                if m and m.group(1).strip():
                    base, vol = m.group(1).strip(), int(m.group(2))
                    matched = "tail_after_close"
            # A3. 英字語+空白+裸数字(GOLD RUSH 8 / S-WITCH 2 型 2026-09-02): 題の一部かも(Area 88)なので suspect
            if matched is None:
                m = re.search(r"^(.*?[A-Za-z])[\s　]+([2-9]|[1-9][0-9]{1,2})[\s　]*(?:[（(]完[)）])?$", t)
                if m and m.group(1).strip():
                    return {"base": m.group(1).strip(), "vol": None, "part": None, "subtitle": "",
                            "clean": t, "matched": None, "vol_suspect": int(m.group(2))}
            # A'. 直結裸数字(サンダー3=題の一部かも/鬼平犯科帳128=巻かも)→確定せずsuspect
            if matched is None:
                m = re.search(r"^(.{3,}?[ぁ-ん一-龯ァ-ヶ])(\d{1,3})[\s　]*$", t)
                if m:
                    return {"base": m.group(1).strip(), "vol": None, "part": None, "subtitle": "",
                            "clean": t, "matched": None, "vol_suspect": int(m.group(2))}
    # C'. 漢数字末尾(大江戸イノベーション 二/税務職員の美酒 弐 型 2026-07-06): スペース区切りのみ
    if matched is None:
        m = re.search(r"^(.{3,}?)[\s　]([一二三四五六七八九十]|[壱弐参])$", t)
        if m and m.group(1).strip():
            _KN2 = {"壱": 1, "弐": 2, "参": 3}
            g = m.group(2)
            base = m.group(1).strip()
            vol = _KANJI_NUM.get(g) or _KN2.get(g)
            matched = "kanji_tail"
    # C. かな数詞末尾: 題 その六
    if matched is None:
        m = re.search(r"^(.*?)[\s　]*その([一二三四五六七八九十]|\d{1,2})$", t)
        if m and m.group(1).strip():
            g = m.group(2)
            base = m.group(1).strip()
            vol = int(g) if g.isdigit() else _KANJI_NUM.get(g)
            matched = "sono"

    clean = (base + ("　" + sub if sub else "")).strip() if matched else t
    return {"base": base if matched else t, "vol": vol, "part": part,
            "subtitle": sub, "clean": clean, "matched": matched, "vol_suspect": None}


def strip_kana_vol(kana, vol):
    """ヨミ側の巻数トークン除去(スペース区切りの数字/数詞・ソノN)。分からなければそのまま。"""
    k = _nfkc(kana)
    k = re.sub(r"[\s　]*ソノ(?:イチ|ニ|サン|ヨン|ゴ|ロク|ナナ|ハチ|キュウ|ジュウ)[イチニサンヨンゴロクナナハチキュウジュウ]*[\s　]*", " ", k)
    k = re.sub(r"[\s　]+(?:\d{1,3}|イチ|ニ|サン|ヨン|ゴ|ロク|ナナ|ハチ|キュウ|ジュウ(?:イチ|ニ|サン|ヨン|ゴ|ロク|ナナ|ハチ|キュウ)?)(?=[\s　]|$)", " ", k)
    k = re.sub(r"[\s　]+(?:ジョウ|チュウ|ゲ)(?:カン)?$", "", k)
    # ★ヨミ欄にラテンの巻表示がそのまま入る型(痛覚探偵 …VOLUME2TWO 2026-09-14)。
    #   楽天は題のラテン部をヨミへ素通しするので、巻表示だけは剥がす(題側 _VOL_TAIL と対)。
    k = re.sub(r"[\s　]*(?:VOLUME|VOL\.?)[\s　]*\d{1,3}"
               r"(?:[\s　]*(?:ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN|ELEVEN|TWELVE))?[\s　]*$",
               "", k, flags=re.I)
    return re.sub(r"[\s　]{2,}", " ", k).strip()


COMIC_MARK = re.compile(r"[\s　]*(?:[（(]\s*コミック\s*[)）]|@\s*COMIC|THE COMIC|The Comic|[（(]\s*comic\s*[)）])[\s　]*", re.I)

def split_subtitle(title):
    """本題と副題の分離(2026-07-07 ユーザ裁定): (a)コミカライズ表記(@COMIC/THE COMIC/(コミック))は除去
    (b)末尾の『〜副題〜』はsubtitleへ(詳細頁は title+subtitle 2行表示が既存設計)。slugは本題のみから生成。
    → (title, subtitle|None)"""
    t = _nfkc(title)
    t = COMIC_MARK.sub(" ", t).strip()
    m = re.search(r"^(.{3,}?)[\s　]*[〜~]([^〜~]{3,})[〜~][\s　]*$", t)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return t, None
