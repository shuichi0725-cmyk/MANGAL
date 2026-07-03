"use client";

import { useEffect, useState } from "react";

/** いいねボタン(本実装): Worker /api/like + KV の匿名カウンタ(PIIゼロ)。
 *  API不在環境(preview等)では localStorage のみで劣化動作(エラーは出さない)。 */
export default function LikeButton({ id }: { id: string }) {
  const [liked, setLiked] = useState(false);
  const [n, setN] = useState<number | null>(null);
  useEffect(() => {
    if (typeof window === "undefined") return;
    setLiked(!!localStorage.getItem(`like:${id}`));
    fetch(`/api/like?id=${encodeURIComponent(id)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d && typeof d.count === "number") setN(d.count);
      })
      .catch(() => {});
  }, [id]);
  return (
    <button
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        if (liked) return; // 一度押したら取り消しなし(カウンタの整合を単純に保つ)
        setLiked(true);
        setN((v) => (v == null ? 1 : v + 1));
        localStorage.setItem(`like:${id}`, "1");
        fetch("/api/like", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ id }),
        }).catch(() => {});
      }}
      className={`spring-press inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors ${
        liked
          ? "border-rose-300 bg-rose-50 text-rose-500"
          : "border-[var(--color-line)] bg-[var(--color-surface)] text-ink/50"
      }`}
      aria-label="いいね"
    >
      {liked ? "♥" : "♡"} {n == null ? "" : n}
    </button>
  );
}
