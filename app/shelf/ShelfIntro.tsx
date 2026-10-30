"use client";

import { useState } from "react";

/**
 * 見出し「本棚」+ 横の「?」で説明文を開く(案A 2026-10-31 ユーザ裁定: 説明文6行で棚が画面の下半分から始まっていた)。
 * ★既定は畳む = サーバ描画と水和が一致する(保存を読まない)。
 */
export default function ShelfIntro() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <div className="shelf-head">
        <h1 className="text-xl font-extrabold">📚 本棚</h1>
        <button
          type="button"
          className="shelf-help-q"
          aria-expanded={open}
          aria-controls="shelf-help"
          aria-label="本棚の使い方"
          onClick={() => setOpen((v) => !v)}
        >
          ?
        </button>
      </div>
      {/* ★日本語の文は行をまたがない(JSX は改行を空白1つにする) */}
      <p id="shelf-help" hidden={!open} className="mt-1.5 text-[12.5px] leading-relaxed text-ink/70">
        作品頁の「しまう」で入れた漫画が、<b>もってる</b>・<b>ほしい</b>・<b>気になる</b>の棚に並びます。
        {"「もってる」は1巻から何巻まで持っているかを覚えていて、続きの巻が出ていれば番号のタイルと札でお知らせします。"}
        {"番号のタイルを押すとその巻の書影が開き、「ここまで持ってる」で巻数を直せます。"}
        {"段を長押し(PCは右クリック)か「⋯」で、棚の移動・巻数の変更・取り出しができます。"}
        {"棚はこの端末だけに保存されるので、頁の下の「棚のURL」を保存しておくと、消えても元に戻せます。"}
      </p>
    </>
  );
}
