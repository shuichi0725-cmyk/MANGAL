"use client";

type Props = {
  value: string;
  onChange: (v: string) => void;
};

export default function SearchBox({ value, onChange }: Props) {
  return (
    <div className="relative">
      <span
        className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink/35"
        aria-hidden="true"
      >
        🔍
      </span>
      <input
        type="search"
        placeholder="タイトル・よみがな・ローマ字で検索"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-card border border-[var(--color-line)] bg-[var(--color-surface)] shadow-[var(--shadow-soft)] pl-9 pr-10 py-2.5 text-sm transition focus:outline-none focus:border-[var(--color-accent)] focus:shadow-[var(--shadow-lift)]"
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange("")}
          className="absolute right-2 top-1/2 -translate-y-1/2 flex h-6 w-6 items-center justify-center rounded-full text-ink/40 hover:bg-[var(--color-surface-2)] hover:text-ink transition-colors"
          aria-label="検索をクリア"
        >
          ×
        </button>
      )}
    </div>
  );
}
