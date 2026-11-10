import Link from "next/link";

export const metadata = { robots: { index: false, follow: false } };  // 実験頁=非索引

/** ナビ見本ラボ2(/nav-pack): #1(アイコン16px・ラベル有)ベースで「右側の詰め方」だけを振る。
 *  ≡メニューは右端で固定(位置を変えない)。 変えるのは 5項目の間隔 / メニューとの距離 / 分散か密集か。 */

const ITEMS = [
  ["📋", "一覧"],
  ["🔍", "検索"],
  ["📝", "AI書評"],
  ["🕘", "過去ログ"],
  ["🔰", "使い方"],
] as const;

const ICON = 16;
const LABEL = 9;
const cell = "flex flex-col items-center gap-0.5 shrink-0";

function Cell({ icon, label, dim }: { icon: string; label: string; dim?: boolean }) {
  return (
    <span className={`${cell}${dim ? " opacity-70" : ""}`} aria-label={label}>
      <span style={{ fontSize: ICON, lineHeight: 1 }}>{icon}</span>
      <span style={{ fontSize: LABEL }} className="text-ink/55">
        {label}
      </span>
    </span>
  );
}

function NavBar({
  itemGap,
  menuGap,
  spread,
  divider,
}: {
  itemGap: number;
  menuGap: number;
  spread?: boolean;
  divider?: boolean;
}) {
  const items = ITEMS.map(([icon, label], i) => (
    <span key={label} className="flex items-center" style={{ gap: 0 }}>
      {divider && i > 0 && (
        <span className="mr-2 h-5 w-px bg-[var(--color-line)]" aria-hidden />
      )}
      <Cell icon={icon} label={label} />
    </span>
  ));
  return (
    <div className="flex items-center border-b border-[var(--color-line)] bg-[var(--color-surface)] px-3 py-1.5">
      <Cell icon="🏠" label="ホーム" />
      {spread ? (
        <div className="mx-3 flex flex-1 items-center justify-between">{items}</div>
      ) : (
        <div className="ml-auto flex items-center" style={{ gap: itemGap }}>
          {items}
        </div>
      )}
      {/* ≡ メニュー = 右端固定。 itemsとの距離(menuGap)だけ変える(メニュー自体は動かない) */}
      <span style={{ marginLeft: menuGap }}>
        <Cell icon="≡" label="メニュー" dim />
      </span>
    </div>
  );
}

const VARIANTS: Array<{
  note: string;
  itemGap: number;
  menuGap: number;
  spread?: boolean;
  divider?: boolean;
}> = [
  { note: "密集・右寄せ(間隔6)", itemGap: 6, menuGap: 6 },
  { note: "標準・右寄せ(間隔10)", itemGap: 10, menuGap: 10 },
  { note: "やや緩め・右寄せ(間隔14)", itemGap: 14, menuGap: 14 },
  { note: "ゆったり・右寄せ(間隔20)", itemGap: 20, menuGap: 20 },
  { note: "項目は密(6)・メニュー少し離す(20)", itemGap: 6, menuGap: 20 },
  { note: "項目は密(6)・メニュー大きく離す(36)", itemGap: 6, menuGap: 36 },
  { note: "項目は緩(16)・メニュー密(6)", itemGap: 16, menuGap: 6 },
  { note: "区切り線入り(間隔10)", itemGap: 10, menuGap: 12, divider: true },
  { note: "全幅に分散・メニュー右端(近12)", itemGap: 0, menuGap: 12, spread: true },
  { note: "全幅に分散・メニュー右端(離28)", itemGap: 0, menuGap: 28, spread: true },
];

export default function NavPackPage() {
  return (
    <div className="min-h-screen bg-[var(--color-bg)] px-3 py-5 pb-20">
      <div className="mx-auto max-w-md">
        <Link href="/" className="text-[12px] text-[var(--color-accent)]">
          ← ホーム
        </Link>
        <h1 className="mt-2 text-[20px] font-black">ナビ見本ラボ2 ・ 右の詰め方</h1>
        <p className="mt-1 text-[12px] leading-relaxed text-ink/65">
          #1(アイコン16px・ラベル有)ベース。 🏠ホーム左固定・≡メニュー右端固定のまま、
          5項目の詰め方だけを {VARIANTS.length} 通り。 気に入った番号を教えてください。
        </p>

        <ul className="mt-5 space-y-4">
          {VARIANTS.map((v, i) => (
            <li
              key={i}
              className="overflow-hidden rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] shadow-sm"
            >
              <div className="flex items-center justify-between bg-[var(--color-surface-2)] px-3 py-1.5">
                <span className="text-[12px] font-bold tabular-nums">
                  #{String(i + 1).padStart(2, "0")}
                </span>
                <span className="text-[10px] text-ink/55">{v.note}</span>
              </div>
              <NavBar
                itemGap={v.itemGap}
                menuGap={v.menuGap}
                spread={v.spread}
                divider={v.divider}
              />
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
