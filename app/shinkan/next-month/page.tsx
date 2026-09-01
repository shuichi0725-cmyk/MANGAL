import type { Metadata } from "next";
import Link from "next/link";
import { DesignNav } from "@/lib/homeDesign";
import { ShinkanDayBlock } from "@/components/ShinkanRow";
import ShinkanAbout from "@/components/ShinkanAbout";
import ShinkanMonthNav from "@/components/ShinkanMonthNav";
import ShinkanStaleNotice from "@/components/ShinkanStaleNotice";
import { dateLabel, jstYm, knownSlugs, listShinkanMonths, loadShinkanMonth, monthTotal, shinkanJsonLd, ymLabel } from "@/lib/shinkanData";

/** 来月の新刊発売予定(固定URL・2026-09-01 SEO)。build 時の翌月を静的に焼く。
 *  月別ページ(/shinkan/YYYY-MM)と内容は重なるが、「来月 漫画 新刊」の意図を常設URLで受ける面。 */
const SITE = "https://mangal-db.com";

export const metadata: Metadata = {
  title: "来月発売予定の漫画・コミック新刊一覧",
  description:
    "来月に発売予定の漫画・コミック新刊を発売予定日ごとに全冊掲載。書影・巻数・著者・出版社つきで、Amazonでの予約と作品ページ(全巻の発売日)へ移動できます。毎週更新。",
  alternates: { canonical: `${SITE}/shinkan/next-month` },
  openGraph: { title: "来月発売予定の漫画・コミック新刊一覧", url: `${SITE}/shinkan/next-month`, siteName: "MANGAL", type: "website" },
};

export default function ShinkanNextMonthPage() {
  const ym = jstYm(1);
  const d = loadShinkanMonth(ym) ?? { days: {}, unknown: [] };
  const known = knownSlugs();
  const days = Object.keys(d.days).sort();
  const rows = days.map((day) => ({ date: `${ym}-${day.padStart(2, "0")}`, items: d.days[day] }));
  const n = monthTotal(d);
  const jsonLd = shinkanJsonLd(`${ymLabel(ym)}発売予定の漫画・コミック新刊一覧`, `${SITE}/shinkan/next-month`, rows);
  return (
    <>
      <DesignNav />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <div className="mx-auto w-full max-w-[720px] pb-12">
        <header className="border-b-[3px] border-[var(--color-accent)] px-4 py-3">
          <h1 className="text-[20px] font-black leading-tight">📦 来月({ymLabel(ym)})発売予定の漫画・コミック新刊</h1>
          <p className="mt-1 text-[12px] text-ink/65">
            全{n.toLocaleString()}冊を発売予定日ごとに掲載。予約はAmazonへ、「詳細」は作品ページへ。発売日は変更されることがあります。
          </p>
          <nav className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] font-bold" aria-label="関連ページ">
            <Link href="/shinkan/this-week" className="underline">今週の新刊</Link>
            <Link href={`/shinkan/${jstYm(0)}`} className="underline">今月の新刊一覧</Link>
            <Link href={`/shinkan/${ym}`} className="underline">{ymLabel(ym)}の月別ページ</Link>
          </nav>
        </header>
        <ShinkanStaleNotice builtYm={ym} offset={1} />
        {rows.map((r, k) => (
          <ShinkanDayBlock key={r.date} id={`d${days[k]}`} heading={dateLabel(r.date, true)} items={r.items} known={known} />
        ))}
        {d.unknown?.length > 0 && <ShinkanDayBlock heading={`${ymLabel(ym)}発売(日付未確定)`} items={d.unknown} known={known} />}
        {n === 0 && <p className="px-4 py-8 text-[13px] text-ink/60">来月の新刊はまだ登録されていません。</p>}
      </div>
      <ShinkanMonthNav months={listShinkanMonths()} />
      <ShinkanAbout />
    </>
  );
}
