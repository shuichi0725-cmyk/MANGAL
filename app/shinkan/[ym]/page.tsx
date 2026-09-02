import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { DesignNav } from "@/lib/homeDesign";
import ShinkanAbout from "@/components/ShinkanAbout";
import ShinkanMonthView from "@/components/ShinkanMonthView";
import { jstYm, knownSlugs, listShinkanMonths, loadShinkanMonth, monthCount, shinkanJsonLd, sortedDays, ymLabel } from "@/lib/shinkanData";

/** 月別の新刊発売日ページ(2026-09-01 SEO): /shinkan/2026-09。
 *  public/shinkan/{ym}.json が実在する月だけ生成(dynamicParams=false)。
 *  「漫画 発売日」「コミック 新刊 9月」等の着地先。当月以降は ShinkanLive で鮮度を保つ。 */
const SITE = "https://mangal-db.com";

export const dynamicParams = false;
export function generateStaticParams() {
  return listShinkanMonths().map((ym) => ({ ym }));
}

function pageTitle(ym: string, n: number): string {
  return `${ymLabel(ym)}の漫画・コミック新刊発売日一覧(${n.toLocaleString()}冊)`;
}

export async function generateMetadata({ params }: { params: Promise<{ ym: string }> }): Promise<Metadata> {
  const { ym } = await params;
  const d = loadShinkanMonth(ym);
  if (!d) return {};
  const n = monthCount(d);
  const title = pageTitle(ym, n);
  const description =
    `${ymLabel(ym)}に発売される漫画・コミックの新刊${n.toLocaleString()}冊を発売日ごとに全冊掲載。` +
    "書影・巻数・著者・出版社・レーベル・ISBNつきで、Amazonでの予約・購入と作品ページ(全巻の発売日)へ移動できます。";
  return {
    title,
    description,
    alternates: { canonical: `${SITE}/shinkan/${ym}` },
    openGraph: { title, description, url: `${SITE}/shinkan/${ym}`, siteName: "MANGAL", type: "website" },
  };
}

export default async function ShinkanMonthPage({ params }: { params: Promise<{ ym: string }> }) {
  const { ym } = await params;
  const d = loadShinkanMonth(ym);
  if (!d) notFound();
  const months = listShinkanMonths();
  const i = months.indexOf(ym);
  const rows = sortedDays(d).map((day) => ({ date: `${ym}-${day.padStart(2, "0")}`, items: d.days[day] }));
  const jsonLd = shinkanJsonLd(pageTitle(ym, monthCount(d)), `${SITE}/shinkan/${ym}`, rows);
  return (
    <>
      <DesignNav />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <ShinkanMonthView
        ym={ym}
        data={d}
        months={months}
        known={knownSlugs()}
        heading={`${ymLabel(ym)}の漫画・コミック新刊 発売日一覧`}
        lead="発売日ごとに全冊掲載。書影・題名はAmazon(予約・購入)、「詳細」は作品ページへ。"
        pageUrl={`${SITE}/shinkan/${ym}`}
        live={ym >= jstYm(0)}
        prev={i > 0 ? months[i - 1] : null}
        next={i >= 0 && i < months.length - 1 ? months[i + 1] : null}
      />
      <ShinkanAbout />
    </>
  );
}
