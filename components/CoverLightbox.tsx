"use client";

import { useCallback, useEffect, useState } from "react";

/** 書影ライトボックス(2026-08-03 ユーザ要望): カード上の書影を押すと**最高画質**で大きく表示。
 *  - 最高画質 = 楽天サムネの `?_ex=NxN` を外したマスター原寸(スマホ/PC共通)。
 *  - 開いている間は背景操作不可(全面オーバーレイ)。閉じる = ✕ / 背景クリック / Esc。
 *  - 子要素(通常表示の書影)をトリガーとして包むだけ=既存レイアウト不変。 */
export default function CoverLightbox({
  src, label, children, className,
}: {
  src: string | null | undefined;
  label?: string;
  children: React.ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden"; // 背景スクロールも封じる
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, close]);

  if (!src) return <>{children}</>;
  const hi = src.replace(/\?_ex=\d+x\d+/, ""); // マスター原寸

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={`${label ?? "書影"}を拡大表示`}
        className={className ?? "block h-full w-full cursor-zoom-in"}
      >
        {children}
      </button>
      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`${label ?? "書影"}の拡大表示`}
          onClick={close}
          className="fixed inset-0 z-[999] flex flex-col items-center justify-center bg-black/85 p-4 backdrop-blur-sm"
        >
          <button
            type="button"
            onClick={close}
            aria-label="閉じる"
            className="absolute right-3 top-3 flex h-10 w-10 items-center justify-center rounded-full bg-white/15 text-xl text-white hover:bg-white/25"
          >
            ✕
          </button>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={hi}
            alt={label ?? "書影"}
            className="max-h-[88vh] max-w-[94vw] rounded bg-white object-contain shadow-[0_20px_60px_rgba(0,0,0,.6)]"
            onClick={(e) => e.stopPropagation()}
          />
          {label && <p className="mt-3 text-[13px] font-bold text-white/85">{label}</p>}
          <p className="mt-1 text-[11px] text-white/50">タップまたは ✕ で閉じる</p>
        </div>
      )}
    </>
  );
}
