import { toRomaji, toHiragana } from "wanakana";

export function kanaToRomaji(input: string): string {
  return toRomaji(input).toLowerCase();
}

export function romajiToHiragana(input: string): string {
  return toHiragana(input.toLowerCase());
}

/**
 * 検索照合用の正規化:
 * - ダイアクリティカルマーク（マクロン等）を除去
 * - NFKC で全角半角を統一（半角中黒 ･ U+FF65 → ・ U+30FB も統一）
 * - 小文字化
 * - 長音符・ハイフン・空白・中黒(・)を除去
 *   （"wanpi-su"="wanpisu" / "シャングリラ・フロンティア"="シャングリラフロンティア" を同一視。
 *    中黒は位置揺れも吸収=「シャングリ・ラフロンティア」でも当たる）
 * - ★カタカナ→ひらがな畳み込み(2026-07-21): 「こちかめ」⇄「コチカメ」等、クエリと
 *   データのかな表記種が違っても直接当たる(クエリ・haystack双方が本関数を通る前提)
 * - ★数字表記揺れ折り畳み(2026-07-27 会議決定): ローマ数字(Ⅱ/II)・漢数字(単字)・カナ数詞
 *   (ツー/スリー等)を算用数字へ統一。「ロザリオとバンパイアseason2」でseasonⅡ頁が、
 *   「世紀末ダーリン2」で年次頁が当たる。クエリ・haystack双方が同関数を通るので
 *   置換の衝突(ワンピース→1ピース等)は両側で一貫し自己一致は壊れない。
 *   ※データ監査側の同種正規化は scripts/_title_numnorm.py(検出器用・別実装)。片方を
 *   直したらもう片方も見ること。位取り漢数字(十百千)は誤爆リスクで両実装とも対象外。
 */
const KANA_NUMS: Array<[string, string]> = [
  ["トゥエルブ", "12"], ["イレブン", "11"], ["ファースト", "1"], ["セカンド", "2"],
  ["サード", "3"], ["フォース", "4"], ["フィフス", "5"], ["シックス", "6"],
  ["セブン", "7"], ["エイト", "8"], ["ナイン", "9"], ["テン", "10"],
  ["ファイブ", "5"], ["フォー", "4"], ["スリー", "3"], ["ツー", "2"], ["ワン", "1"],
];
const ROMAN_MAP: Record<string, string> = {
  i: "1", ii: "2", iii: "3", iv: "4", v: "5", vi: "6", vii: "7", viii: "8",
  ix: "9", x: "10", xi: "11", xii: "12",
};
function foldNumerals(s: string): string {
  // ローマ数字(ASCII綴り): 英字に挟まれていない単独トークンのみ(ILLUSION等の語中は不変)。
  // 空白除去より前に呼ぶこと(境界が要る)。
  s = s.replace(/(?<![a-z])[ivx]{1,4}(?![a-z])/g, (m) => ROMAN_MAP[m] ?? m);
  for (const [k, v] of KANA_NUMS) s = s.split(k).join(v);
  s = s.replace(/[一二三四五六七八九〇零]/g, (c) => "12345678900"["一二三四五六七八九〇零".indexOf(c)]);
  return s;
}

/** Unicodeローマ数字文字(Ⅱ等)を数字へ。★NFKCより前に呼ぶ(NFKCはⅡ→"II"へ分解し
 *  「seasonⅡ」が"seasonii"と連結して境界判定が効かなくなる=2026-07-27実測)。 */
function foldUnicodeRoman(s: string): string {
  return s.replace(/[Ⅰ-Ⅻⅰ-ⅻ]/g, (c) => {
    const n = (c.charCodeAt(0) - (c.charCodeAt(0) >= 0x2170 ? 0x2170 : 0x2160)) + 1;
    return String(n);
  });
}

export function normalizeForSearch(input: string): string {
  return foldNumerals(
    foldUnicodeRoman(input)
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .normalize("NFKC")
      .toLowerCase(),
  )
    .replace(/[ー・\-\s]/g, "")
    .replace(/[ァ-ヶ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0x60))
    .replace(/[惡應戀壽假萬圓學國]/g, (c) => "悪応恋寿仮万円学国"["惡應戀壽假萬圓學國".indexOf(c)])
    .trim();
}
