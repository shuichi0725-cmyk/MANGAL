"use client";

type Props = {
  value: string;
  onChange: (v: string) => void;
};

export default function SearchBox({ value, onChange }: Props) {
  return (
    <div className="relative">
      <input
        type="search"
        placeholder="タイトル・よみがな・ローマ字で検索"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-black/15 bg-white px-4 py-2 pr-10 focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]/40"
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange("")}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-black/40 hover:text-black"
          aria-label="検索をクリア"
        >
          ×
        </button>
      )}
    </div>
  );
}
