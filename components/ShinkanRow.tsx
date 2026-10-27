import Link from "next/link";
import { amazonDpUrlFromIsbn13, amazonQuerySearchUrls, hasRakutenPaper } from "@/lib/amazon";
import MarqueeTitle from "@/components/MarqueeTitle";
import ShinkanDayHeader from "@/components/ShinkanDayHeader";
import { sortedDays, weekdayOf, type KnownSet, type ShinkanItem, type ShinkanMonth } from "@/lib/shinkanDates";

/** 新刊1冊の行(サーバ/クライアント両用=フックなし)。旧ShinkanClient の Row と同じ見た目。
 *  2026-09-01: 月別/今週/来月/今月の静的ページで共有するため切り出し(ShinkanClient は退役)。 */
const AMZ_TAG = process.env.NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG ?? "";

export function ShinkanRow({ it, known }: { it: ShinkanItem; known: boolean }) {
  const [slug, vol, title, cover, isbn, authors, publisher, imprint] = it;
  // ★Amazon・Kindle は作品頁(VolumeCoverflow)と同じ規則(2026-10-15 ユーザ裁定「エラーを出さない方を優先」):
  //   書影が楽天ブックスの紙の画像なら ISBN-10 の /dp/(紙も Kindle も)、それ以外は「題名 巻 著者」で検索
  const nameQ = [title, vol ? `${vol}巻` : "", (authors ?? "").split("・")[0]].filter(Boolean).join(" ");
  const dp = isbn && hasRakutenPaper(cover) ? amazonDpUrlFromIsbn13(isbn, AMZ_TAG) : null;
  const buy = dp ? { paper: dp, kindle: dp } : amazonQuerySearchUrls(nameQ, AMZ_TAG);
  const amz = buy.paper;
  // 表示150px高に合わせ楽天サムネイルを300x300へ格上げ(120/200のままだとぼやける)
  const coverHi = cover ? cover.replace(/_ex=(120x120|200x200)/, "_ex=300x300") : null;
  return (
    <div className="flex items-start gap-3 border-b border-[#1d1d1d] px-3 py-2">
      {/* 書影 → Amazon(アフィ。約105×150) */}
      <a href={amz} target="_blank" rel="nofollow sponsored noopener" className="spring-press block h-[150px] w-[105px] shrink-0 overflow-hidden bg-[#1a1a1a]" title={`${title} をAmazonで見る`}>
        {coverHi ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={coverHi} alt={vol ? `${title} ${vol}巻` : title} loading="lazy" className="h-full w-full bg-white object-cover" />
        ) : (
          <span className="flex h-full w-full items-center justify-center text-[10px] font-bold text-ink/40">NO IMG</span>
        )}
      </a>
      <div className="min-w-0 flex-1">
        {/* ★2026-10-27 ユーザ裁定(見本 札3・C): 長い題は1行で横に流す / 巻の札は1つ(1巻だけ枠線の「1巻 NEW」)/ 下に 詳細・Kindle・Amazon */}
        <a href={amz} target="_blank" rel="nofollow sponsored noopener" className="block">
          <MarqueeTitle text={title} className="text-[14px] font-bold leading-snug" />
          {vol ? (
            <span className="mt-0.5 block leading-none">
              {vol === 1 ? (
                <span className="border border-[var(--color-accent)] px-1 text-[9.5px] font-black text-[var(--color-accent)]">1巻 NEW</span>
              ) : (
                <span className="bg-[var(--color-accent)] px-1 text-[9.5px] font-black text-[#0d0d0d]">{vol}巻</span>
              )}
            </span>
          ) : null}
          {/* ★2026-08-27 ユーザ要望: 作者(複数でも1行)/会社/レーベル を1行ずつ */}
          {authors ? <span className="mt-1 block truncate text-[11.5px] leading-snug text-ink/60">{authors}</span> : null}
          {publisher ? <span className="mt-0.5 block truncate text-[10.5px] leading-snug text-ink/45">{publisher}</span> : null}
          {imprint ? <span className="mt-0.5 block truncate text-[10.5px] leading-snug text-ink/45">{imprint}</span> : null}
        </a>
        <div className="mt-1.5 flex items-center gap-1.5">
          {known && (
            <Link href={`/manga/${slug}`} className="spring-press border border-[var(--color-line)] px-2 py-0.5 text-[10.5px] font-bold text-ink/65">
              詳細
            </Link>
          )}
          <a href={buy.kindle} target="_blank" rel="nofollow sponsored noopener" className="spring-press bg-[#3b82f6] px-2.5 py-0.5 text-[11px] font-extrabold text-white">
            Kindle
          </a>
          <a href={buy.paper} target="_blank" rel="nofollow sponsored noopener" className="spring-press bg-[#e69500] px-2.5 py-0.5 text-[11px] font-extrabold text-white">
            Amazon
          </a>
        </div>
      </div>
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
