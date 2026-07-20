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
 */
export function normalizeForSearch(input: string): string {
  return input
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[ー・\-\s]/g, "")
    .replace(/[ァ-ヶ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0x60))
    .replace(/[惡應戀壽假萬圓學國]/g, (c) => "悪応恋寿仮万円学国"["惡應戀壽假萬圓學國".indexOf(c)])
    .trim();
}
