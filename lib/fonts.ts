import { DotGothic16 } from "next/font/google";

/** E融合型(2026-08-15)のドット文字見出し用。日本語グリフはunicode-range分割で遅延読込されるため
 *  preloadはlatinのみ=falseで抑制(巨大JPサブセットの先読みを避ける)。 */
export const dotGothic = DotGothic16({
  weight: "400",
  subsets: ["latin"],
  display: "swap",
  preload: false,
});
