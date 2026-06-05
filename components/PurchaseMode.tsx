"use client";

import { createContext, useContext, useEffect, useState } from "react";

/**
 * 購入モード = 紙の書籍 (print) / 電子書籍 (ebook) のグローバル切替。
 *
 * ★狙い: 購入ボタン (Amazon紙 / Kindle / 将来は楽天等) を全部並べると画面が
 *   ごちゃつくので、 ヘッダーのトグル 1 個で「今のモードのストアだけ」を出す。
 * ★フォルダは増やさない: ストア追加 = リンク生成関数 + ボタン分岐を足すだけ。
 * ★選択は localStorage に保持 = ページ遷移・再訪でも維持。
 */
export type PurchaseMode = "print" | "ebook";

const STORAGE_KEY = "mangal:purchase-mode";

type PurchaseModeCtx = {
  mode: PurchaseMode;
  setMode: (m: PurchaseMode) => void;
  toggle: () => void;
};

const Ctx = createContext<PurchaseModeCtx | null>(null);

export function PurchaseModeProvider({ children }: { children: React.ReactNode }) {
  // 既定 = 書籍 (紙)。 初回マウント後に localStorage から復元。
  const [mode, setMode] = useState<PurchaseMode>("print");

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved === "print" || saved === "ebook") setMode(saved);
  }, []);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, mode);
    // ★html に属性付与 = globals.css が寒色テーマへ全体再着色 (0.4s遷移)
    document.documentElement.setAttribute("data-purchase-mode", mode);
  }, [mode]);

  const toggle = () => setMode((m) => (m === "print" ? "ebook" : "print"));

  return <Ctx.Provider value={{ mode, setMode, toggle }}>{children}</Ctx.Provider>;
}

export function usePurchaseMode(): PurchaseModeCtx {
  const c = useContext(Ctx);
  // Provider 外で呼ばれても落ちないよう安全な既定を返す。
  return c ?? { mode: "print", setMode: () => {}, toggle: () => {} };
}

/**
 * ヘッダー右上のトグル 1 個。 ★舞台セットの表裏のように 180度フリップして
 * 紙 ⇄ 電子 が入れ替わる (0.4s)。 面=書籍 / 裏=電子書籍。
 */
export function PurchaseModeToggle() {
  const { mode, toggle } = usePurchaseMode();
  const isEbook = mode === "ebook";
  const next = isEbook ? "書籍(紙)" : "電子書籍";
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={`購入モード: 現在は${isEbook ? "電子書籍" : "書籍(紙)"}。 タップで${next}に切替`}
      title={`タップで${next}モードに切替`}
      className="flip-toggle relative h-9 w-32 shrink-0 text-sm active:scale-95 transition-transform"
    >
      <span className={`flip-inner block ${isEbook ? "is-ebook" : ""}`}>
        {/* 面 = 書籍 */}
        <span className="flip-face flip-front">
          <span aria-hidden className="text-xs text-ink/40">⇄</span>
          <span aria-hidden>📖</span>
          <span>書籍</span>
        </span>
        {/* 裏 = 電子書籍 */}
        <span className="flip-face flip-back">
          <span aria-hidden className="text-xs opacity-50">⇄</span>
          <span aria-hidden>📱</span>
          <span>電子書籍</span>
        </span>
      </span>
    </button>
  );
}
