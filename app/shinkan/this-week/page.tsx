import type { Metadata } from "next";
import Link from "next/link";
import { DesignNav } from "@/lib/homeDesign";
import ShinkanAbout from "@/components/ShinkanAbout";
import ShinkanMonthNav from "@/components/ShinkanMonthNav";
import ShinkanWeekList from "@/components/ShinkanWeekList";
import { dateLabel, itemsInRange, knownSlugs, listShinkanMonths, shinkanJsonLd, weekRange } from "@/lib/shinkanData";

/** 今週の新刊発売日(固定URL・2026-09-01 SEO)。build 時の今週(月〜日・JST)を静的に焼き、
 *  閲覧時に週が進んでいれば client が JSON から差し替える(ShinkanWeekList)。 */
const SITE = "https://mangal-db.com";

export const metadata: Metadata = {
  title: "今週の漫画・コミック新刊発売日一覧",
  description:
    "今週発売の漫画・コミック新刊を発売日ごとに全冊掲載(月曜〜日曜)。書影・巻数・著者・出版社つきで、Amazonでの予約・購入と作品ページ(全巻の発売日)へ移動できます。毎週更新。",
  alternates: { canonical: `${SITE}/shinkan/this-week` },
  openGraph: { title: "今週の漫画・コミック新刊発売日一覧", url: `${SITE}/shinkan/this-week`, siteName: "MANGAL", type: "website" },
};

export default function ShinkanThisWeekPage() {
  const { start, end } = weekRange();
  const rows = itemsInRange(start, end);
  const known = knownSlugs();
  const knownArr = [...new Set(rows.flatMap((r) => r.items.map((it) => it[0])))].filter((s) => known.has(s));
  const jsonLd = shinkanJsonLd("今週の漫画・コミック新刊発売日一覧", `${SITE}/shinkan/this-week`, rows);
  return (
    <>
      <DesignNav />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <div className="mx-auto w-full max-w-[720px] pb-12">
        <header className="border-b-[3px] border-[var(--color-accent)] px-4 py-3">
          <h1 className="text-[20px] font-black leading-tight">📦 今週の漫画・コミック新刊 発売日一覧</h1>
          <p className="mt-1 text-[12px] text-ink/65">
            今週({dateLabel(start)}〜{dateLabel(end)})に発売される新刊を日ごとに全冊。毎週更新。
          </p>
          <nav className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] font-bold" aria-label="関連ページ">
            <Link href={`/shinkan/${start.slice(0, 7)}`} className="underline">今月の新刊一覧</Link>
            <Link href="/shinkan/next-month" className="underline">来月の新刊</Link>
          </nav>
        </header>
        <ShinkanWeekList initialStart={start} initialEnd={end} initialRows={rows} knownSlugs={knownArr} />
      </div>
      <ShinkanMonthNav months={listShinkanMonths()} />
      <ShinkanAbout />
    </>
  );
}
