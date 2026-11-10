import Link from "next/link";

export const metadata = { robots: { index: false, follow: false } };  // 実験頁=非索引

/** ナビ見本ラボ(/nav-lab): ヘッダーのアイコン大きさ×間隔×ラベル有無を 30種 並べて選ぶ用。
 *  レイアウトは「🏠ホーム左固定 / 残り右寄せ + ≡メニュー」で固定。 本番反映はしない見本。 */

const RIGHT = [
  ["📋", "一覧"],
  ["🔍", "検索"],
  ["📝", "AI書評"],
  ["🕘", "過去ログ"],
  ["🔰", "使い方"],
] as const;

const ICON_SIZES = [16, 18, 20, 22, 24] as const;
const GAPS = [
  { px: 10, name: "狭" },
  { px: 16, name: "中" },
  { px: 22, name: "広" },
] as const;
const LABELS = [true, false] as const;

function NavBar({
  iconPx,
  gapPx,
  showLabel,
}: {
  iconPx: number;
  gapPx: number;
  showLabel: boolean;
}) {
  const cell = "flex flex-col items-center gap-0.5";
  const labelPx = 9;
  return (
    <div className="flex items-center border-b border-[var(--color-line)] bg-[var(--color-surface)] px-3 py-1.5">
      <span className={cell} aria-label="ホーム">
        <span style={{ fontSize: iconPx, lineHeight: 1 }}>🏠</span>
        {showLabel && (
          <span style={{ fontSize: labelPx }} className="text-ink/55">
            ホーム
          </span>
        )}
      </span>
      <div className="ml-auto flex items-center" style={{ gap: gapPx }}>
        {RIGHT.map(([icon, label]) => (
          <span key={label} className={cell}>
            <span style={{ fontSize: iconPx, lineHeight: 1 }}>{icon}</span>
            {showLabel && (
              <span style={{ fontSize: labelPx }} className="text-ink/55">
                {label}
              </span>
            )}
          </span>
        ))}
        <span className={`${cell} opacity-70`} aria-label="メニュー">
          <span style={{ fontSize: iconPx, lineHeight: 1 }}>≡</span>
          {showLabel && (
            <span style={{ fontSize: labelPx }} className="text-ink/55">
              メニュー
            </span>
          )}
        </span>
      </div>
    </div>
  );
}

export default function NavLabPage() {
  const variants: Array<{
    n: number;
    iconPx: number;
    gap: (typeof GAPS)[number];
    showLabel: boolean;
  }> = [];
  let n = 0;
  for (const showLabel of LABELS) {
    for (const iconPx of ICON_SIZES) {
      for (const gap of GAPS) {
        n += 1;
        variants.push({ n, iconPx, gap, showLabel });
      }
    }
  }

  return (
    <div className="min-h-screen bg-[var(--color-bg)] px-3 py-5 pb-20">
      <div className="mx-auto max-w-md">
        <Link href="/" className="text-[12px] text-[var(--color-accent)]">
          ← ホーム
        </Link>
        <h1 className="mt-2 text-[20px] font-black">ナビ見本ラボ</h1>
        <p className="mt-1 text-[12px] leading-relaxed text-ink/65">
          アイコンの大きさ×間隔×ラベル有無を {variants.length} 種。
          レイアウトは「🏠ホーム左・残り右寄せ＋≡メニュー」固定。
          気に入った番号を教えてください（例: 「#14」）。
        </p>

        <ul className="mt-5 space-y-4">
          {variants.map((v) => (
            <li
              key={v.n}
              className="overflow-hidden rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] shadow-sm"
            >
              <div className="flex items-center justify-between bg-[var(--color-surface-2)] px-3 py-1.5">
                <span className="text-[12px] font-bold tabular-nums">
                  #{String(v.n).padStart(2, "0")}
                </span>
                <span className="text-[10px] text-ink/55">
                  アイコン {v.iconPx}px ・ 間隔 {v.gap.name}({v.gap.px}px) ・
                  ラベル{v.showLabel ? "有" : "無"}
                </span>
              </div>
              <NavBar iconPx={v.iconPx} gapPx={v.gap.px} showLabel={v.showLabel} />
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
