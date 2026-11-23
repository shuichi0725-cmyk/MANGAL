"use client";

import { useEffect } from "react";

/**
 * 上端固定の帯(共通ヘッダー + アイコンナビ = layout の #site-chrome)の実高を CSS 変数 `--chrome-h` に入れる。
 * ★2026-11-24 ユーザ指示「ヘッダーのホームや検索ボタンが下にスクロールすると消える。全ページで固定に」。
 *   帯の下に貼り付く他の sticky(新刊の日付見出し・PC左レール)と、#見出しへの飛び先(scroll-padding)が
 *   この変数で帯の下に着地する。 既定値は globals.css の :root(描画前・JS無しでもほぼ正しい高さ)。
 */
export default function ChromeHeightVar() {
  useEffect(() => {
    const el = document.getElementById("site-chrome");
    if (!el) return;
    const set = () => document.documentElement.style.setProperty("--chrome-h", `${el.offsetHeight}px`);
    set();
    const ro = new ResizeObserver(set);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return null;
}
