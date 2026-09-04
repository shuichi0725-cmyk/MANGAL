import Link from "next/link";
import CoverImage from "@/components/CoverImage";
import MarqueeTitle from "@/components/MarqueeTitle";
import { authorKeyFor } from "@/lib/authors";
import type { MangaListItem } from "@/lib/schema";

/** ジャンル面/下位面の書影グリッド(server)。 元は app/genre/[key] 内蔵だったものを共有化(2026-09-04)。
 *  ★著者名を著者頁へリンク(元は素の文字=ジャンル面から著者頁への導線0本だった)。
 *    <a>入れ子は不正HTMLなので、書影+題のLinkと著者行を分けて置く。 */
export default function GenreGrid({ items, limit = 120 }: { items: MangaListItem[]; limit?: number }) {
  return (
    <ul className="mt-5 grid grid-cols-3 gap-x-3 gap-y-5 sm:grid-cols-4">
      {items.slice(0, limit).map((m) => {
        const c = m.cover;
        return (
          <li key={m.slug}>
            <Link href={`/manga/${m.slug}`} className="block group spring-press">
              <div className="relative aspect-[2/3] w-full overflow-hidden rounded bg-[var(--color-surface-2)] border border-[var(--color-line)]">
                {c ? (
                  <CoverImage src={c} alt={m.title} sizes="120px" size="card" />
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center p-2 text-center text-[11px] leading-tight text-ink/45">
                    {m.title.slice(0, 28)}
                  </div>
                )}
                {typeof m.score === "number" && m.score >= 70 && (
                  <span className="absolute right-1 top-1 rounded bg-ink/80 px-1 py-0.5 text-[9px] font-bold text-white tabular-nums">
                    ★{(m.score / 10).toFixed(1)}
                  </span>
                )}
              </div>
              <MarqueeTitle text={m.title} className="mt-1 text-[12px] leading-snug text-ink/85 group-hover:text-[var(--color-accent)]" />
            </Link>
            <p className="truncate text-[10px] text-ink/50">
              {m.authors.map((a, i) => {
                const k = authorKeyFor(a.name);
                return (
                  <span key={`${a.name}-${i}`}>
                    {i > 0 && "・"}
                    {k ? (
                      <Link href={`/author/${k}`} className="hover:text-ink">
                        {a.name}
                      </Link>
                    ) : (
                      a.name
                    )}
                  </span>
                );
              })}
            </p>
          </li>
        );
      })}
    </ul>
  );
}
