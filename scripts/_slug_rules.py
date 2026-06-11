"""slug ローマ字化の共通規則 (= 2026-06-10 ユーザ裁定 4規則の実装。 CLAUDE.md「ローマ字化4規則」)。

①長音 = 保持 (= おう→ou / うう→uu 逐字。 旧5/31裁定の drop_long は廃止)
   例外: 英語圏で定着した固有名詞 (= Tokyo 等) は定着綴り (FIXED_SPELLING)
②助詞「ヲ」= o (= ヘボン標準。 wo は使わない。 token 単独の ヲ のみ = 語中の ヲ は不変)
③敬称ハイフン = 呼び出し側 (= v1 split_honorific) が token 分離してから本 module に渡す
④カタカナ外来語 = 英綴り資産 (= gap a/b override 層) が優先、 本 module はヘボン fallback

v1/_slug-assemble/_slug-num-fix が共用。 drop_long は比較・正規化用途でのみ各所に残存
(= 姓ローマ字 [AniList 慣行=長音落ち] / 音写骨格比較 は意図的に旧式維持)。
"""
import json
import re
from pathlib import Path

import pykakasi

_kks = pykakasi.kakasi()
_ROOT = Path(__file__).resolve().parent.parent

# ①例外: 英語圏で定着した固有名詞 (token 単位、 hep 後の綴りで引く)。
# ★2026-06-11 ユーザ採用(A全部)。 ※カントウは「巻頭」同音のため不採用 / 人名(tarou等)は
#   同読み一般語(週一/高1/勇気)と不可分のためヘボン維持(ユーザ報告済)。
FIXED_SPELLING = {
    "toukyou": "tokyo", "tookyoo": "tokyo",
    "kyouto": "kyoto",
    "oosaka": "osaka",
    "koube": "kobe",
    "koushien": "koshien",
    "ooedo": "oedo",
    "shougun": "shogun",
    "shougi": "shogi",
    "juudou": "judo",
    "hokkaidou": "hokkaido",
    "ryuukyuu": "ryukyu",
    "sumou": "sumo",
    "kendou": "kendo",
    "toukai": "tokai",
    "touhoku": "tohoku",
    "kyuudou": "kyudo",
}

# ④埋込カタカナ外来語 = kata-dict(検証済2,412語)を ★ガード付きで token 適用(2026-06-11 ユーザC採用)。
#   ガード: 全カタカナ・2文字以上 / 値=英字のみ3字以上 / 切断防止(値が読みの半分未満なら不採用)。
#   → ゲーム→game / アンソロジー→anthology は通り、 オ→wo / ツー→2 / スローライフ→life は弾く。
_KATA_RE = re.compile(r"^[゠-ヿー・]+$")
_VAL_RE = re.compile(r"^[a-z][a-z-]*$")
try:
    KATA_DICT = json.loads((_ROOT / ".cache" / "kata-dict.json").read_text(encoding="utf-8"))
except OSError:
    KATA_DICT = {}


def hep(kana):
    """かな→ヘボン (pykakasi)。 長音は逐字 (マホウカ→mahouka / スクール→sukuuru)。"""
    return "".join(it["hepburn"] for it in _kks.convert(kana)).lower()


def _dict_value(tok):
    """埋込カタカナ外来語の英綴り (ガード通過時のみ)。 不採用なら None。"""
    if len(tok) < 2 or not _KATA_RE.match(tok):
        return None
    v = KATA_DICT.get(tok)
    if not v or not _VAL_RE.match(v):
        return None
    core = v.replace("-", "")
    if len(core) < 3:
        return None
    if 2 * len(core) < len(hep(tok)):   # 切断ガード (スローライフ→life 型)
        return None
    return v


def token_roman(tok):
    """分かち書き token 1つ → ローマ字 (規則①②④適用、 記号除去)。"""
    if tok in ("ヲ", "を"):
        return "o"
    v = _dict_value(tok)
    if v:
        return v
    r = re.sub(r"[^a-z0-9]+", "", hep(tok))
    return FIXED_SPELLING.get(r, r)
