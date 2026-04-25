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
 * - NFKC で全角半角を統一
 * - 小文字化
 * - 長音符・ハイフン・空白を除去（"wanpi-su" と "wanpisu" を同一視）
 */
export function normalizeForSearch(input: string): string {
  return input
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[ー\-\s]/g, "")
    .trim();
}
