/* タブ #5(高さ2.1rem)ベース・横間隔(gap)検証 — /tab-design。
   高さ・文字組みは固定。 タブ間の間隔を詰めて隣が触れるまで段階表示。最後は連結セグメント版。
   中央「新装版」を選択中(橙塗り)表示。 */
import type { CSSProperties } from "react";

export const metadata = { robots: { index: false, follow: false } };  // 実験頁=非索引

type T = { name: string; year: string; full: boolean };
const TABS: T[] = [
  { name: "初版", year: "1980", full: false },
  { name: "新装版", year: "2006", full: true },
  { name: "復刻BOX", year: "2022", full: true },
];
const ACT = 1;
const RT = "rounded-[var(--radius-tag)]";
const W = "var(--color-accent-warm)";
const H = "2.1rem";
const PY = "0.15rem";

function Cell({ t, a, rounded = true }: { t: T; a: boolean; rounded?: boolean }) {
  const style: CSSProperties = { minHeight: H, paddingTop: PY, paddingBottom: PY };
  if (a) {
    style.background = W;
    style.borderColor = W;
    style.color = "#fff";
  }
  return (
    <div
      className={`relative flex items-center justify-center overflow-hidden border px-2 ${rounded ? RT : ""} ${
        a ? "shadow-soft" : "border-[var(--color-line)] bg-[var(--color-surface-2)] text-ink/70"
      }`}
      style={style}
    >
      <span className="text-[18px] font-black leading-none">{t.name}</span>
      <span className={`absolute bottom-0.5 right-1.5 text-[7px] tabular-nums ${a ? "text-white/70" : "opacity-40"}`}>
        {t.year}
      </span>
      {!t.full && (
        <span className="absolute left-1 top-0.5 text-[7px]" style={{ color: a ? "rgba(255,255,255,0.85)" : "var(--color-accent)" }}>
          一部
        </span>
      )}
    </div>
  );
}

const GAPS = ["0.5rem", "0.375rem", "0.25rem", "0.125rem", "0.0625rem", "0rem"];

export default function TabDesignPage() {
  return (
    <div className="mx-auto max-w-md px-4 py-6">
      <h1 className="text-lg font-bold">#5 横間隔 検証(下ほど密)</h1>
      <p className="mt-1 text-xs text-ink/55">
        高さ・文字は固定。下にいくほどタブ間隔が狭く=横幅が広がり隣が触れる。好みの番号を。
      </p>
      <div className="mt-5 space-y-5">
        {GAPS.map((g, i) => (
          <div key={g}>
            <div className="mb-1.5 text-xs font-semibold text-ink/70">
              #{i + 1} 間隔 {g === "0rem" ? "0(接触)" : g}
            </div>
            <div className="grid grid-cols-3" style={{ gap: g }}>
              {TABS.map((t, idx) => (
                <Cell key={t.name} t={t} a={idx === ACT} />
              ))}
            </div>
          </div>
        ))}

        {/* 連結セグメント版(境界共有・外側だけ角丸) */}
        <div>
          <div className="mb-1.5 text-xs font-semibold text-ink/70">#7 連結セグメント(枠共有・接触)</div>
          <div className={`grid grid-cols-3 overflow-hidden border border-[var(--color-line)] ${RT}`}>
            {TABS.map((t, idx) => {
              const a = idx === ACT;
              const style: CSSProperties = { minHeight: H, paddingTop: PY, paddingBottom: PY };
              if (a) {
                style.background = W;
                style.color = "#fff";
              }
              return (
                <div
                  key={t.name}
                  className={`relative flex items-center justify-center px-2 ${idx > 0 ? "border-l border-[var(--color-line)]" : ""} ${a ? "" : "bg-[var(--color-surface-2)] text-ink/70"}`}
                  style={style}
                >
                  <span className="text-[18px] font-black leading-none">{t.name}</span>
                  <span className={`absolute bottom-0.5 right-1.5 text-[7px] tabular-nums ${a ? "text-white/70" : "opacity-40"}`}>
                    {t.year}
                  </span>
                  {!t.full && (
                    <span className="absolute left-1 top-0.5 text-[7px]" style={{ color: a ? "rgba(255,255,255,0.85)" : "var(--color-accent)" }}>
                      一部
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
