"""slug ローマ字化の共通規則 (= 2026-06-10 ユーザ裁定 4規則の実装。 CLAUDE.md「ローマ字化4規則」)。

①長音 = 保持 (= おう→ou / うう→uu 逐字。 旧5/31裁定の drop_long は廃止)
   例外: 英語圏で定着した固有名詞 (= Tokyo 等) は定着綴り (FIXED_SPELLING)
②助詞「ヲ」= o (= ヘボン標準。 wo は使わない。 token 単独の ヲ のみ = 語中の ヲ は不変)
③敬称ハイフン = 呼び出し側 (= v1 split_honorific) が token 分離してから本 module に渡す
④カタカナ外来語 = 英綴り資産 (= gap a/b override 層) が優先、 本 module はヘボン fallback

v1/_slug-assemble/_slug-num-fix が共用。 drop_long は比較・正規化用途でのみ各所に残存
(= 姓ローマ字 [AniList 慣行=長音落ち] / 音写骨格比較 は意図的に旧式維持)。
"""
import re

import pykakasi

_kks = pykakasi.kakasi()

# ①例外: 英語圏で定着した固有名詞 (token 単位、 hep 後の綴りで引く)。 ★最小リスト=要レビュー
FIXED_SPELLING = {
    "toukyou": "tokyo", "tookyoo": "tokyo",
    "kyouto": "kyoto",
    "oosaka": "osaka",
    "koube": "kobe",
}


def hep(kana):
    """かな→ヘボン (pykakasi)。 長音は逐字 (マホウカ→mahouka / スクール→sukuuru)。"""
    return "".join(it["hepburn"] for it in _kks.convert(kana)).lower()


def token_roman(tok):
    """分かち書き token 1つ → ローマ字 (規則①②適用、 記号除去)。"""
    if tok in ("ヲ", "を"):
        return "o"
    r = re.sub(r"[^a-z0-9]+", "", hep(tok))
    return FIXED_SPELLING.get(r, r)
