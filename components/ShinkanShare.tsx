"use client";

/** 共有ボタン(旧ShinkanClient から移植 2026-09-01)。navigator.share が無ければ X のポスト画面。 */
export default function ShinkanShare({ url, text }: { url: string; text: string }) {
  const share = () => {
    if (typeof navigator !== "undefined" && navigator.share) {
      navigator.share({ title: text, url }).catch(() => {});
    } else {
      window.open(`https://x.com/intent/post?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`, "_blank");
    }
  };
  return (
    <button type="button" onClick={share} aria-label="このページを共有"
      className="spring-press ml-auto border-2 border-[var(--color-accent)] px-2.5 py-1 text-[11px] font-black text-[var(--color-accent)]">
      共有
    </button>
  );
}
