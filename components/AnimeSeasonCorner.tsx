import Link from "next/link";
import CoverImage from "./CoverImage";
import MarqueeTitle from "./MarqueeTitle";
import view from "@/data/anime-seasons-view.json";
import {
  currentSeasonKey,
  seasonLabel,
  sourceLabel,
  type AnimeSeasonsView,
} from "@/lib/animeSeason";

const V = view as unknown as AnimeSeasonsView;

/** 📺 今季アニメの原作コーナー(トップ用・server)。季刊入替=view JSON再生成のみ。2026-07-12 */
export default function AnimeSeasonCorner() {
  const key = currentSeasonKey(V.order);
  const entries = (V.seasons[key] ?? []).slice(0, 12);
  if (entries.length === 0) return null;

  return (
    <section className="mt-4 px-4">
      <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3.5 shadow-sm">
        <div className="flex items-baseline justify-between">
          <h2 className="text-[14px] font-extrabold">📺 {seasonLabel(key)}アニメの原作</h2>
          <Link href={`/anime/${key}`} className="text-[11px] font-semibold text-[var(--color-accent)]">
            全{(V.seasons[key] ?? []).length}作品 →
          </Link>
        </div>
        <ul className="-mx-3.5 mt-2.5 flex gap-3 overflow-x-auto px-3.5 pb-1 snap-x">
          {entries.map((e) => (
            <li key={e.slug} className="w-[96px] shrink-0 snap-start">
              <Link href={`/manga/${e.slug}`} className="block group spring-press">
                <div
                  className="relative overflow-hidden rounded-md border border-[var(--color-line)] bg-[var(--color-surface-2)]"
                  style={{ aspectRatio: "2 / 3" }}
                >
                  {e.cover ? (
                    <CoverImage src={e.cover} alt={e.title} sizes="96px" />
                  ) : (
                    <span className="flex h-full w-full items-center justify-center text-[10px] text-ink/40">
                      no image
                    </span>
                  )}
                  <span className="absolute left-1 top-1 rounded bg-black/60 px-1 py-0.5 text-[9px] font-semibold text-white">
                    {sourceLabel(e.source)}
                  </span>
                </div>
                <MarqueeTitle
                  text={e.title}
                  className="mt-1 text-[12px] leading-snug text-ink/85 group-hover:text-[var(--color-accent)]"
                />
              </Link>
            </li>
          ))}
        </ul>
        <p className="mt-1.5 text-right text-[10px] text-ink/40">
          <Link href="/anime" className="hover:text-[var(--color-accent)]">
            過去の季節も見る(1960年代〜) →
          </Link>
        </p>
      </div>
    </section>
  );
}
