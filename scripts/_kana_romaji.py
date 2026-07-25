"""カナ→ローマ字(ヘボン・決定的) = **新規頁のslug生成の単一ソース**。

規則(CLAUDE.md「ローマ字化4規則」2026-06-10 ユーザ裁定):
  長音=直前母音を重ねる / 助詞ヲ=o / 促音=次の頭子音を重ねる / 記号・空白=hyphen。
2026-07-25 に `_preorder-gen-preview.py` から切り出し(取りこぼし頁化でも同じ変換を使うため。
★コピペで別実装を作らない=slugは後からrename困難)。
"""
import re
import unicodedata

# --- カナ→ローマ字(ヘボン・決定的)。slug規則: 長音=母音連続(おう→ou相当はカナ由来でォ表現なし=ーは前母音重ね)/を=o/スペース=hyphen ---
_K2R = {
 "ア":"a","イ":"i","ウ":"u","エ":"e","オ":"o","カ":"ka","キ":"ki","ク":"ku","ケ":"ke","コ":"ko",
 "サ":"sa","シ":"shi","ス":"su","セ":"se","ソ":"so","タ":"ta","チ":"chi","ツ":"tsu","テ":"te","ト":"to",
 "ナ":"na","ニ":"ni","ヌ":"nu","ネ":"ne","ノ":"no","ハ":"ha","ヒ":"hi","フ":"fu","ヘ":"he","ホ":"ho",
 "マ":"ma","ミ":"mi","ム":"mu","メ":"me","モ":"mo","ヤ":"ya","ユ":"yu","ヨ":"yo",
 "ラ":"ra","リ":"ri","ル":"ru","レ":"re","ロ":"ro","ワ":"wa","ヲ":"o","ン":"n",
 "ガ":"ga","ギ":"gi","グ":"gu","ゲ":"ge","ゴ":"go","ザ":"za","ジ":"ji","ズ":"zu","ゼ":"ze","ゾ":"zo",
 "ダ":"da","ヂ":"ji","ヅ":"zu","デ":"de","ド":"do","バ":"ba","ビ":"bi","ブ":"bu","ベ":"be","ボ":"bo",
 "パ":"pa","ピ":"pi","プ":"pu","ペ":"pe","ポ":"po","ヴ":"vu",
 "キャ":"kya","キュ":"kyu","キョ":"kyo","シャ":"sha","シュ":"shu","ショ":"sho","チャ":"cha","チュ":"chu","チョ":"cho",
 "ニャ":"nya","ニュ":"nyu","ニョ":"nyo","ヒャ":"hya","ヒュ":"hyu","ヒョ":"hyo","ミャ":"mya","ミュ":"myu","ミョ":"myo",
 "リャ":"rya","リュ":"ryu","リョ":"ryo","ギャ":"gya","ギュ":"gyu","ギョ":"gyo","ジャ":"ja","ジュ":"ju","ジョ":"jo",
 "ビャ":"bya","ビュ":"byu","ビョ":"byo","ピャ":"pya","ピュ":"pyu","ピョ":"pyo",
 "ファ":"fa","フィ":"fi","フェ":"fe","フォ":"fo","ティ":"ti","ディ":"di","デュ":"dyu","ウィ":"wi","ウェ":"we","ウォ":"wo",
 "シェ":"she","ジェ":"je","チェ":"che","ツァ":"tsa","ツェ":"tse","ツォ":"tso","トゥ":"tu","ドゥ":"du","イェ":"ye","ヴァ":"va","ヴィ":"vi","ヴェ":"ve","ヴォ":"vo",
}
def kana2romaji(kana: str) -> str:
    s = unicodedata.normalize("NFKC", str(kana or ""))
    # ひら→カタ
    s = "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ん" else c for c in s)
    out = []
    i = 0
    while i < len(s):
        c = s[i]
        two = s[i:i+2]
        if c == "ッ":
            # 促音: 次のローマ字の頭子音を重ねる
            nxt = _K2R.get(s[i+1:i+3]) or _K2R.get(s[i+1:i+2]) or ""
            out.append(nxt[0] if nxt and nxt[0] not in "aiueo" else "")
            i += 1
            continue
        if c == "ー":
            # 長音: 直前母音を重ねる(長音保持規則)
            prev = out[-1][-1] if out and out[-1] else ""
            out.append(prev if prev in "aiueo" else "")
            i += 1
            continue
        if two in _K2R:
            out.append(_K2R[two]); i += 2; continue
        if c in _K2R:
            out.append(_K2R[c]); i += 1; continue
        if re.match(r"[A-Za-z0-9]", c):
            out.append(c.lower()); i += 1; continue
        if c in " 　・=/:：〜~☆★!！?？、。,.'’\"-−–":
            out.append("-"); i += 1; continue
        out.append("-"); i += 1
    r = "".join(out)
    r = re.sub(r"-+", "-", r).strip("-")
    # ん+母音/ y → n のまま(簡易)。空なら失敗
    return r

