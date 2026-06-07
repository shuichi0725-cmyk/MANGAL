/* タブ デザイン案(文字組み重視) — /tab-design。中央「新装版」を選択中表示。
   色でなく ★文字配置/フォント/レイアウト を変えた30案。 */
import type { ReactNode } from "react";

type T = { name: string; year: string; full: boolean };
const TABS: T[] = [
  { name: "初版", year: "1980", full: false },
  { name: "新装版", year: "2006", full: true },
  { name: "復刻BOX", year: "2022", full: true },
];
const ACT = 1;
const RT = "rounded-[var(--radius-tag)]";

/** 共通の枠(色は控えめ=文字組みを主役に)。選択中は橙の淡い地+枠。 */
function Box({ active, children, cls = "" }: { active: boolean; children: ReactNode; cls?: string }) {
  return (
    <div
      className={`flex min-h-[3.4rem] flex-col items-center justify-center overflow-hidden ${RT} border px-2 py-1.5 ${
        active
          ? "border-[var(--color-accent-warm)] bg-[var(--color-accent-warm)]/10 text-ink"
          : "border-[var(--color-line)] bg-[var(--color-surface-2)] text-ink/70"
      } ${cls}`}
    >
      {children}
    </div>
  );
}
function Row({ render }: { render: (t: T, active: boolean) => ReactNode }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      {TABS.map((t, i) => render(t, i === ACT))}
    </div>
  );
}
const yr = (t: T) => `${t.year}${!t.full ? " ·一部" : ""}`;

const V: { id: number; name: string; node: ReactNode }[] = [
  { id: 1, name: "明朝・大名/小年", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="font-serif text-[15px] font-semibold leading-none">{t.name}</span><span className="mt-1 font-serif text-[10px] opacity-60">{yr(t)}</span></Box>} /> },
  { id: 2, name: "レタースペース名", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="text-[13px] font-semibold tracking-[0.35em] leading-none indent-[0.35em]">{t.name}</span><span className="mt-1 text-[10px] tracking-widest opacity-55">{yr(t)}</span></Box>} /> },
  { id: 3, name: "年を上付き", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="text-[14px] font-semibold leading-none">{t.name}<sup className="ml-0.5 text-[9px] font-normal opacity-60">{t.year}</sup></span>{!t.full && <span className="mt-1 text-[9px] opacity-50">一部</span>}</Box>} /> },
  { id: 4, name: "年大・名キャプション", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="text-[9px] tracking-wide opacity-55 leading-none">{t.name}</span><span className="mt-0.5 text-[17px] font-bold tabular-nums leading-none">{t.year}</span></Box>} /> },
  { id: 5, name: "縦区切り線", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="flex items-center gap-1.5"><span className="text-[13px] font-semibold leading-none">{t.name}</span><span className="h-3 w-px bg-current opacity-25" /><span className="text-[10px] tabular-nums opacity-60">{t.year}</span></span>{!t.full && <span className="mt-0.5 text-[9px] opacity-45">一部</span>}</Box>} /> },
  { id: 6, name: "年を縦書き添え", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="flex items-center gap-1"><span className="text-[13px] font-semibold leading-tight">{t.name}</span><span className="text-[8px] tabular-nums opacity-55 [writing-mode:vertical-rl] leading-none">{t.year}</span></span></Box>} /> },
  { id: 7, name: "明朝・中央太・ゆったり", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="font-serif text-[14px] font-bold tracking-[0.15em] leading-none">{t.name}</span><span className="mt-1.5 font-serif text-[9px] tracking-[0.2em] opacity-55">{yr(t)}</span></Box>} /> },
  { id: 8, name: "二重ウェイト名", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="text-[14px] leading-none"><span className="font-extrabold">{t.name.slice(0, 2)}</span><span className="font-light">{t.name.slice(2)}</span></span><span className="mt-1 text-[10px] opacity-55">{yr(t)}</span></Box>} /> },
  { id: 9, name: "透かし年(背景大)", node: <Row render={(t, a) => <Box key={t.name} active={a} cls="relative"><span className="pointer-events-none absolute inset-0 flex items-center justify-center text-[26px] font-black tabular-nums opacity-[0.08] leading-none">{t.year}</span><span className="relative text-[13px] font-bold leading-none">{t.name}</span>{!t.full && <span className="relative mt-0.5 text-[9px] opacity-50">一部</span>}</Box>} /> },
  { id: 10, name: "右寄せ年(横並び)", node: <Row render={(t, a) => <Box key={t.name} active={a} cls="!items-stretch !justify-center"><span className="flex w-full items-baseline justify-between"><span className="text-[13px] font-semibold leading-none">{t.name}</span><span className="text-[9px] tabular-nums opacity-50">{t.year}</span></span></Box>} /> },
  { id: 11, name: "印(seal)風", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="flex items-center gap-1"><span className={`grid h-4 w-4 place-items-center rounded-[3px] text-[8px] font-bold ${a ? "bg-[var(--color-accent-warm)] text-white" : "bg-ink/15"}`}>{t.name.slice(0, 1)}</span><span className="text-[12px] font-semibold leading-none">{t.name.slice(1)}</span></span><span className="mt-1 text-[9px] tabular-nums opacity-55">{yr(t)}</span></Box>} /> },
  { id: 12, name: "等幅年・ゴシック太", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="text-[13px] font-bold leading-none">{t.name}</span><span className="mt-1 font-mono text-[10px] tabular-nums tracking-tight opacity-60">{t.year}{!t.full && " *"}</span></Box>} /> },
  { id: 13, name: "雑誌マストヘッド", node: <Row render={(t, a) => <Box key={t.name} active={a} cls="!items-stretch"><span className="text-center text-[13px] font-extrabold leading-none">{t.name}</span><span className={`my-0.5 h-px w-full ${a ? "bg-[var(--color-accent-warm)]" : "bg-ink/15"}`} /><span className="text-center text-[9px] tabular-nums opacity-55">{yr(t)}</span></Box>} /> },
  { id: 14, name: "ローマ字併記", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="text-[13px] font-semibold leading-none">{t.name}</span><span className="mt-1 text-[8px] uppercase tracking-[0.15em] opacity-50">{t.year}</span></Box>} /> },
  { id: 15, name: "「刊」付き和", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="font-serif text-[14px] font-semibold leading-none">{t.name}</span><span className="mt-1 font-serif text-[9px] opacity-55">{t.year}<span className="ml-px opacity-70">刊</span></span></Box>} /> },
  { id: 16, name: "condensed詰め", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="text-[14px] font-bold tracking-tighter leading-none">{t.name}</span><span className="mt-1 text-[10px] tabular-nums tracking-tighter opacity-55">{yr(t)}</span></Box>} /> },
  { id: 17, name: "年を右上コーナー", node: <Row render={(t, a) => <Box key={t.name} active={a} cls="relative !justify-center"><span className="absolute right-1 top-0.5 text-[8px] tabular-nums opacity-45">{t.year}</span><span className="text-[14px] font-bold leading-none">{t.name}</span>{!t.full && <span className="mt-0.5 text-[8px] opacity-45">一部</span>}</Box>} /> },
  { id: 18, name: "明朝名+ゴシック年", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="font-serif text-[15px] font-semibold leading-none">{t.name}</span><span className="mt-1 font-sans text-[9px] font-medium tabular-nums opacity-55">{yr(t)}</span></Box>} /> },
  { id: 19, name: "下線キャプション年", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="text-[13px] font-semibold leading-none">{t.name}</span><span className={`mt-1 border-b text-[9px] tabular-nums leading-tight ${a ? "border-[var(--color-accent-warm)] opacity-80" : "border-transparent opacity-50"}`}>{yr(t)}</span></Box>} /> },
  { id: 20, name: "ゆったり行間・中央", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="text-[13px] font-medium tracking-[0.1em] leading-loose">{t.name}</span><span className="text-[9px] tracking-[0.1em] opacity-50">{yr(t)}</span></Box>} /> },
  { id: 21, name: "括弧年・1行明朝", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="font-serif text-[13px] font-semibold leading-tight">{t.name}<span className="ml-0.5 text-[9px] font-normal opacity-55">（{t.year}）</span></span>{!t.full && <span className="mt-0.5 text-[8px] opacity-45">一部</span>}</Box>} /> },
  { id: 22, name: "年ヒーロー大+名上小", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="text-[8px] font-medium tracking-[0.2em] opacity-55 leading-none">{t.name}</span><span className="mt-0.5 text-[19px] font-black tabular-nums leading-none">{t.year}</span>{!t.full && <span className="text-[7px] opacity-45">一部</span>}</Box>} /> },
  { id: 23, name: "二言語(英ラベル)", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="text-[13px] font-bold leading-none">{t.name}</span><span className="mt-0.5 text-[7px] uppercase tracking-[0.2em] opacity-45">{t.name === "初版" ? "1st" : t.name === "新装版" ? "Reissue" : "Repro"}・{t.year}</span></Box>} /> },
  { id: 24, name: "名のみ大(年は淡点)", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="text-[15px] font-bold tracking-wide leading-none">{t.name}</span><span className="mt-1 flex items-center gap-1 text-[8px] tabular-nums opacity-45"><span className={`inline-block h-1 w-1 rounded-full ${t.full ? "bg-current" : "bg-[var(--color-accent)]"}`} />{t.year}</span></Box>} /> },
  { id: 25, name: "全角風・大字間", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="text-[13px] font-semibold tracking-[0.5em] indent-[0.5em] leading-none">{t.name}</span><span className="mt-1 text-[9px] tracking-[0.3em] indent-[0.3em] opacity-55">{t.year}</span></Box>} /> },
  { id: 26, name: "縦書き名(明朝)", node: <Row render={(t, a) => <Box key={t.name} active={a} cls="!flex-row !items-center gap-1"><span className="font-serif text-[12px] font-bold [writing-mode:vertical-rl] leading-none">{t.name}</span><span className="text-[8px] tabular-nums opacity-50">{t.year}</span></Box>} /> },
  { id: 27, name: "名+丸年バッジ", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="text-[13px] font-bold leading-none">{t.name}</span><span className={`mt-1 rounded-full px-1.5 py-px text-[8px] tabular-nums ${a ? "bg-[var(--color-accent-warm)] text-white" : "bg-ink/10 opacity-70"}`}>{t.year}</span></Box>} /> },
  { id: 28, name: "極太+年薄右下", node: <Row render={(t, a) => <Box key={t.name} active={a} cls="relative !justify-center"><span className="text-[15px] font-black leading-none">{t.name}</span><span className="absolute bottom-0.5 right-1 text-[8px] tabular-nums opacity-35">{t.year}</span></Box>} /> },
  { id: 29, name: "年='06 略記", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="text-[13px] font-semibold leading-none">{t.name}</span><span className="mt-1 text-[10px] tabular-nums opacity-55">&apos;{t.year.slice(2)}{!t.full && " 一部"}</span></Box>} /> },
  { id: 30, name: "名→年 区切り中黒", node: <Row render={(t, a) => <Box key={t.name} active={a}><span className="text-center text-[12px] leading-tight"><span className="font-bold">{t.name}</span><span className="mx-1 opacity-30">·</span><span className="text-[10px] tabular-nums opacity-55">{t.year}</span></span>{!t.full && <span className="text-[8px] opacity-45">一部</span>}</Box>} /> },
];

export default function TabDesignPage() {
  return (
    <div className="mx-auto max-w-md px-4 py-6">
      <h1 className="text-lg font-bold">タブ デザイン案 30(文字組み)</h1>
      <p className="mt-1 text-xs text-ink/55">
        色でなく文字の組み方/フォント/配置を変えた案。中央「新装版」を選択中表示。気に入った番号を。
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
