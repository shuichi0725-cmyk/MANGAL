import type { Metadata } from "next";
import { DesignNav } from "@/lib/homeDesign";
import ShinkanAbout from "@/components/ShinkanAbout";
import ShinkanMonthView from "@/components/ShinkanMonthView";
import ShinkanStaleNotice from "@/components/ShinkanStaleNotice";
import { jstYm, knownSlugs, listShinkanMonths, loadShinkanMonth, shinkanJsonLd, sortedDays, ymLabel } from "@/lib/shinkanData";

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
  const months = listShinkanMonths();
  const rows = sortedDays(d).map((day) => ({ date: `${ym}-${day.padStart(2, "0")}`, items: d.days[day] }));
  const jsonLd = shinkanJsonLd(`${ymLabel(ym)}発売予定の漫画・コミック新刊一覧`, `${SITE}/shinkan/next-month`, rows);
  return (
    <>
      <DesignNav />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <ShinkanMonthView
        ym={ym}
        data={d}
        months={months}
        known={knownSlugs()}
        heading={`来月(${ymLabel(ym)})の新刊発売予定`}
        lead="発売予定日ごとに全冊掲載。予約はAmazonへ、「詳細」は作品ページへ。発売日は変更されることがあります。"
        pageUrl={`${SITE}/shinkan/next-month`}
        live
        notice={<ShinkanStaleNotice builtYm={ym} offset={1} />}
      />
      <ShinkanAbout />
    </>
  );
}
