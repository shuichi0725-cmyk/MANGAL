import Link from "next/link";
import { jstTodayStr, loadTokushuDay, loadTokushuIndexDays, type TokushuItem } from "@/lib/cornerData";

/** 日替わり特集のサーバー描画版(2026-09-18 新設)。
 *
 *  ★なぜ要るか: `/tokushu` の本体 `TokushuClient` は `useSearchParams`(?d=過去号)を使うので、
 *  静的エクスポートでは **Suspense の fallback がそのまま静的HTMLになる**。その fallback が
 *  「読み込み中…」だったため、配信HTMLは頁固有31字・作品リンク0本の空頁だった
 *  (番人 _check-ssr-content.py が検出。ブラウザでは正常に見えるので目視では気づけない型)。
 *
 *  ここでは **build時のJSTの号**を fs で読んで実体を描く。ハイドレート後は TokushuClient が
 *  本当の「今日」や ?d= の号に差し替えるので、利用者の体験は変わらない。
 *  ★h1 は恒久的な「日替わり特集」にし、その日のお題は h2 に置く(/shinkan と同じ考え方=
 *    恒久URLの見出しを日替わりの文言に縛らない)。
 */
export default function TokushuStatic() {
  const today = jstTodayStr();
  const day = loadTokushuDay(today);
  const days = loadTokushuIndexDays();
  const past = Object.keys(days).filter((k) => k < today).sort().reverse().slice(0, 30);

  if (!day) {
    // stock切れ。せめて過去号の索引だけは静的に出す(リンク0本の空頁にしない)
    return (
      <div className="px-4 py-10">
        <h1 className="text-xl font-black">📅 日替わり特集</h1>
        <p className="mt-2 text-sm text-ink/55">毎日ひとつのお題で、漫画を最大100作えらんで並べます。</p>
        <PastList past={past} days={days} />
      </div>
    );
  }

  const yearLabel = (it: TokushuItem) =>
    `${it[4] ?? "?"}${it[5] ? `〜${it[5]}` : "〜"}${it[6] === "completed" ? "・完結" : ""}`;

  return (
    <div className="mx-auto w-full md:max-w-[480px]">
      <div className="px-4 pb-4 pt-6">
        <h1 className="text-xl font-black">📅 日替わり特集</h1>
        <h2 className="mt-2 text-[26px] font-black leading-tight" style={{ color: day.c.a }}>{day.t}</h2>
        <p className="mt-1.5 text-[12px] leading-relaxed text-ink/70">{day.lead}</p>
        <p className="mt-2 text-[11px] font-extrabold text-ink/50">全{day.n}作</p>
      </div>
      <ol className="px-3.5">
        {day.items.map((it, i) => (
          <li key={it[0]} className="mb-1.5 flex items-center gap-2.5 rounded-md border border-[var(--color-line)] bg-[var(--color-surface)] px-2.5 py-1.5">
            <span className="w-7 shrink-0 text-center text-[16px] font-black italic text-ink/35">{i + 1}</span>
            <div className="min-w-0">
              <Link href={`/manga/${it[0]}`} className="truncate text-[13px] font-bold leading-snug">{it[1]}</Link>
              <p className="text-[10.5px] text-ink/55">{it[2]} ｜ {yearLabel(it)}</p>
            </div>
          </li>
        ))}
      </ol>
      <p className="mx-auto mt-3 w-fit pb-1 text-[12px] font-bold text-ink/50">
        <Link href={`/browse?${day.q}`} className="underline underline-offset-4">この条件で検索面でも見る →</Link>
      </p>
      <PastList past={past} days={days} />
    </div>
  );
}

function PastList({ past, days }: { past: string[]; days: ReturnType<typeof loadTokushuIndexDays> }) {
  if (past.length === 0) return null;
  return (
    <section className="mx-3.5 mb-10 mt-8">
      <h2 className="mb-2 text-[13px] font-extrabold text-ink/60">🗒️ 過去の特集</h2>
      <div className="overflow-hidden rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)]">
        {past.map((k) => (
          <Link key={k} href={`/tokushu?d=${k}`} className="flex items-baseline gap-3 border-b border-[var(--color-line)] px-3 py-2 last:border-b-0">
            <span className="w-[52px] shrink-0 text-[11px] tabular-nums text-ink/45">{k.slice(5).replace("-", "/")}</span>
            <span className="min-w-0 truncate text-[13px] font-bold">{days[k]?.t ?? k}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
