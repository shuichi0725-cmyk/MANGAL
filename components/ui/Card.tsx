import Link from "next/link";

type Props = {
  href?: string;
  className?: string;
  children: React.ReactNode;
};

/**
 * ソフト触感の汎用カード (= 角丸 + 境界 + 柔らかい影、 hover浮き / press沈み)。
 * href があれば Link (= 押せるカード)、 無ければ div。 押せる感の中核プリミティブ。
 * 触感の実体は globals.css の `.tactile`。
 */
export default function Card({ href, className = "", children }: Props) {
  const cls = `tactile rounded-card ${className}`;
  if (href) {
    return (
      <Link href={href} className={`block ${cls}`}>
        {children}
      </Link>
    );
  }
  return <div className={cls}>{children}</div>;
}
