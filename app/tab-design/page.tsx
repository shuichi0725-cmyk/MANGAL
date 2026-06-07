/* タブ デザイン #28 ブラッシュアップ — /tab-design。
   #28 のDNA(極太名・中央 + 年は小さく隅)を基本に、書体/年配置/選択中表現を変えた案。
   中央「新装版」を選択中表示。 */
import type { ReactNode, CSSProperties } from "react";

type T = { name: string; year: string; full: boolean };
const TABS: T[] = [
  { name: "初版", year: "1980", full: false },
  { name: "新装版", year: "2006", full: true },
  { name: "復刻BOX", year: "2022", full: true },
];
const ACT = 1;
const RT = "rounded-[var(--radius-tag)]";
const W = "var(--color-accent-warm)"; // アニメ化オレンジ

function Row({ render }: { render: (t: T, a: boolean) => ReactNode }) {
  return <div className="grid grid-cols-3 gap-2">{TABS.map((t, i) => render(t, i === ACT))}</div>;
}

/** #28 基本枠。 selKind で選択中の見せ方を変える。 オレンジは inline style(JIT回避)。 */
function Cell({
  t,
  a,
  selKind = "fill",
  serif = false,
  big = "text-[16px]",
  track = "",
  cornerPos = "bottom-0.5 right-1.5",
  yearCls = "",
  child,
}: {
  t: T;
  a: boolean;
  selKind?: "fill" | "underline" | "ring" | "text" | "bar";
  serif?: boolean;
  big?: string;
  track?: string;
  cornerPos?: string;
  yearCls?: string;
  child?: ReactNode;
}) {
  const fill = selKind === "fill" && a;
  // 色は inline style で(動的Tailwindクラスは生成されないため)
  const boxStyle: CSSProperties = {};
  if (fill) {
    boxStyle.background = W;
    boxStyle.borderColor = W;
    boxStyle.color = "#fff";
  } else if (a) {
    boxStyle.borderColor = W;
    if (selKind === "ring") boxStyle.boxShadow = "0 0 0 2px rgba(224,137,46,0.4)";
  }
  const neutral = a
    ? "border bg-[var(--color-surface)] text-ink shadow-soft"
    : "border border-[var(--color-line)] bg-[var(--color-surface-2)] text-ink/70";
  const nameStyle: CSSProperties =
    a && selKind === "text" && !fill ? { color: W } : {};
  return (
    <div
      className={`relative flex min-h-[3.2rem] items-center justify-center overflow-hidden ${RT} px-2 ${neutral}`}
      style={boxStyle}
    >
      {a && selKind === "bar" && <span className="absolute inset-x-0 top-0 h-[3px]" style={{ background: W }} />}
      <span className={`${big} ${serif ? "font-serif" : ""} font-black leading-none ${track}`} style={nameStyle}>
        {t.name}
        {a && selKind === "underline" && (
          <span className="mt-0.5 block h-[2px] w-full" style={{ background: W }} />
        )}
      </span>
      {child ?? (
        <span className={`absolute ${cornerPos} text-[8px] tabular-nums ${fill ? "text-white/70" : "opacity-40"} ${yearCls}`}>
          {t.year}
        </span>
      )}
      {!t.full && (
        <span
          className="absolute left-1 top-0.5 text-[7px]"
          style={{ color: fill ? "rgba(255,255,255,0.85)" : "var(--color-accent)" }}
        >
          一部
        </span>
      )}
    </div>
  );
}

const V: { id: number; name: string; node: ReactNode }[] = [
  { id: 1, name: "基本洗練(塗り橙)", node: <Row render={(t, a) => <Cell key={t.name} t={t} a={a} />} /> },
  { id: 2, name: "明朝ブラック", node: <Row render={(t, a) => <Cell key={t.name} t={t} a={a} serif />} /> },
  { id: 3, name: "選択=橙下線(名は黒)", node: <Row render={(t, a) => <Cell key={t.name} t={t} a={a} selKind="underline" />} /> },
  { id: 4, name: "選択=橙文字(地白)", node: <Row render={(t, a) => <Cell key={t.name} t={t} a={a} selKind="text" />} /> },
  { id: 5, name: "選択=橙リング", node: <Row render={(t, a) => <Cell key={t.name} t={t} a={a} selKind="ring" />} /> },
  { id: 6, name: "選択=上に橙バー", node: <Row render={(t, a) => <Cell key={t.name} t={t} a={a} selKind="bar" />} /> },
  { id: 7, name: "年を右上", node: <Row render={(t, a) => <Cell key={t.name} t={t} a={a} cornerPos="top-0.5 right-1.5" />} /> },
  { id: 8, name: "年を左下", node: <Row render={(t, a) => <Cell key={t.name} t={t} a={a} cornerPos="bottom-0.5 left-1.5" />} /> },
  { id: 9, name: "名に字間(tracking)", node: <Row render={(t, a) => <Cell key={t.name} t={t} a={a} track="tracking-[0.12em]" />} /> },
  { id: 10, name: "超コントラスト(名特大)", node: <Row render={(t, a) => <Cell key={t.name} t={t} a={a} big="text-[18px]" yearCls="!text-[7px]" />} /> },
  { id: 11, name: "年に「刊」", node: <Row render={(t, a) => <Cell key={t.name} t={t} a={a} child={<span className={`absolute bottom-0.5 right-1.5 text-[8px] tabular-nums ${a ? "text-ink/45" : "opacity-40"}`}>{t.year}<span className="opacity-70">刊</span></span>} />} /> },
  { id: 12, name: "年=等幅mono右下", node: <Row render={(t, a) => <Cell key={t.name} t={t} a={a} child={<span className={`absolute bottom-0.5 right-1.5 font-mono text-[8px] tabular-nums tracking-tight ${a ? "text-ink/45" : "opacity-40"}`}>{t.year}</span>} />} /> },
  { id: 13, name: "年=縦書き右端", node: <Row render={(t, a) => <Cell key={t.name} t={t} a={a} child={<span className={`absolute right-0.5 top-1/2 -translate-y-1/2 text-[7px] tabular-nums [writing-mode:vertical-rl] ${a ? "text-ink/40" : "opacity-35"}`}>{t.year}</span>} />} /> },
  { id: 14, name: "年=小pill右下", node: <Row render={(t, a) => <Cell key={t.name} t={t} a={a} child={<span className={`absolute bottom-0.5 right-1 rounded-full px-1 text-[7px] tabular-nums ${a ? "bg-[color:var(--color-accent-warm)]/15 text-ink/55" : "bg-ink/10 opacity-60"}`}>{t.year}</span>} />} /> },
  { id: 15, name: "明朝+橙下線(和)", node: <Row render={(t, a) => <Cell key={t.name} t={t} a={a} serif selKind="underline" />} /> },
  { id: 16, name: "明朝+橙文字", node: <Row render={(t, a) => <Cell key={t.name} t={t} a={a} serif selKind="text" />} /> },
];

export default function TabDesignPage() {
  return (
    <div className="mx-auto max-w-md px-4 py-6">
      <h1 className="text-lg font-bold">#28 ブラッシュアップ 16案</h1>
      <p className="mt-1 text-xs text-ink/55">
        極太名+隅に年 を基本に、書体/年配置/選択表現を変えた案。中央「新装版」選択中。気に入った番号を。
      </p>
      <div className="mt-5 space-y-6">
        {V.map((v) => (
          <div key={v.id}>
            <div className="mb-1.5 text-xs font-semibold text-ink/70">#{v.id} {v.name}</div>
            {v.node}
          </div>
        ))}
      </div>
    </div>
  );
}
