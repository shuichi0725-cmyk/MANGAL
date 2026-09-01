import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { DesignNav } from "@/lib/homeDesign";
import { ShinkanDayBlock } from "@/components/ShinkanRow";
import ShinkanAbout from "@/components/ShinkanAbout";
import ShinkanMonthNav from "@/components/ShinkanMonthNav";
import {
  dateLabel,
  knownSlugs,
  listShinkanMonths,
  loadShinkanMonth,
  monthTotal,
  shinkanJsonLd,
  ymLabel,
} from "@/lib/shinkanData";

/** 月別の新刊発売日ページ(2026-09-01 SEO): /shinkan/2026-09。
 *  ★/shinkan(ShinkanClient)は client fetch 描画で静的HTMLが「読み込み中…」だけ=Googleに空に見えていた。
 *  同じ public/shinkan/{ym}.json を build 時に焼いた静的面を月ごとに持ち、
 *  「漫画 発売日」「コミック 新刊 9月」等の着地先にする。対話面(/shinkan?m=)はそのまま併存。 */
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
  const n = monthTotal(d);
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
  const prev = i > 0 ? months[i - 1] : null;
  const next = i >= 0 && i < months.length - 1 ? months[i + 1] : null;
  const known = knownSlugs();
  const days = Object.keys(d.days).sort();
  const rows = days.map((day) => ({ date: `${ym}-${day.padStart(2, "0")}`, items: d.days[day] }));
  const n = monthTotal(d);
  const title = pageTitle(ym, n);
  const jsonLd = shinkanJsonLd(title, `${SITE}/shinkan/${ym}`, rows);
  return (
    <>
      <DesignNav />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <div className="mx-auto w-full max-w-[720px] pb-12">
        <header className="border-b-[3px] border-[var(--color-accent)] px-4 py-3">
          <h1 className="text-[20px] font-black leading-tight">📦 {ymLabel(ym)}の漫画・コミック新刊 発売日一覧</h1>
          <p className="mt-1 text-[12px] text-ink/65">
            全{n.toLocaleString()}冊を発売日ごとに掲載。書影・題名はAmazon(予約・購入)、「詳細」は作品ページへ。
          </p>
          <nav className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[12px] font-bold" aria-label="前後の月">
            {prev ? <Link href={`/shinkan/${prev}`} className="underline">← {ymLabel(prev)}</Link> : <span className="text-ink/35">← 前の月</span>}
            <Link href="/shinkan/this-week" className="underline">今週の新刊</Link>
            {next ? <Link href={`/shinkan/${next}`} className="underline">{ymLabel(next)} →</Link> : <span className="text-ink/35">次の月 →</span>}
          </nav>
          {days.length > 0 && (
            <p className="mt-2 flex flex-wrap gap-x-2 gap-y-1 text-[11px]" aria-label="日付へ移動">
              {days.map((day) => (
                <a key={day} href={`#d${day}`} className="underline text-ink/70">{Number(day)}日({d.days[day].length})</a>
              ))}
            </p>
          )}
        </header>
        {rows.map((r, k) => (
          <ShinkanDayBlock key={r.date} id={`d${days[k]}`} heading={dateLabel(r.date, true)} items={r.items} known={known} />
        ))}
        {d.unknown?.length > 0 && (
          <ShinkanDayBlock heading={`${ymLabel(ym)}発売(日付未確定)`} items={d.unknown} known={known} />
        )}
        {n === 0 && <p className="px-4 py-8 text-[13px] text-ink/60">この月の新刊はまだ登録されていません。</p>}
      </div>
      <ShinkanMonthNav months={months} current={ym} />
      <ShinkanAbout />
    </>
  );
}
