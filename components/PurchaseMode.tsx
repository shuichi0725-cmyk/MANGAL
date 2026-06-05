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
 * ヘッダー右上のトグル 1 個。 タップで 紙 ⇄ 電子 が入れ替わる。
 * ラベル = 現在のモード。 ⇄ アイコンで「切り替わる」ことを示す。
 */
export function PurchaseModeToggle() {
  const { mode, toggle } = usePurchaseMode();
  const isPrint = mode === "print";
  const next = isPrint ? "電子書籍" : "書籍(紙)";
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={`購入モード: 現在は${isPrint ? "書籍(紙)" : "電子書籍"}。 タップで${next}に切替`}
      title={`タップで${next}モードに切替`}
      className="tactile-chip inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium active:scale-95 transition"
    >
      <span aria-hidden className="text-xs text-ink/40">⇄</span>
      <span aria-hidden>{isPrint ? "📖" : "📱"}</span>
      <span className="whitespace-nowrap">{isPrint ? "書籍" : "電子書籍"}</span>
    </button>
  );
}
