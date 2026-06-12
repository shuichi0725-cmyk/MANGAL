"use client";

import { useEffect, useState } from "react";

/** いいねボタンのモック(見本市用)。 本実装 = Cloudflare Worker + KV の匿名カウンタ
 *  (POST /api/like {date, persona} → 集計のみ・PIIゼロ)。 ここでは localStorage でデモ。 */
export default function LikeButtonMock({ id, base }: { id: string; base: number }) {
  const [liked, setLiked] = useState(false);
  const [n, setN] = useState(base);
  useEffect(() => {
    if (typeof window !== "undefined" && localStorage.getItem(`like:${id}`)) {
      setLiked(true);
      setN(base + 1);
    }
  }, [id, base]);
  return (
    <button
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        const next = !liked;
        setLiked(next);
        setN(base + (next ? 1 : 0));
        if (next) localStorage.setItem(`like:${id}`, "1");
        else localStorage.removeItem(`like:${id}`);
      }}
      className={`spring-press inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10.5px] font-semibold active:scale-90 ${
        liked
          ? "border-rose-300 bg-rose-50 text-rose-600"
          : "border-[var(--color-line)] bg-[var(--color-surface)] text-ink/55"
      }`}
    >
      {liked ? "♥" : "♡"} {n}
    </button>
  );
}
