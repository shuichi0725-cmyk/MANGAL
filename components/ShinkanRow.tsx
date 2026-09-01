import Link from "next/link";
import { amazonDpUrlFromIsbn13, amazonSearchUrl } from "@/lib/amazon";
import type { ShinkanItem } from "@/lib/shinkanData";

/** 新刊1冊の行(サーバ/クライアント両用=フックなし)。ShinkanClient の Row と同じ見た目。
 *  2026-09-01: 月別/今週/来月の静的ページで共有するため切り出し。 */
const AMZ_TAG = process.env.NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG ?? "";

export function ShinkanRow({ it, known }: { it: ShinkanItem; known: boolean }) {
  const [slug, vol, title, cover, isbn, authors, publisher, imprint] = it;
  const amz = (isbn && amazonDpUrlFromIsbn13(isbn, AMZ_TAG)) || amazonSearchUrl(`${title} ${vol ?? ""}`.trim(), AMZ_TAG);
  const coverHi = cover ? cover.replace(/_ex=(120x120|200x200)/, "_ex=300x300") : null;
  return (
    <div className="flex items-start gap-3 border-b border-[#1d1d1d] px-3 py-2">
      <a href={amz} target="_blank" rel="nofollow sponsored noopener" className="spring-press flex min-w-0 flex-1 items-start gap-3" title={`${title} をAmazonで見る`}>
        <span className="relative block h-[150px] w-[105px] shrink-0 overflow-hidden bg-[#1a1a1a]">
          {coverHi ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={coverHi} alt={vol ? `${title} ${vol}巻` : title} loading="lazy" className="h-full w-full object-cover" />
          ) : (
            <span className="flex h-full w-full items-center justify-center text-[10px] font-bold text-ink/40">NO IMG</span>
          )}
        </span>
        <span className="min-w-0">
          <span className="block text-[14px] font-bold leading-snug">
            {title}
            {vol ? <span className="ml-1 bg-[var(--color-accent)] px-1 text-[9.5px] font-black text-[#0d0d0d] align-[1px]">{vol}巻</span> : null}
            {vol === 1 ? <span className="ml-1 border border-[var(--color-accent)] px-1 text-[9px] font-black text-[var(--color-accent)] align-[1px]">新刊1巻</span> : null}
          </span>
          {authors ? <span className="mt-1 block truncate text-[11.5px] leading-snug text-ink/60">{authors}</span> : null}
          {publisher ? <span className="mt-0.5 block truncate text-[10.5px] leading-snug text-ink/45">{publisher}</span> : null}
          {imprint ? <span className="mt-0.5 block truncate text-[10.5px] leading-snug text-ink/45">{imprint}</span> : null}
        </span>
      </a>
      {known && (
        <Link href={`/manga/${slug}`} className="spring-press shrink-0 border border-[var(--color-line)] px-1.5 py-0.5 text-[10px] font-bold text-ink/65">
          詳細
        </Link>
      )}
    </div>
  );
}

/** 「9月1日(月) 12冊」見出し+行群 */
export function ShinkanDayBlock({ heading, id, items, known }: { heading: string; id?: string; items: ShinkanItem[]; known: Set<string> }) {
  return (
    <section id={id} className="scroll-mt-14">
      <h2 className="sticky top-0 z-10 border-b border-[var(--color-accent)]/60 bg-[var(--color-surface)] px-3 py-1.5 text-[13px] font-black">
        {heading} <span className="ml-1 text-[11px] font-bold text-ink/55">{items.length}冊</span>
      </h2>
      {items.map((it, i) => (
        <ShinkanRow key={`${it[0]}-${it[1] ?? "x"}-${i}`} it={it} known={known.has(it[0])} />
      ))}
    </section>
  );
}
