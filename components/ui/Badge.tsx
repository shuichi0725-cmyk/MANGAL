type Props = {
  tone?: "neutral" | "accent" | "warm";
  className?: string;
  children: React.ReactNode;
};

/**
 * 小型ピルバッジ (= status / 分野 / 巻数 等のラベル)。 記事のオレンジタグ相当。
 * 押せない静的ラベル(リンクでない)。 tone で色を出し分け。
 */
export default function Badge({ tone = "neutral", className = "", children }: Props) {
  const skin =
    tone === "accent"
      ? "bg-[var(--color-accent)] text-white"
      : tone === "warm"
        ? "bg-[var(--color-accent-warm)] text-white"
        : "bg-[var(--color-surface-2)] text-ink/70 border border-[var(--color-line)]";
  return (
    <span
      className={`inline-flex items-center rounded-chip px-2 py-0.5 text-[10px] font-semibold leading-none ${skin} ${className}`}
    >
      {children}
    </span>
  );
}
