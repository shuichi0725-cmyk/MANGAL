"use client";

import { useEffect, useState } from "react";

/** ショートカットバー: 見た目はヘッダーと同じ全幅バー。 最上部では隠れていて、
 *  スクロールすると上からしまわれていたものが出てくる(戻るとまたしまわれる)。 */
export default function ScrollShortcutsMock() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    const onScroll = () => setShow(window.scrollY > 120);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return (
    // 見本市バー(高さ~37px)の下から出てくる。 本実装ではサイトヘッダー直下に差し替え
    <div
      className={`fixed inset-x-0 top-[37px] z-40 transition-transform duration-200 ease-out ${
        show ? "translate-y-0" : "-translate-y-[150%]"
      }`}
    >
      <div className="flex items-center justify-end gap-5 border-b border-[var(--color-line)] bg-[var(--color-surface)]/95 px-5 pb-2 pt-2.5 shadow-sm backdrop-blur">
        {[
          ["📋", "一覧"],
          ["📚", "書庫"],
          ["🔰", "使い方"],
          ["🔍", "検索"],
          ["≡", "メニュー"],
        ].map(([icon, label]) => (
          <button key={label} aria-label={label} className="flex flex-col items-center gap-0.5 active:scale-90">
            <span className="text-[19px] leading-none">{icon}</span>
            <span className="text-[9px] text-ink/50">{label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
