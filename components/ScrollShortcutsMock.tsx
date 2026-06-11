"use client";

import { useEffect, useState } from "react";

/** スクロールすると現れるショートカットバー(アイコンのみ・ロゴなし)。
 *  ページ最上部では隠れる(= サイトヘッダーが見えている時は不要、 動き出したら出る)。 */
export default function ScrollShortcutsMock() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    const onScroll = () => setShow(window.scrollY > 120);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return (
    <div
      className={`fixed inset-x-0 top-0 z-50 flex justify-center transition-transform duration-200 ${
        show ? "translate-y-0" : "-translate-y-full"
      }`}
    >
      <div className="mt-1.5 flex items-center gap-5 rounded-full border border-[var(--color-line)] bg-[var(--color-surface)]/95 px-5 py-2 shadow-md backdrop-blur">
        {[
          ["📋", "一覧"],
          ["📚", "書庫"],
          ["🔰", "使い方"],
          ["🔍", "検索"],
          ["≡", "メニュー"],
        ].map(([icon, label]) => (
          <button key={label} aria-label={label} className="text-[20px] leading-none active:scale-90">
            {icon}
          </button>
        ))}
      </div>
    </div>
  );
}
