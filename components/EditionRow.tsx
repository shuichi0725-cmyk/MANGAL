"use client";

import Link from "next/link";
import CoverImage from "./CoverImage";
import { amazonDpUrlFromIsbn13, amazonQuerySearchUrls, hasRakutenPaper } from "@/lib/amazon";

/** 版もの一覧(/aizouban・/tokusouban)の1行。★2026-09-06 ユーザ指示
 *  「今月の新刊みたいに。画像を押すとアマゾン、小さい詳細を押すと漫画ページへ。画像の大きさも同じに」
 *  = components/ShinkanRow と同じ作り(書影105×150・書影+題がAmazon・右端に小さい「詳細」)。
 *  Amazonは ISBN-13→ISBN-10 の /dp/ 直リンク(取れない時だけ題名検索)。 */
const AMZ_TAG = process.env.NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG ?? "";

export default function EditionRow({
  slug, title, authors, cover, isbn, badge, meta, note, query,
}: {
  slug: string;
  title: string;
  authors?: string;
  cover: string;
  isbn?: string;
  badge: string;
  meta: React.ReactNode;
  note?: string;
  /** Amazon検索フォールバックのクエリ(既定=題名) */
  query?: string;
}) {
  // ★2026-11-09(見本 v1 ④): 新刊(ShinkanRow)と同じ規則にそろえる = 書影が楽天ブックスの紙の画像なら ISBN-10 の /dp/
  //   (紙も Kindle も)、それ以外は「題名 著者」で検索(旧 = ISBN があれば無条件に /dp/ = 紙の商品頁が無い巻で犬の404)
  const dp = isbn && hasRakutenPaper(cover) ? amazonDpUrlFromIsbn13(isbn, AMZ_TAG) : null;
  const buy = dp
    ? { paper: dp, kindle: dp }
    : amazonQuerySearchUrls([query ?? title, (authors ?? "").split("・")[0]].filter(Boolean).join(" "), AMZ_TAG);
  const amz = buy.paper;
  return (
    <div className="flex items-stretch gap-2.5 rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)] p-2">
      {/* 書影 → Amazon(アフィ) */}
      <a
        href={amz}
        target="_blank"
        rel="nofollow sponsored noopener"
        title={`${title} をAmazonで見る`}
        className="spring-press relative block h-[150px] w-[105px] shrink-0 overflow-hidden rounded border border-[var(--color-line)] bg-[var(--color-surface-2)]"
      >
        <CoverImage src={cover} alt={`${title} ${badge}`} sizes="105px" />
        <span className="absolute left-0 top-0 max-w-full truncate rounded-br bg-[var(--color-accent)] px-1 py-[1px] text-[9.5px] font-bold text-[var(--color-on-accent)]">
          {badge}
        </span>
      </a>
      <div className="flex min-w-0 flex-1 flex-col">
        {/* 題 → Amazon(アフィ) */}
        <a href={amz} target="_blank" rel="nofollow sponsored noopener" title={`${title} をAmazonで見る`} className="spring-press block min-w-0">
          <span className="line-clamp-3 block text-[13px] font-bold leading-snug">{title}</span>
          {authors ? <span className="mt-1 block truncate text-[11px] leading-snug text-ink/60">{authors}</span> : null}
          <span className="mt-1 block text-[11px] leading-snug tabular-nums text-ink/70">{meta}</span>
          {note ? <span className="mt-0.5 block truncate text-[10.5px] leading-snug text-ink/40">{note}</span> : null}
        </a>
        {/* ★詳細・Kindle・Amazon を書影の下端にそろえる(2026-11-09 ユーザ「書影の下方の列にあわせて」)。 詳細 = 作品ページ */}
        <div className="mt-auto flex items-center gap-1.5 pt-1.5">
          <Link
            href={`/manga/${slug}`}
            className="spring-press border border-[var(--color-line)] px-2 py-0.5 text-[10.5px] font-bold text-ink/65 hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
          >
            詳細
          </Link>
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
