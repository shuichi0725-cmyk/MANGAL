"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";

/**
 * 購入モード = 紙の書籍 (print) / 電子書籍 (ebook) のグローバル切替。
 *
 * ★狙い: 購入ボタン (Amazon紙 / Kindle / 将来は楽天等) を全部並べると画面が
 *   ごちゃつくので、 ヘッダーのトグル 1 個で「今のモードのストアだけ」を出す。
 * ★切替時は ★画面全体★ が舞台セットのように 180度フリップして裏面 (電子) が現れる。
 * ★電子モードは全体が寒色テーマに変わる (globals.css の html[data-purchase-mode])。
 * ★選択は localStorage に保持 = ページ遷移・再訪でも維持。
 */
export type PurchaseMode = "print" | "ebook";

const STORAGE_KEY = "mangal:purchase-mode";
const FLIP_MS = 450; // 全体フリップ所要 (0.3〜0.5s帯)
const SWAP_MS = 225; // 半回転=エッジオンの瞬間に色・モードを入替

type PurchaseModeCtx = {
  mode: PurchaseMode;
  setMode: (m: PurchaseMode) => void;
  toggle: () => void;
  flipping: boolean;
};

const Ctx = createContext<PurchaseModeCtx | null>(null);

export function PurchaseModeProvider({ children }: { children: React.ReactNode }) {
  // 既定 = 書籍 (紙)。 初回マウント後に localStorage から復元。
  const [mode, setMode] = useState<PurchaseMode>("print");
  const [flipping, setFlipping] = useState(false);
  const timers = useRef<number[]>([]);

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved === "print" || saved === "ebook") setMode(saved);
  }, []);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, mode);
    // ★html に属性付与 = globals.css が寒色テーマへ全体再着色 (0.4s遷移)
    document.documentElement.setAttribute("data-purchase-mode", mode);
  }, [mode]);

  useEffect(() => () => timers.current.forEach((t) => window.clearTimeout(t)), []);

  const toggle = () => {
    if (flipping) return; // 回転中の二重発火を無視
    const next: PurchaseMode = mode === "print" ? "ebook" : "print";

    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setMode(next); // 動き控えめ設定 = 瞬時切替
      return;
    }

    setFlipping(true);
    // 半回転 (エッジオンで見えない瞬間) に色・モードを入替 = 裏返って見える
    timers.current.push(window.setTimeout(() => setMode(next), SWAP_MS));
    timers.current.push(window.setTimeout(() => setFlipping(false), FLIP_MS + 20));
  };

  return (
    <Ctx.Provider value={{ mode, setMode, toggle, flipping }}>{children}</Ctx.Provider>
  );
}

export function usePurchaseMode(): PurchaseModeCtx {
  const c = useContext(Ctx);
  // Provider 外で呼ばれても落ちないよう安全な既定を返す。
  return c ?? { mode: "print", setMode: () => {}, toggle: () => {}, flipping: false };
}

/**
 * ★画面全体フリップの器。 main をこれで包む。 flipping 中だけ rotateY アニメ。
 * 0→90度(エッジオン)で消え、 -90→0度で裏面(再着色済)が回り込んで来る =
 * 舞台セットが裏返る見え方。 文字が鏡像にならないようエッジオンで入替える。
 */
export function ScreenFlip({ children }: { children: React.ReactNode }) {
  const { flipping } = usePurchaseMode();
  return (
    <div className="screen-flip-stage flex-1 flex flex-col">
      <div className={`screen-flip-panel flex-1 flex flex-col${flipping ? " is-flipping" : ""}`}>
        {children}
      </div>
    </div>
  );
}

/**
 * ヘッダー右上のトグル 1 個。 ★ボタン自体は回らず (回転は画面全体)、
 * 現在モードを表示して幅は固定 (w-32)。
 */
export function PurchaseModeToggle() {
  const { mode, toggle, flipping } = usePurchaseMode();
  const isEbook = mode === "ebook";
  const next = isEbook ? "書籍(紙)" : "電子書籍";
  return (
    <button
      type="button"
      onClick={toggle}
      disabled={flipping}
      aria-label={`購入モード: 現在は${isEbook ? "電子書籍" : "書籍(紙)"}。 タップで${next}に切替`}
      title={`タップで${next}モードに切替`}
      className="tactile-chip mode-recolor inline-flex h-9 w-32 shrink-0 items-center justify-center gap-1.5 rounded-full text-sm font-medium"
    >
      <span aria-hidden className="text-xs text-ink/40">⇄</span>
      <span aria-hidden>{isEbook ? "📱" : "📖"}</span>
      <span className="whitespace-nowrap">{isEbook ? "電子書籍" : "書籍"}</span>
    </button>
  );
}
