import Link from "next/link";

type BaseProps = {
  active?: boolean;
  className?: string;
  children: React.ReactNode;
};

/**
 * ソフト触感のピル型チップ (= 淡い塗り + 境界 + 押せる感)。
 * active で accent 塗り + 白字。 button(onClick)と Link(href)の両用。
 * フィルタ条件・カテゴリの両方で再利用する共通プリミティブ。
 */
function chipClass(active: boolean, className: string) {
  const base =
    "inline-flex items-center gap-1 rounded-[var(--radius-tag)] px-3 py-1.5 text-xs font-medium select-none " +
    "transition duration-100 active:scale-[0.94]";
  const skin = active
    ? "bg-[var(--color-accent)] text-white border border-transparent shadow-[var(--shadow-soft)]"
    : "tactile-chip text-ink/80";
  return `${base} ${skin} ${className}`;
}

export function ChipButton({
  active = false,
  onClick,
  className = "",
  children,
}: BaseProps & { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className={chipClass(active, className)}>
      {children}
    </button>
  );
}

export function ChipLink({
  active = false,
  href,
  className = "",
  children,
}: BaseProps & { href: string }) {
  return (
    <Link href={href} className={chipClass(active, className)}>
      {children}
    </Link>
  );
}

/**
 * アウトライン枠タグ (= メタ項目の押せる値: 著者/出版社/連載誌/分野/年)。
 * チップ(淡塗り)とは別系統の「枠線のみ」で、 hover で accent に染まる。 角はわずか丸。
 */
export function TagLink({
  href,
  className = "",
  children,
}: { href: string; className?: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className={
        "inline-flex items-center rounded-[var(--radius-tag)] border border-[var(--color-line)] " +
        "bg-[var(--color-surface)] px-2.5 py-1 text-[13px] font-medium text-ink/85 " +
        "transition duration-100 hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] " +
        "active:scale-[0.94] active:bg-[var(--color-surface-2)] active:border-[var(--color-accent)] " +
        className
      }
    >
      {children}
    </Link>
  );
}
