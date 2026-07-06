import Link from "next/link";
import { bundle, DesignNav, volCount, Cover, firstVolumeDate } from "@/lib/homeDesign";
import type { Manga } from "@/lib/schema";

export const metadata = {
  title: "なんでもランキング | MANGAL",
  description: "巻数・連載年数・完結大作…データベースだから作れる切り口ランキング。",
};

/** なんでもランキング(2026-07-07 manba学び「切り口ランキング量産はDB強者の土俵」):
 *  ビルド時に全DBから機械生成。コミュニティ投票不要=MANGALの差別化軸。 */
export default function RankingsPage() {
  const { manga } = bundle();
  const year = new Date(Date.now() + 9 * 3600 * 1000).getUTCFullYear();

  const axes: Array<{ icon: string; title: string; note: string; items: Manga[]; value: (m: Manga) => string }> = [
    {
      icon: "📚", title: "巻数最長(連載中)", note: "いま追いかけられる最長シリーズ",
      items: manga.filter((m) => m.status !== "completed").sort((a, b) => volCount(b) - volCount(a)).slice(0, 10),
      value: (m) => `${volCount(m)}巻`,
    },
    {
      icon: "🏛️", title: "巻数最長(完結)", note: "読み切った人はいるのか",
      items: manga.filter((m) => m.status === "completed").sort((a, b) => volCount(b) - volCount(a)).slice(0, 10),
      value: (m) => `全${volCount(m)}巻`,
    },
    {
      icon: "⏳", title: "最古の現役連載", note: "昭和から続く鉄人たち",
      items: manga.filter((m) => m.status !== "completed" && m.year_started).sort((a, b) => (a.year_started ?? 9999) - (b.year_started ?? 9999)).slice(0, 10),
      value: (m) => `${m.year_started}年〜 (${year - (m.year_started ?? year)}年目)`,
    },
    {
      icon: "🎉", title: `今年(${year}年)完結した大作`, note: "一気読みするなら今",
      items: manga.filter((m) => m.status === "completed" && m.year_ended === year && volCount(m) >= 10).sort((a, b) => volCount(b) - volCount(a)).slice(0, 10),
      value: (m) => `全${volCount(m)}巻`,
    },
    {
      icon: "⚡", title: "短期集中・全3巻以内の完結作", note: "週末で読み切れる",
      items: manga.filter((m) => m.status === "completed" && volCount(m) >= 2 && volCount(m) <= 3 && (m.popularity ?? 0) > 0)
        .sort((a, b) => (b.popularity ?? 0) - (a.popularity ?? 0)).slice(0, 10),
      value: (m) => `全${volCount(m)}巻`,
    },
    {
      icon: "🐣", title: "1巻が出たのはいつ? 現役最長キャリア", note: "巻データで見る古参",
      items: manga.filter((m) => firstVolumeDate(m) && m.status !== "completed").sort((a, b) => String(firstVolumeDate(a)).localeCompare(String(firstVolumeDate(b)))).slice(0, 10),
      value: (m) => `1巻 ${String(firstVolumeDate(m)).replaceAll("-", ".")}`,
    },
  ];

  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-12">
      <DesignNav />
      <div className="mx-auto w-full max-w-[720px] px-4">
        <h1 className="mt-5 text-[18px] font-extrabold">🏆 なんでもランキング</h1>
        <p className="mt-1 text-[11.5px] text-ink/55">全{manga.length.toLocaleString()}作品のデータベースから機械集計。人気投票ではなく、数字の事実だけ。</p>
        {axes.map((ax) => (
          <section key={ax.title} className="mt-6 rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3.5 shadow-sm">
            <h2 className="text-[14px] font-extrabold">{ax.icon} {ax.title}</h2>
            <p className="text-[10.5px] text-ink/45">{ax.note}</p>
            <ol className="mt-2 space-y-1.5">
              {ax.items.map((m, i) => (
                <li key={m.slug}>
                  <Link href={`/manga/${m.slug}`} className="spring-press flex items-center gap-2.5">
                    <span className={`w-6 shrink-0 text-center text-[13px] font-extrabold tabular-nums ${i < 3 ? "text-[var(--color-accent)]" : "text-ink/40"}`}>{i + 1}</span>
                    <div className="w-8 shrink-0"><Cover m={m} sizes="32px" /></div>
                    <span className="min-w-0 flex-1 truncate text-[13px] font-medium">{m.title}</span>
                    <span className="shrink-0 text-[11px] tabular-nums text-ink/55">{ax.value(m)}</span>
                  </Link>
                </li>
              ))}
            </ol>
          </section>
        ))}
      </div>
    </div>
  );
}
