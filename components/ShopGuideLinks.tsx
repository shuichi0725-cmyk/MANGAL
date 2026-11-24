import Link from "next/link";

/**
 * 作品頁の羅針盤マークの右に置く、おすすめの読書端末(/devices)と Amazon のサービス(/service)への入口
 * (2026-11-24 ユーザ指示「羅針盤の右にスペースがある。ここにおすすめハードとサブスクのリンク貼りたい」)。
 * 行き先はどちらも PR 頁(頁側で PR 表記)。 見た目は CompassLink と同じく style で持つ(Tailwind の新クラスを足さない)。
 */
const BTN: React.CSSProperties = {
  marginLeft: 8,
  padding: "4px 8px",
  border: "2px solid color-mix(in srgb, var(--color-ink) 35%, transparent)",
  borderRadius: "var(--radius-tag)",
  color: "var(--color-ink)",
  fontSize: 11.5,
  fontWeight: 700,
  gap: 4,
  verticalAlign: "middle",
};
const ICON: React.CSSProperties = { stroke: "var(--color-accent)", fill: "none", strokeWidth: 1.9 };

export default function ShopGuideLinks() {
  return (
    <>
      <Link href="/devices" title="電子書籍を読むのにおすすめの端末" className="spring-press inline-flex items-center" style={{ ...BTN, marginLeft: 10 }}>
        <svg viewBox="0 0 24 24" aria-hidden="true" width={16} height={16} style={ICON}>
          <path d="M6 3h12v18H6zM10.5 18h3" />
        </svg>
        端末
      </Link>
      <Link href="/service" title="漫画好きのための Amazon サービス" className="spring-press inline-flex items-center" style={BTN}>
        <svg viewBox="0 0 24 24" aria-hidden="true" width={16} height={16} style={ICON}>
          <path d="M3 5h18v12H3zM10 8.5l5 2.5-5 2.5zM8 21h8" />
        </svg>
        サブスク
      </Link>
    </>
  );
}
