import type { Metadata } from "next";
import { DesignNav } from "@/lib/homeDesign";
import ShinkanAbout from "@/components/ShinkanAbout";
import ShinkanMonthView from "@/components/ShinkanMonthView";
import ShinkanStaleNotice from "@/components/ShinkanStaleNotice";
import { jstYm, knownSlugs, listShinkanMonths, loadShinkanMonth, monthCount, shinkanJsonLd, sortedDays, ymLabel } from "@/lib/shinkanData";

/** 今月の新刊発売日一覧(=常設URL /shinkan)。
 *  ★2026-09-01 静的化(ユーザ裁定「静的ページのみで問題ない」): 旧 ShinkanClient(client fetch 描画・
 *  静的HTMLは「読み込み中…」だけ=Googleに空)を退役し、build 時の当月分を本文に焼く。
 *  月の切替は月別ページ(/shinkan/YYYY-MM)への静的リンク、鮮度は ShinkanLive、
 *  旧URL(?m=)と ?go=today は ShinkanPageEffects が受ける。 */
const SITE = "https://mangal-db.com";

function current() {
  const ym = jstYm(0);
  const data = loadShinkanMonth(ym) ?? { days: {}, unknown: [] };
  return { ym, data, n: monthCount(data) };
}

export function generateMetadata(): Metadata {
  const { ym, n } = current();
  // ★layout の title テンプレートが「| 漫画・コミックのMANGAL」を付けるので、ここでは「漫画・コミック」を重ねない
  const title = `今月の新刊発売日一覧(${ymLabel(ym)}・漫画${n.toLocaleString()}冊)`;
  const description =
    `${ymLabel(ym)}に発売される漫画・コミックの新刊${n.toLocaleString()}冊を発売日ごとに全冊掲載。` +
    "書影・巻数・著者・出版社・レーベルつきで、Amazonでの予約・購入と作品ページ(全巻の発売日)へ移動できます。毎週更新。";
  return {
    title,
    description,
    alternates: { canonical: `${SITE}/shinkan` },
    openGraph: { title, description, url: `${SITE}/shinkan`, siteName: "MANGAL", type: "website" },
  };
}

export default function ShinkanPage() {
  const { ym, data } = current();
  const months = listShinkanMonths();
  const i = months.indexOf(ym);
  const rows = sortedDays(data).map((day) => ({ date: `${ym}-${day.padStart(2, "0")}`, items: data.days[day] }));
  const known = knownSlugs();
  const jsonLd = shinkanJsonLd(`今月(${ymLabel(ym)})の漫画・コミック新刊発売日一覧`, `${SITE}/shinkan`, rows, known);
  return (
    <>
      <DesignNav />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <ShinkanMonthView
        ym={ym}
        data={data}
        months={months}
        known={known}
        heading={`${ymLabel(ym)}の新刊`}
        lead="発売日ごとに全冊掲載。スクロールだけで全部見られます。書影・題はAmazonへ、「詳細」で作品ページへ。"
        pageUrl={`${SITE}/shinkan`}
        live
        prev={i > 0 ? months[i - 1] : null}
        next={i >= 0 && i < months.length - 1 ? months[i + 1] : null}
        notice={<ShinkanStaleNotice builtYm={ym} offset={0} />}
      />
      <ShinkanAbout />
    </>
  );
}
