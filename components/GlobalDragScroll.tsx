"use client";

import { useEffect } from "react";

/** PCマウスの横ドラッグ=スワイプ相当(2026-07-31 ユーザ報告「スマホでスワイプできる操作がPCだと動かない」)。
 *  サイトの横帯は overflow-x-auto + スクロールバー非表示(no-scrollbar)で統一されており、
 *  タッチ以外に操作手段が無かった(巻コーフロー/関連作品/コーナー各帯/全集タブ…)。
 *  ★方式=documentレベルの1デリゲート: pointerdown から祖先を遡り「横にあふれた scrollable」を探し、
 *  横意図(|dx|>|dy|)のドラッグだけを scrollLeft に変換する。個別コンポーネント改修ゼロで
 *  server描画の帯にも将来の帯にも効く。ドラッグ後の click は capture で1回だけ握り潰す(誤タップ防止)。
 *  タッチ/ペンはネイティブ挙動(本来のスワイプ)に任せて一切触らない。 */

const THRESHOLD = 5; // px: これ未満はクリック扱い

function findScrollableX(start: Element | null): HTMLElement | null {
  let el: Element | null = start;
  while (el && el !== document.body) {
    if (el instanceof HTMLElement && el.scrollWidth > el.clientWidth + 4) {
      const ox = getComputedStyle(el).overflowX;
      if (ox === "auto" || ox === "scroll") return el;
    }
    el = el.parentElement;
  }
  return null;
}

export default function GlobalDragScroll() {
  useEffect(() => {
    let target: HTMLElement | null = null;
    let dragging = false;
    let startX = 0, startY = 0, startL = 0, pid = -1;

    const blockClick = (e: MouseEvent) => {
      e.stopPropagation();
      e.preventDefault();
    };
    const cleanup = () => {
      if (target && dragging) {
        target.style.cursor = "";
        document.documentElement.style.userSelect = "";
        // ドラッグ直後の click を1回だけ無効化(離した位置のリンク/ボタン誤発火防止)
        document.addEventListener("click", blockClick, { capture: true, once: true });
        setTimeout(() => document.removeEventListener("click", blockClick, { capture: true } as EventListenerOptions), 0);
      }
      target = null;
      dragging = false;
      pid = -1;
    };

    const onDown = (e: PointerEvent) => {
      if (e.pointerType !== "mouse" || e.button !== 0) return;
      target = findScrollableX(e.target as Element);
      if (!target) return;
      dragging = false;
      startX = e.clientX;
      startY = e.clientY;
      startL = target.scrollLeft;
      pid = e.pointerId;
    };
    const onMove = (e: PointerEvent) => {
      if (!target || e.pointerId !== pid) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      if (!dragging) {
        if (Math.abs(dx) < THRESHOLD) return;
        if (Math.abs(dx) <= Math.abs(dy)) {
          // 縦意図(ページスクロール/テキスト選択)には介入しない
          target = null;
          return;
        }
        dragging = true;
        try {
          target.setPointerCapture(pid);
        } catch {}
        target.style.cursor = "grabbing";
        document.documentElement.style.userSelect = "none";
      }
      target.scrollLeft = startL - dx;
      e.preventDefault();
    };
    const onUp = (e: PointerEvent) => {
      if (e.pointerId !== pid) return;
      cleanup();
    };

    document.addEventListener("pointerdown", onDown, { passive: true });
    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", onUp, { passive: true });
    document.addEventListener("pointercancel", onUp, { passive: true });
    return () => {
      document.removeEventListener("pointerdown", onDown);
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
      document.removeEventListener("pointercancel", onUp);
    };
  }, []);
  return null;
}
