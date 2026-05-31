"use client";

import { useEffect, useState } from "react";

/**
 * スクロールすると右下に出る「先頭へ戻る」フローティングボタン。
 * 全ページ共通(layout に1つ設置)。 触感デザイン統一(surface地+境界+柔影+押下)。
 */
export default function ScrollTopButton() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > 400);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <button
      type="button"
      aria-label="ページ上部へ戻る"
      onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
      className={
        "tactile fixed bottom-5 right-4 z-30 flex h-11 w-11 items-center justify-center " +
        "rounded-full text-lg text-ink/70 active:scale-90 transition-opacity duration-200 " +
        (visible ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none")
      }
    >
      ↑
    </button>
  );
}
