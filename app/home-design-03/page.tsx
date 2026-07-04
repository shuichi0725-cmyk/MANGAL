import Link from "next/link";
import { bundle, DesignNav, seeded, volCount, Cover, CoverTile } from "@/lib/homeDesign";

/** 案3: 雑誌型 — 特集が主役。帯コピー付きフィーチャー+自動生成特集ブロック */
export default function Design03() {
  const { byNew, completedClassics, manga } = bundle();
  const feature = completedClassics[0];
  const fiveVols = manga.filter((m) => m.status === "completed" && volCount(m) >= 3 && volCount(m) <= 5).slice(0, 6);
  const nineties = manga.filter((m) => (m.year_started ?? 0) >= 1990 && (m.year_started ?? 0) < 2000).slice(0, 6);
  const Feature = ({ title, lead, items }: { title: string; lead: string; items: typeof fiveVols }) => (
    <section className="mt-8 px-4">
      <h2 className="border-l-4 border-[var(--color-accent)] pl-2.5 text-base font-extrabold text-ink">{title}</h2>
      <p className="mt-1 pl-3 text-[11.5px] text-ink/60">{lead}</p>
      <ul className="mt-3 grid grid-cols-3 gap-3">
        {items.map((m) => (
          <li key={m.slug}><CoverTile m={m} sizes="110px" /></li>
        ))}
      </ul>
    </section>
  );
  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-10">
      <DesignNav current={3} />
      <header className="bg-[var(--color-surface)] px-4 pb-4 pt-5 border-b-2 border-ink/80">
        <p className="text-[10px] font-semibold tracking-[0.25em] text-ink/50">WEEKLY MANGAL — 漫画と出会う週刊誌</p>
        <h1 className="mt-1 text-2xl font-black tracking-tight">MANGAL<span className="text-[var(--color-accent)]">.</span></h1>
      </header>
      {feature && (
        <Link href={`/manga/${feature.slug}`} className="block bg-[var(--color-surface)] px-4 py-5 border-b border-[var(--color-line)]">
          <div className="flex gap-4">
            <div className="w-32 shrink-0 rotate-[-2deg] shadow-xl"><Cover m={feature} sizes="128px" /></div>
            <div className="min-w-0 self-center">
              <p className="inline-block bg-ink px-2 py-0.5 text-[10px] font-bold tracking-widest text-white">今週の一冊</p>
              <p className="mt-2 text-xl font-extrabold leading-snug">{feature.title}</p>
              <p className="mt-1.5 border-l-2 border-[var(--color-accent)] pl-2 text-[12px] leading-relaxed text-ink/70 line-clamp-3">
                {feature.synopsis ?? `${(feature.authors ?? []).map((a) => a.name).join("・")}が描く、全${volCount(feature)}巻の金字塔。`}
              </p>
            </div>
          </div>
        </Link>
      )}
      <Feature title="特集: 週末で読み切る、全5巻以内の完結作" lead="短いのに濃い。一気読みの満足感で選んだ6作。" items={fiveVols} />
      <Feature title="特集: 90年代という奇跡" lead="あの10年に生まれた作品は、なぜ今も色褪せないのか。" items={nineties} />
      <Feature title="新刊クリップ" lead="今月手に入るようになった単行本から。" items={byNew.slice(0, 6)} />
      <section className="mt-8 px-4">
        <div className="rounded-lg border border-dashed border-ink/30 p-4 text-center text-[12px] text-ink/55">
          ◆ 特集は毎週自動生成 ◆<br />「完結◯巻」「年代」「ジャンル」「連載誌」の組合せで無限に作れます
        </div>
      </section>
    </div>
  );
}
