/** カテゴリのモノクロSVG線画(2026-08-12 D3トライアル)。ホーム(案12)と同じ絵柄を
 *  /browse のカテゴリカード(CategoryHub/BrowseShell)にも配る共有部品。
 *  ★表示切替はCSSのみ: 絵文字とSVGを両方描き、.theme-d3 の時だけSVGを見せる
 *  (client/server両対応・env不要・ライトテーマ=絵文字のまま画素同一)。 */

const PATHS: Record<string, { d: string; circle?: [number, number, number] }> = {
  anime: { d: "M7 5v14M17 5v14M3 9h4M3 15h4M17 9h4M17 15h4M3 5h18v14H3z" },
  done: { d: "M4 4h16v16H4zM8 12l3 3 5-6" },
  ongoing: { d: "M12 6c-2-1.6-5-1.6-8-.6V19c3-1 6-1 8 .6 2-1.6 5-1.6 8-.6V5.4c-3-1-6-1-8 .6zM12 6v14" },
  kodomo: { d: "M6.5 20c.6-4 3-6 5.5-6s4.9 2 5.5 6M9 5.5C10 4.5 11 4 12 4s2 .5 3 1.5", circle: [12, 9, 3.4] },
  shounen: { d: "M5.5 20c.8-4.5 3.4-7 6.5-7s5.7 2.5 6.5 7", circle: [12, 8, 3.6] },
  seinen: { d: "M5.5 20c.8-4.5 3.4-7 6.5-7s5.7 2.5 6.5 7M9 20v-3M15 20v-3", circle: [12, 8, 3.6] },
  shoujo: { d: "M5.5 20c.8-4.5 3.4-7 6.5-7s5.7 2.5 6.5 7M8 6.5C7.4 9 6.8 10.5 6 12M16 6.5c.6 2.5 1.2 4 2 5.5", circle: [12, 8, 3.6] },
  josei: { d: "M5.5 20c.8-4.5 3.4-7 6.5-7s5.7 2.5 6.5 7M8.5 6C7.5 9.5 7 12 6.5 14M15.5 6c1 3.5 1.5 6 2 8", circle: [12, 8, 3.6] },
};

/** ラベル(表示名)→アイコンキー。CategoryHub/BrowseShell双方のラベル表記に対応 */
export function catKeyOf(label: string): string | null {
  if (label.startsWith("アニメ化")) return "anime";
  if (label.startsWith("完結")) return "done";
  if (label.startsWith("連載中")) return "ongoing";
  if (label === "児童") return "kodomo";
  if (label === "少年") return "shounen";
  if (label === "青年") return "seinen";
  if (label === "少女") return "shoujo";
  if (label === "女性") return "josei";
  return null;
}

export default function CatPict({ k, className = "" }: { k: string; className?: string }) {
  const p = PATHS[k];
  if (!p) return null;
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className={`cat-svg mx-auto h-5 w-5 ${className}`}
      style={{ stroke: "var(--color-ink)", fill: "none", strokeWidth: 1.8 }}
    >
      {p.circle && <circle cx={p.circle[0]} cy={p.circle[1]} r={p.circle[2]} />}
      <path d={p.d} />
    </svg>
  );
}
