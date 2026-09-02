import Link from "next/link";
import { amazonDpUrlFromIsbn13, amazonSearchUrl } from "@/lib/amazon";
import ShinkanDayHeader from "@/components/ShinkanDayHeader";
import { sortedDays, weekdayOf, type KnownSet, type ShinkanItem, type ShinkanMonth } from "@/lib/shinkanDates";

/** 新刊1冊の行(サーバ/クライアント両用=フックなし)。旧ShinkanClient の Row と同じ見た目。
 *  2026-09-01: 月別/今週/来月/今月の静的ページで共有するため切り出し(ShinkanClient は退役)。 */
const AMZ_TAG = process.env.NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG ?? "";

export function ShinkanRow({ it, known }: { it: ShinkanItem; known: boolean }) {
  const [slug, vol, title, cover, isbn, authors, publisher, imprint] = it;
  const amz = (isbn && amazonDpUrlFromIsbn13(isbn, AMZ_TAG)) || amazonSearchUrl(`${title} ${vol ?? ""}`.trim(), AMZ_TAG);
  // 表示150px高に合わせ楽天サムネイルを300x300へ格上げ(120/200のままだとぼやける)
  const coverHi = cover ? cover.replace(/_ex=(120x120|200x200)/, "_ex=300x300") : null;
  return (
    <div className="flex items-start gap-3 border-b border-[#1d1d1d] px-3 py-2">
      {/* 書影+題 → Amazon(アフィ。約105×150) */}
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
          {/* ★2026-08-27 ユーザ要望: 作者(複数でも1行)/会社/レーベル を1行ずつ */}
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

/** 日付見出し+行群(今週ページ等、月に閉じない並び用) */
export function ShinkanDayBlock({
  id,
  label,
  sub,
  items,
  known,
  prevId,
  nextId,
}: {
  id?: string;
  label: string;
  sub?: string;
  items: ShinkanItem[];
  known: KnownSet;
  prevId?: string;
  nextId?: string;
}) {
  return (
    <section id={id}>
      <ShinkanDayHeader label={label} sub={sub} count={items.length} prevId={prevId} nextId={nextId} />
      {items.map((it, i) => (
        <ShinkanRow key={`${it[0]}-${it[1] ?? "x"}-${i}`} it={it} known={known.has(it[0])} />
      ))}
    </section>
  );
}

/** 1か月分の本文(日ごとのセクション+日付未定+PR表記)。server でも client でも描ける(フック無し)。
 *  セクションid は旧ShinkanClient と同じ `day-{N}`(ホーム「全部見る→?go=today」のジャンプ先互換)。 */
export function ShinkanMonthList({ ym, data, known }: { ym: string; data: ShinkanMonth; known: KnownSet }) {
  const days = sortedDays(data);
  const mm = Number(ym.slice(5));
  return (
    <>
      {days.map((d, di) => (
        <ShinkanDayBlock
          key={d}
          id={`day-${Number(d)}`}
          label={`${mm}/${d.padStart(2, "0")}`}
          sub={weekdayOf(`${ym}-${d.padStart(2, "0")}`)}
          items={data.days[d]}
          known={known}
          prevId={di > 0 ? `day-${Number(days[di - 1])}` : undefined}
          nextId={di < days.length - 1 ? `day-${Number(days[di + 1])}` : undefined}
        />
      ))}
      {data.unknown?.length > 0 && <ShinkanDayBlock id="day-unknown" label="日付未定" items={data.unknown} known={known} />}
      {days.length === 0 && !data.unknown?.length && (
        <p className="p-6 text-[12px] text-ink/50">この月のデータはまだありません。</p>
      )}
      <p className="px-4 pt-3 text-[10px] text-ink/40">[PR] Amazonリンクにはアフィリエイト広告を含みます</p>
    </>
  );
}
