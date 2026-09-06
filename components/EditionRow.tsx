"use client";

import Link from "next/link";
import CoverImage from "./CoverImage";
import { amazonDpUrlFromIsbn13, amazonSearchUrl } from "@/lib/amazon";

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
  const amz =
    (isbn && amazonDpUrlFromIsbn13(isbn, AMZ_TAG)) || amazonSearchUrl(query ?? title, AMZ_TAG);
  return (
    <div className="flex items-start gap-2.5 rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)] p-2">
      {/* 書影+題 → Amazon(アフィ) */}
      <a
        href={amz}
        target="_blank"
        rel="nofollow sponsored noopener"
        title={`${title} をAmazonで見る`}
        className="spring-press flex min-w-0 flex-1 items-start gap-2.5"
      >
        <span className="relative block h-[150px] w-[105px] shrink-0 overflow-hidden rounded border border-[var(--color-line)] bg-[var(--color-surface-2)]">
          <CoverImage src={cover} alt={`${title} ${badge}`} sizes="105px" />
          <span className="absolute left-0 top-0 max-w-full truncate rounded-br bg-[var(--color-accent)] px-1 py-[1px] text-[9.5px] font-bold text-[var(--color-on-accent)]">
            {badge}
          </span>
        </span>
        <span className="min-w-0 flex-1">
          <span className="line-clamp-3 block text-[13px] font-bold leading-snug">{title}</span>
          {authors ? <span className="mt-1 block truncate text-[11px] leading-snug text-ink/60">{authors}</span> : null}
          <span className="mt-1 block text-[11px] leading-snug tabular-nums text-ink/70">{meta}</span>
          {note ? <span className="mt-0.5 block truncate text-[10.5px] leading-snug text-ink/40">{note}</span> : null}
        </span>
      </a>
      {/* 小さい「詳細」→ 作品ページ */}
      <Link
        href={`/manga/${slug}`}
        className="spring-press shrink-0 self-start rounded border border-[var(--color-line)] px-1.5 py-0.5 text-[10px] font-bold text-ink/65 hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
      >
        詳細
      </Link>
    </div>
  );
}
