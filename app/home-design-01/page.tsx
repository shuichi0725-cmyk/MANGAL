import Link from "next/link";
import { bundle, DesignNav, latestDate, volCount, Cover } from "@/lib/homeDesign";

/** 案1: データベース型 — 検索が主役、密度の高いリスト行(IMDb/読書メーター寄り) */
export default function Design01() {
  const { manga, byNew } = bundle();
  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <DesignNav current={1} />
      <header className="border-b border-[var(--color-line)] bg-[var(--color-surface)] px-4 pb-5 pt-6">
        <h1 className="text-xl font-extrabold tracking-tight">
          MANGAL<span className="text-[var(--color-accent)]">.</span>
          <span className="ml-2 align-middle text-xs font-medium text-ink/55">日本の漫画データベース</span>
        </h1>
        <div className="mt-3 flex items-center gap-2 rounded-lg border-2 border-[var(--color-accent)] bg-white px-3 py-2.5 shadow-sm">
          <span className="text-ink/40">🔍</span>
          <span className="text-sm text-ink/45">作品名・著者名・よみがな で検索…</span>
        </div>
        <p className="mt-2.5 text-[11px] text-ink/55">
          収録 <b className="text-ink/80">{manga.length.toLocaleString()}</b> 作品
          ・ <b className="text-ink/80">68,789</b> ページ規模(本番)
          ・ 毎月更新
        </p>
        <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
          {["連載中", "完結", "アニメ化", "全巻5冊以内", "90年代", "ジャンルで探す"].map((t) => (
            <span key={t} className="rounded-full border border-[var(--color-line)] bg-[var(--color-surface-2)] px-2.5 py-1 text-ink/70">
              {t}
            </span>
          ))}
        </div>
      </header>
      <div className="px-4 py-2 text-[11px] text-ink/50 flex justify-between border-b border-[var(--color-line)]">
        <span>発売日が新しい順</span>
        <span>表示 1–40</span>
      </div>
      <ul className="divide-y divide-[var(--color-line)]">
        {byNew.slice(0, 40).map((m, i) => (
          <li key={m.slug}>
            <Link href={`/manga/${m.slug}`} className="flex gap-3 px-4 py-2.5 active:bg-[var(--color-surface-2)]">
              <span className="w-7 shrink-0 pt-1 text-right text-[11px] tabular-nums text-ink/35">{i + 1}</span>
              <div className="w-10 shrink-0">
                <Cover m={m} sizes="40px" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13.5px] font-semibold text-ink">{m.title}</p>
                <p className="truncate text-[11px] text-ink/55">
                  {(m.authors ?? []).map((a) => a.name).join("・")} ・ {m.year_started ?? "—"}年
                </p>
                <p className="text-[11px] text-ink/45">
                  {volCount(m)}巻 {m.status === "completed" ? "完結" : "続刊"} ・ 最新 {latestDate(m)?.slice(0, 7) ?? "—"}
                </p>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
