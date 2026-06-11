import Link from "next/link";
import { bundle, DesignNav, seeded, CoverTile, Cover } from "@/lib/homeDesign";

/** 案2: 本屋の平台型 — 表紙が主役。新刊平台+棚(BOOK☆WALKER寄りのビジュアル先行) */
export default function Design02() {
  const { byNew, completedClassics, manga } = bundle();
  const hero = byNew[0];
  const shelf1 = byNew.slice(1, 13);
  const shelf2 = completedClassics.slice(0, 12);
  const shelf3 = seeded(manga, (m) => m.slug, 12, 13);
  const Shelf = ({ title, items, sub }: { title: string; sub?: string; items: typeof shelf1 }) => (
    <section className="mt-7 px-4">
      <div className="flex items-baseline justify-between">
        <h2 className="text-[15px] font-bold text-ink">{title}</h2>
        {sub && <span className="text-[11px] text-ink/50">{sub} →</span>}
      </div>
      <ul className="-mx-4 mt-2.5 flex gap-3 overflow-x-auto px-4 pb-2 snap-x">
        {items.map((m) => (
          <li key={m.slug} className="w-[108px] shrink-0 snap-start">
            <CoverTile m={m} sizes="108px" />
          </li>
        ))}
      </ul>
    </section>
  );
  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-10">
      <DesignNav current={2} />
      <header className="flex items-center justify-between px-4 py-3">
        <h1 className="text-lg font-extrabold">MANGAL<span className="text-[var(--color-accent)]">.</span></h1>
        <div className="flex gap-3 text-lg">
          <span>🔍</span><span>📚</span><span>≡</span>
        </div>
      </header>
      {hero && (
        <Link href={`/manga/${hero.slug}`} className="mx-4 flex gap-4 rounded-xl bg-gradient-to-br from-[var(--color-accent)]/90 to-[var(--color-accent)] p-4 text-white shadow-md">
          <div className="w-24 shrink-0 drop-shadow-lg"><Cover m={hero} sizes="96px" /></div>
          <div className="min-w-0 self-center">
            <p className="text-[10px] font-bold tracking-widest opacity-80">今日の新刊から</p>
            <p className="mt-1 text-lg font-extrabold leading-snug line-clamp-2">{hero.title}</p>
            <p className="mt-1 text-[12px] opacity-90">{hero.authors.map((a) => a.name).join("・")}</p>
            <span className="mt-2 inline-block rounded-full bg-white/20 px-3 py-1 text-[11px] font-semibold">作品ページへ →</span>
          </div>
        </Link>
      )}
      <Shelf title="新刊平台" sub="新刊をもっと見る" items={shelf1} />
      <Shelf title="全巻揃えたい完結の名作" sub="完結作品" items={shelf2} />
      <Shelf title="今日の出会い棚" sub="シャッフル" items={shelf3} />
      <section className="mt-8 px-4">
        <h2 className="text-[15px] font-bold text-ink">ジャンルの棚へ</h2>
        <div className="mt-2.5 grid grid-cols-3 gap-2 text-center text-[12px] font-semibold">
          {["スポーツ", "ファンタジー", "SF", "ラブコメ", "ホラー", "歴史"].map((g) => (
            <span key={g} className="rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)] py-3 text-ink/80 shadow-sm">{g}</span>
          ))}
        </div>
      </section>
    </div>
  );
}
