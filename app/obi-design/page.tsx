/* キャッチコピー帯のデザイン比較 — /obi-design。
   縦線色 6 × 背景 5 = 30案。 文面・文字組みは本番カードと同一(text-xs font-medium leading-snug line-clamp-3)。
   番号で選んでもらう用。 ミニカード文脈(タイトル+著者行)付き。 */

const CATCH = "鬼ごっこに負けて宇宙人の押しかけ女房がやってきた。すべてのラブコメの原点、ここに在り。";

type Line = { name: string; color: string };
type Bg = { name: string; bg: (line: string) => string };

const LINES: Line[] = [
  { name: "赤(現行)", color: "#d23f3f" },
  { name: "橙", color: "#e0892e" },
  { name: "青", color: "#2f74d0" },
  { name: "緑", color: "#2e8b57" },
  { name: "紫", color: "#7c5cbf" },
  { name: "墨", color: "#0f1115" },
];

const BGS: Bg[] = [
  { name: "クリーム(現行)", bg: () => "#f0ede4" },
  { name: "白+細枠", bg: () => "#ffffff" },
  { name: "濃クリーム", bg: () => "#e9e4d4" },
  { name: "線色の超淡", bg: (line) => line + "14" }, // 線色の8%
  { name: "薄墨", bg: () => "rgba(15,17,21,0.05)" },
];

function Obi({ n, line, bg }: { n: number; line: Line; bg: Bg }) {
  const background = bg.bg(line.color);
  const isWhite = bg.name === "白+細枠";
  return (
    <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3">
      <div className="flex items-baseline gap-2">
        <span className="text-[11px] font-black tabular-nums text-ink/40 shrink-0">#{n}</span>
        <p className="font-bold text-base leading-tight">うる星やつら</p>
        <span className="ml-auto text-[10px] text-ink/40 shrink-0">
          {line.name} × {bg.name}
        </span>
      </div>
      <p className="text-xs text-ink/65 mt-1 line-clamp-1">
        高橋留美子<span className="text-ink/45">　1978〜1987 完結</span>
      </p>
      <p
        className="text-xs text-ink/75 font-medium leading-snug mt-1 line-clamp-3 rounded-r-md px-2 py-1"
        style={{
          borderLeft: `2px solid ${line.color}`,
          background,
          ...(isWhite ? { outline: "1px solid rgba(15,17,21,0.08)" } : {}),
        }}
      >
        {CATCH}
      </p>
    </div>
  );
}

export default function ObiDesignPage() {
  let n = 0;
  return (
    <main className="mx-auto max-w-md px-4 py-6 space-y-6">
      <h1 className="text-xl font-bold">キャッチコピー帯 30案</h1>
      <p className="text-xs text-ink/60">
        縦線6色 × 背景5種。番号でご指定ください。文面・文字サイズは本番カードと同一。
      </p>
      {LINES.map((line) => (
        <section key={line.name} className="space-y-2">
          <h2 className="text-sm font-bold text-ink/70">
            縦線: {line.name} <span className="font-normal text-ink/40">{line.color}</span>
          </h2>
          {BGS.map((bg) => {
            n += 1;
            return <Obi key={bg.name} n={n} line={line} bg={bg} />;
          })}
        </section>
      ))}
    </main>
  );
}
