# -*- coding: utf-8 -*-
"""予約タイトル分離器 (= 2026-07-06 ユーザ裁定「タイトル/巻数/副題の分離器がいる」)

楽天の生タイトルを {base(題), vol(巻数|None), subtitle(副題), clean(表示題=base+副題)} に分解する。
巻数の出現位置パターン(実測で全部踏んだ):
  A. 末尾: 「題 (N)」「題 第N巻」「題 N」
  B. 中間: 「題(N) 〜副題〜」「題 N 〜副題〜」   ← 三ツ星レシピ型/魔王のアトリエ型
  C. かな数詞: 「題 その六」(題側は途切れも)      ← 悪役令嬢99型(ヨミ照合で検出)
  D. 上下巻: 「題 上/下」「題(上)」             ← vol=1/2相当(ペア統合は呼び出し側)
検出しないもの: 題の一部の数字(レベル99/U149/After20=直前が英数字)。
"""
import re
import unicodedata

_KANJI_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_SUB_OPEN = r"[〜~\-−ー―《〈「『]"

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

    # B. 中間括弧: 題(N) 副題
    m = re.match(r"^(.{3,}?)[\s　]*[（(]\s*(\d{1,3})\s*[)）][\s　]*(\S.*)$", t)
    if m:
        base, vol, sub = m.group(1).strip(), int(m.group(2)), m.group(3).strip()
        sub = re.sub(r"^[（(]完[)）][\s　]*", "", sub)
        matched = "mid_paren"
    else:
        # B'. 中間裸数字(前後空白): 題 N 副題
        m = re.match(r"^(.{3,}?[^A-Za-z0-9])[\s　](\d{1,3})[\s　](\S.*)$", t)
        if m and not re.match(r"^[0-9]", m.group(3)):
            base, vol, sub = m.group(1).strip(), int(m.group(2)), m.group(3).strip()
            matched = "mid_bare"
        else:
            # A. 末尾: (N) / 第N巻 / N巻 / スペース区切り裸N (=巻と確定できるもの)
            m = re.search(r"^(.*?)(?:[\s　]*[（(]\s*(\d{1,3})\s*[)）]|[\s　]*第\s*(\d{1,3})\s*巻|[\s　]*(\d{1,3})\s*巻|[\s　]+(\d{1,3}))[\s　]*(?:[（(]完[)）])?$", t)
            if m and m.group(1).strip():
                n = next((g for g in m.groups()[1:] if g and g.strip().isdigit()), None)
                if n is not None:
                    pre = m.group(1)
                    if not re.search(r"[A-Za-z0-9]$", pre.rstrip()):
                        base, vol = pre.strip(), int(n)
                        matched = "tail"
            # A'. 直結裸数字(サンダー3=題の一部かも/鬼平犯科帳128=巻かも)→確定せずsuspect
            if matched is None:
                m = re.search(r"^(.{3,}?[ぁ-ん一-龯ァ-ヶ])(\d{1,3})[\s　]*$", t)
                if m:
                    return {"base": m.group(1).strip(), "vol": None, "part": None, "subtitle": "",
                            "clean": t, "matched": None, "vol_suspect": int(m.group(2))}
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
    return re.sub(r"[\s　]{2,}", " ", k).strip()
