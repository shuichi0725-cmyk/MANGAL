/* タブ デザイン案ショーケース (一時) — /tab-design で30案を比較。中央=新装版 を選択中として表示。 */
import type { ReactNode } from "react";

type T = { name: string; year: string; full: boolean };
const TABS: T[] = [
  { name: "初版", year: "1980", full: false },
  { name: "新装版", year: "2006", full: true },
  { name: "復刻BOX", year: "2022", full: true },
];
const ACT = 1;

function Two({ t }: { t: T }) {
  return (
    <>
      <span className="text-[13px] font-semibold leading-tight">{t.name}</span>
      <span className="mt-0.5 text-[10px] leading-tight opacity-70">
        {t.year}
        {!t.full && " ·一部"}
      </span>
    </>
  );
}
function One({ t }: { t: T }) {
  return (
    <span className="text-xs font-medium leading-tight">
      {t.name}
      <span className="ml-1 text-[10px] opacity-60">{t.year}</span>
    </span>
  );
}

/** 単純クラス差し替え型(grid-cols-3 均等)。 */
function Grid({
  cont = "grid grid-cols-3 gap-2",
  a,
  i,
  one = false,
}: {
  cont?: string;
  a: string;
  i: string;
  one?: boolean;
}) {
  return (
    <div className={cont}>
      {TABS.map((t, idx) => (
        <button
          key={t.name}
          className={`flex w-full flex-col items-center justify-center px-2 py-1.5 transition ${
            idx === ACT ? a : i
          }`}
        >
          {one ? <One t={t} /> : <Two t={t} />}
        </button>
      ))}
    </div>
  );
}

const TAG = "rounded-[var(--radius-tag)]";

// ---- 30 案 ----
const VARIANTS: { id: number; name: string; node: ReactNode }[] = [
  { id: 1, name: "オレンジ塗り(現行)", node: <Grid a={`${TAG} bg-[var(--color-accent-warm)] text-white border border-[var(--color-accent-warm)] shadow-soft`} i={`${TAG} bg-[var(--color-surface-2)] border border-[var(--color-line)] text-ink/75`} /> },
  { id: 2, name: "赤(ブランド)塗り", node: <Grid a={`${TAG} bg-[var(--color-accent)] text-white border border-[var(--color-accent)] shadow-soft`} i={`${TAG} bg-[var(--color-surface-2)] border border-[var(--color-line)] text-ink/75`} /> },
  { id: 3, name: "下線(アンダーライン)", node: <Grid cont="grid grid-cols-3" a="border-b-2 border-[var(--color-accent-warm)] text-ink font-semibold" i="border-b-2 border-transparent text-ink/45" /> },
  { id: 4, name: "下線・赤", node: <Grid cont="grid grid-cols-3" a="border-b-2 border-[var(--color-accent)] text-ink font-semibold" i="border-b-2 border-transparent text-ink/45" /> },
  { id: 5, name: "上線アクセント", node: <Grid a={`${TAG} bg-[var(--color-surface)] border-t-2 border-t-[var(--color-accent-warm)] border border-[var(--color-line)] text-ink shadow-soft`} i={`${TAG} bg-[var(--color-surface-2)] border-t-2 border-t-transparent border border-[var(--color-line)] text-ink/55`} /> },
  { id: 6, name: "アウトライン(枠だけ)", node: <Grid a={`${TAG} border-2 border-[var(--color-accent-warm)] text-[var(--color-accent-warm)] font-semibold bg-transparent`} i={`${TAG} border border-[var(--color-line)] text-ink/55 bg-transparent`} /> },
  { id: 7, name: "セグメント(連結)", node: <div className="grid grid-cols-3 rounded-[var(--radius-tag)] border border-[var(--color-line)] overflow-hidden bg-[var(--color-surface-2)]">{TABS.map((t, idx) => <button key={t.name} className={`flex flex-col items-center justify-center px-2 py-1.5 ${idx > 0 ? "border-l border-[var(--color-line)]" : ""} ${idx === ACT ? "bg-[var(--color-accent-warm)] text-white" : "text-ink/70"}`}><Two t={t} /></button>)}</div> },
  { id: 8, name: "ピル(角丸大)", node: <Grid a="rounded-full bg-[var(--color-accent-warm)] text-white shadow-soft" i="rounded-full bg-[var(--color-surface-2)] border border-[var(--color-line)] text-ink/70" /> },
  { id: 9, name: "ドット標", node: <Grid a={`${TAG} bg-[var(--color-surface)] border border-[var(--color-line)] text-ink font-semibold relative shadow-soft`} i={`${TAG} bg-[var(--color-surface-2)] border border-[var(--color-line)] text-ink/55`} /> },
  { id: 10, name: "二色(名濃/年淡)+赤線", node: <Grid cont="grid grid-cols-3 gap-2" a={`${TAG} bg-[var(--color-surface)] border-b-[3px] border-b-[var(--color-accent)] border border-[var(--color-line)] text-ink shadow-soft`} i={`${TAG} bg-[var(--color-surface-2)] border border-[var(--color-line)] text-ink/55`} /> },
  { id: 11, name: "影持ち浮きカード", node: <Grid a={`${TAG} bg-[var(--color-surface)] border border-[var(--color-accent-warm)] text-ink font-semibold shadow-lift`} i={`${TAG} bg-[var(--color-surface-2)] border border-[var(--color-line)] text-ink/55`} /> },
  { id: 12, name: "反転(濃紺地)", node: <Grid a={`${TAG} bg-ink text-white shadow-soft`} i={`${TAG} bg-[var(--color-surface-2)] border border-[var(--color-line)] text-ink/60`} /> },
  { id: 13, name: "グラデ(橙→赤)", node: <Grid a={`${TAG} text-white shadow-soft bg-gradient-to-r from-[var(--color-accent-warm)] to-[var(--color-accent)]`} i={`${TAG} bg-[var(--color-surface-2)] border border-[var(--color-line)] text-ink/70`} /> },
  { id: 14, name: "モノクロ(黒白)", node: <Grid a={`${TAG} bg-ink text-white`} i={`${TAG} bg-transparent border border-ink/20 text-ink/55`} /> },
  { id: 15, name: "薄橙地+橙文字", node: <Grid a={`${TAG} bg-[var(--color-accent-warm)]/15 border border-[var(--color-accent-warm)] text-[var(--color-accent-warm)] font-semibold`} i={`${TAG} bg-[var(--color-surface-2)] border border-[var(--color-line)] text-ink/55`} /> },
  { id: 16, name: "左アクセントバー", node: <Grid a={`${TAG} bg-[var(--color-surface)] border border-[var(--color-line)] border-l-[3px] border-l-[var(--color-accent-warm)] text-ink font-semibold shadow-soft`} i={`${TAG} bg-[var(--color-surface-2)] border border-[var(--color-line)] border-l-[3px] border-l-transparent text-ink/55`} /> },
  { id: 17, name: "1行コンパクト橙", node: <Grid one a={`${TAG} bg-[var(--color-accent-warm)] text-white shadow-soft`} i={`${TAG} bg-[var(--color-surface-2)] border border-[var(--color-line)] text-ink/70`} /> },
  { id: 18, name: "1行下線", node: <Grid one cont="grid grid-cols-3" a="border-b-2 border-[var(--color-accent-warm)] text-ink font-semibold" i="border-b-2 border-transparent text-ink/45" /> },
  { id: 19, name: "太枠橙(地白)", node: <Grid a={`${TAG} bg-white border-2 border-[var(--color-accent-warm)] text-ink font-bold`} i={`${TAG} bg-[var(--color-surface-2)] border-2 border-transparent text-ink/55`} /> },
  { id: 20, name: "下太バー(チャンク)", node: <Grid cont="grid grid-cols-3 gap-1.5" a="rounded-t-[var(--radius-tag)] bg-[var(--color-surface)] text-ink font-semibold border-b-4 border-b-[var(--color-accent-warm)] shadow-soft" i="rounded-t-[var(--radius-tag)] bg-[var(--color-surface-2)] text-ink/50 border-b-4 border-b-[var(--color-line)]" /> },
  { id: 21, name: "落ち着いた青", node: <Grid a={`${TAG} bg-[#2f74d0] text-white shadow-soft`} i={`${TAG} bg-[var(--color-surface-2)] border border-[var(--color-line)] text-ink/70`} /> },
  { id: 22, name: "緑(在庫=緑連想)", node: <Grid a={`${TAG} bg-[#2e9e6b] text-white shadow-soft`} i={`${TAG} bg-[var(--color-surface-2)] border border-[var(--color-line)] text-ink/70`} /> },
  { id: 23, name: "年を小チップに", node: <div className="grid grid-cols-3 gap-2">{TABS.map((t, idx) => <button key={t.name} className={`flex w-full items-center justify-center gap-1.5 ${TAG} px-2 py-1.5 ${idx === ACT ? "bg-[var(--color-accent-warm)] text-white shadow-soft" : "bg-[var(--color-surface-2)] border border-[var(--color-line)] text-ink/70"}`}><span className="text-[13px] font-semibold">{t.name}</span><span className={`rounded px-1 text-[9px] ${idx === ACT ? "bg-white/25" : "bg-ink/10"}`}>{t.year}</span></button>)}</div> },
  { id: 24, name: "極細枠+影なし", node: <Grid a={`${TAG} bg-[var(--color-accent-warm)] text-white`} i={`${TAG} bg-transparent border border-[var(--color-line)] text-ink/55`} /> },
  { id: 25, name: "下線2本(太+細)", node: <Grid cont="grid grid-cols-3" a="pb-1 border-b-[3px] border-[var(--color-accent-warm)] text-ink font-bold" i="pb-1 border-b border-[var(--color-line)] text-ink/40" /> },
  { id: 26, name: "角丸0(直角)橙", node: <Grid a="rounded-none bg-[var(--color-accent-warm)] text-white shadow-soft" i="rounded-none bg-[var(--color-surface-2)] border border-[var(--color-line)] text-ink/70" /> },
  { id: 27, name: "和紙風(温色地)", node: <Grid a={`${TAG} bg-[#f3e4cf] border border-[var(--color-accent-warm)] text-[#8a5a1e] font-semibold shadow-soft`} i={`${TAG} bg-[var(--color-surface-2)] border border-[var(--color-line)] text-ink/55`} /> },
  { id: 28, name: "選択のみ拡大強調", node: <div className="grid grid-cols-3 gap-2 items-center">{TABS.map((t, idx) => <button key={t.name} className={`flex w-full flex-col items-center justify-center ${TAG} px-2 py-1.5 transition ${idx === ACT ? "bg-[var(--color-accent-warm)] text-white shadow-lift scale-105" : "bg-[var(--color-surface-2)] border border-[var(--color-line)] text-ink/60"}`}><Two t={t} /></button>)}</div> },
  { id: 29, name: "ゴースト(地なし+橙文字)", node: <Grid a="text-[var(--color-accent-warm)] font-bold underline underline-offset-4 decoration-2" i="text-ink/45" /> },
  { id: 30, name: "ツートン地(上濃下淡)", node: <div className="grid grid-cols-3 gap-2">{TABS.map((t, idx) => <button key={t.name} className={`flex w-full flex-col items-stretch overflow-hidden ${TAG} border ${idx === ACT ? "border-[var(--color-accent-warm)] shadow-soft" : "border-[var(--color-line)]"}`}><span className={`py-1 text-[13px] font-semibold ${idx === ACT ? "bg-[var(--color-accent-warm)] text-white" : "bg-[var(--color-surface-2)] text-ink/70"}`}>{t.name}</span><span className={`py-0.5 text-[10px] ${idx === ACT ? "bg-[var(--color-accent-warm)]/15 text-ink/70" : "bg-[var(--color-surface)] text-ink/45"}`}>{t.year}{!t.full && " ·一部"}</span></button>)}</div> },
];

export default function TabDesignPage() {
  return (
    <div className="mx-auto max-w-md px-4 py-6">
      <h1 className="text-lg font-bold">タブ デザイン案 30</h1>
      <p className="mt-1 text-xs text-ink/55">
        中央「新装版」を選択中として表示。 気に入った番号を教えてください。
      </p>
      <div className="mt-5 space-y-6">
        {VARIANTS.map((v) => (
          <div key={v.id}>
            <div className="mb-1.5 text-xs font-semibold text-ink/70">
              #{v.id} {v.name}
            </div>
            {v.node}
          </div>
        ))}
      </div>
    </div>
  );
}
