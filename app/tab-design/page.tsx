/* タブ #10 ベース・高さ縮め検証 — /tab-design。
   #10(極太名+隅に年)の縦の高さを段階的に短く。文字が崩れない最短を選定。横/文字組みは固定。
   中央「新装版」を選択中(橙塗り)表示。 */
import type { CSSProperties } from "react";

type T = { name: string; year: string; full: boolean };
const TABS: T[] = [
  { name: "初版", year: "1980", full: false },
  { name: "新装版", year: "2006", full: true },
  { name: "復刻BOX", year: "2022", full: true },
];
const ACT = 1;
const RT = "rounded-[var(--radius-tag)]";
const W = "var(--color-accent-warm)";

function Cell({ t, a, minH, py }: { t: T; a: boolean; minH: string; py: string }) {
  const style: CSSProperties = { minHeight: minH, paddingTop: py, paddingBottom: py };
  if (a) {
    style.background = W;
    style.borderColor = W;
    style.color = "#fff";
  }
  return (
    <div
      className={`relative flex items-center justify-center overflow-hidden ${RT} border px-2 ${
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

// 高さ段階(高→低)。 py も連動して詰める。
const STEPS: { h: string; py: string; note: string }[] = [
  { h: "3.2rem", py: "0.375rem", note: "現#10(基準)" },
  { h: "2.8rem", py: "0.3rem", note: "" },
  { h: "2.5rem", py: "0.25rem", note: "" },
  { h: "2.3rem", py: "0.2rem", note: "" },
  { h: "2.1rem", py: "0.15rem", note: "" },
  { h: "2.0rem", py: "0.125rem", note: "" },
  { h: "1.9rem", py: "0.1rem", note: "" },
  { h: "1.8rem", py: "0.05rem", note: "かなり短い" },
  { h: "1.7rem", py: "0.05rem", note: "限界付近" },
  { h: "1.6rem", py: "0", note: "崩れ確認用(年が名に近い)" },
];

export default function TabDesignPage() {
  return (
    <div className="mx-auto max-w-md px-4 py-6">
      <h1 className="text-lg font-bold">#10 高さ縮め(短いほど下)</h1>
      <p className="mt-1 text-xs text-ink/55">
        上=現#10。下にいくほど縦が短い。文字/年が崩れない範囲で最短の番号を教えてください。
      </p>
      <div className="mt-5 space-y-5">
        {STEPS.map((s, i) => (
          <div key={s.h}>
            <div className="mb-1.5 text-xs font-semibold text-ink/70">
              #{i + 1} 高さ {s.h}
              {s.note && <span className="ml-2 font-normal text-ink/45">{s.note}</span>}
            </div>
            <div className="grid grid-cols-3 gap-2">
              {TABS.map((t, idx) => (
                <Cell key={t.name} t={t} a={idx === ACT} minH={s.h} py={s.py} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
