/**
 * 作品頁の「同ジャンル検索」の右に置く、羅針盤へのマーク(2026-09-30 ユーザ指示・2026-10-03 本番化)。
 * この作品を真ん中にして羅針盤を開く = /compass?from=<slug>。
 * ★頁を丸ごと読み直す <a>(next/link にしない): テスト環境の羅針盤は索引の読み先を本番の全件(/prod-idx)に変えるため、
 *   サイト内遷移で入るとテスト環境の抜粋の索引を持ち込む(components/GlobalNav.tsx と同じ理由)。 本番では害は無い。
 *   見た目は style で持つ(Tailwind の新しいクラスを足さない)。
 */
export default function CompassLink({ slug, title }: { slug: string; title: string }) {
  return (
    <a
      href={`/compass?from=${encodeURIComponent(slug)}`}
      aria-label={`${title}から羅針盤で旅をする`}
      title="羅針盤でこの作品から旅をする"
      className="spring-press inline-flex items-center"
      style={{
        marginLeft: 8,
        padding: "5px 9px",
        border: "2px solid var(--color-accent)",
        borderRadius: "var(--radius-tag)",
        color: "var(--color-accent)",
        verticalAlign: "middle",
      }}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true" width={18} height={18} style={{ stroke: "currentColor", fill: "none", strokeWidth: 1.9 }}>
        <circle cx={12} cy={12} r={8.5} />
        <path d="M15.5 8.5l-2 5-5 2 2-5z" />
      </svg>
    </a>
  );
}
