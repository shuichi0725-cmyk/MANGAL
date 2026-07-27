# -*- coding: utf-8 -*-
"""題の数字表記揺れを吸収する正規化(共有モジュール)。

ロザリオとバンパイア seasonⅡ vs season2(2026-07-27 ユーザ発見の分裂型)の恒久対策。
使用箇所: _audit-numeral-variant-split.py(検出器) / _torikoboshi-genpages.py(近似題ゲート)。
★ここを直したら両方に効く(コピペ分岐を作らない)。
"""
import re
import unicodedata

# ローマ数字(NFKCでⅡ→II等の互換分解はされるが算用にはならない)
_ROMAN = [("XII", "12"), ("XI", "11"), ("IX", "9"), ("VIII", "8"), ("VII", "7"),
          ("XI", "11"), ("X", "10"), ("VI", "6"), ("IV", "4"), ("V", "5"),
          ("III", "3"), ("II", "2"), ("I", "1")]
# カナ数詞(単語境界が取れないので長い順・題末尾/区切り近傍でよく出る形のみ)
_KANA_NUM = [("トゥエルブ", "12"), ("イレブン", "11"), ("テン", "10"), ("ナイン", "9"),
             ("エイト", "8"), ("セブン", "7"), ("シックス", "6"), ("ファイブ", "5"),
             ("フォー", "4"), ("スリー", "3"), ("ツー", "2"), ("ワン", "1"),
             ("セカンド", "2"), ("サード", "3"), ("ファースト", "1")]
_KANJI_NUM = str.maketrans("一二三四五六七八九〇零壱弐参", "12345678900123")


def numnorm(t: str) -> str:
    """NFKC→小文字→漢数字/カナ数詞/ローマ数字→算用→記号・空白除去。
    ★ローマ数字は「英字語中のI/V/X」を巻き添えないよう、数字・区切り文字に
    隣接する単独トークンのみ置換する。"""
    s = unicodedata.normalize("NFKC", str(t or ""))
    s = s.translate(_KANJI_NUM)
    for k, v in _KANA_NUM:
        s = s.replace(k, v)
    # ローマ数字: 前後が英字でない位置の I/II/... のみ(season II / PARTIII 型を拾い、
    #   ILLUSION 等の語中は触らない)
    def _rn(m):
        w = m.group(0).upper()
        for r, a in _ROMAN:
            if w == r:
                return a
        return m.group(0)
    s = re.sub(r"(?<![A-Za-z])[IVXivx]{1,4}(?![A-Za-z])", _rn, s)
    s = s.lower()
    return re.sub(r"[\s　〜~！!?？・:：（）()【】\[\]「」『』\-。、．.=＆&＋+']", "", s)
