"use client";

type Props = {
  page: number;
  totalPages: number;
  onChange: (p: number) => void;
};

/**
 * 触感デザインのページ番号ページャ。 前へ / 番号(…省略) / 次へ。
 * 番号は先頭・末尾・現在±1 を出し、 間は … で省略(よくある仕様)。
 */
function pageList(page: number, total: number): (number | "…")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const out: (number | "…")[] = [1];
  const lo = Math.max(2, page - 1);
  const hi = Math.min(total - 1, page + 1);
  if (lo > 2) out.push("…");
  for (let i = lo; i <= hi; i++) out.push(i);
  if (hi < total - 1) out.push("…");
  out.push(total);
  return out;
}

export default function Pager({ page, totalPages, onChange }: Props) {
  if (totalPages <= 1) return null;
  const items = pageList(page, totalPages);

  const btn =
    "min-w-9 h-9 px-2 inline-flex items-center justify-center rounded-card text-sm font-medium " +
    "transition duration-100 active:scale-[0.94] select-none";

  return (
    <nav
      className="mt-8 flex flex-wrap items-center justify-center gap-1.5"
      aria-label="ページ送り"
    >
      <button
        type="button"
        onClick={() => onChange(page - 1)}
        disabled={page <= 1}
        className={`${btn} tactile-chip disabled:opacity-40 disabled:pointer-events-none`}
      >
        ← 前へ
      </button>
      {items.map((it, i) =>
        it === "…" ? (
          <span key={`e${i}`} className="px-1 text-ink/35 select-none">
            …
          </span>
        ) : (
          <button
            key={it}
            type="button"
            onClick={() => onChange(it)}
            aria-current={it === page ? "page" : undefined}
            className={
              btn +
              (it === page
                ? " bg-[var(--color-accent)] text-white shadow-[var(--shadow-soft)]"
                : " tactile-chip")
            }
          >
            {it}
          </button>
        ),
      )}
      <button
        type="button"
        onClick={() => onChange(page + 1)}
        disabled={page >= totalPages}
        className={`${btn} tactile-chip disabled:opacity-40 disabled:pointer-events-none`}
      >
        次へ →
      </button>
    </nav>
  );
}
