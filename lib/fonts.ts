import { DotGothic16 } from "next/font/google";

/** E融合型(2026-08-15)のドット文字見出し用。日本語グリフはunicode-range分割で遅延読込されるため
 *  preloadはlatinのみ=falseで抑制(巨大JPサブセットの先読みを避ける)。 */
export const dotGothic = DotGothic16({
  weight: "400",
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--font-dot",  // ★2026-08-24 ユーザ指示「無理なく適応できる所に展開」: .dot-heading(globals)が参照
});

/** ★ドット体の見出しクラス = `dot-heading`(globals.css の font-family)+ フォント変数 を同じ要素に付ける。
 *  2026-09-24: 旧= app/layout.tsx の <body> に dotGothic.variable を付けていた → @font-face 124個
 *  (展開91KB・br 30KB)が**全頁で描画をブロック**していた(作品頁6.9万枚は1つも使っていない)。
 *  使う部品だけがこの定数を import する = フォントのCSSはその部品が載る頁にだけ入る。
 *  ★className に生の "dot-heading" を書かない(変数が無く sans-serif に落ちる)。
 *  ★layout から到達する部品では使わない(また全頁に載る)。番人 = _check-shell-wiring.py 検査5。 */
export const DOT_HEADING = `dot-heading ${dotGothic.variable}`;
