import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import AffiliateLink from "@/components/AffiliateLink";
import { openBdCoverUrl } from "@/lib/amazon";
import { loadAllManga } from "@/lib/loadData";

export function generateStaticParams() {
  return loadAllManga().manga.map((m) => ({ slug: m.slug }));
}

export default async function MangaDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const data = loadAllManga();
  const manga = data.manga.find((m) => m.slug === slug);
  if (!manga) notFound();

  const cover =
    manga.volume_1?.cover_url ||
    openBdCoverUrl(manga.volume_1?.isbn13 ?? null);

  const publisher = data.publishers.find((p) => p.key === manga.publisher);
  const magazine = data.magazines.find((m) => m.key === manga.magazine);
  const demographic = data.demographics.find((d) => d.key === manga.demographic);
  const genreNames = manga.genres.map(
    (g) => data.genres.find((x) => x.key === g)?.name ?? g,
  );

  const yearLabel = manga.year_ended
    ? `${manga.year_started}–${manga.year_ended}`
    : `${manga.year_started}–（連載中）`;

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <Link href="/" className="text-sm text-black/60 hover:text-black">
        ← 一覧へ戻る
      </Link>
      <div className="mt-6 grid md:grid-cols-[260px_1fr] gap-8">
        <div className="relative aspect-[2/3] bg-black/5 rounded overflow-hidden">
          {cover ? (
            <Image src={cover} alt={`${manga.title} 1巻 表紙`} fill sizes="260px" className="object-cover" />
          ) : (
            <div className="absolute inset-0 grid place-items-center text-black/40 text-sm">表紙なし</div>
          )}
        </div>
        <div>
          <h1 className="text-2xl md:text-3xl font-bold">{manga.title}</h1>
          <p className="text-sm text-black/60 mt-1">{manga.title_kana}</p>

          <dl className="mt-6 grid grid-cols-[6em_1fr] gap-y-1.5 text-sm">
            <dt className="text-black/50">出版年</dt>
            <dd>{yearLabel}</dd>
            <dt className="text-black/50">著者</dt>
            <dd>{manga.authors.map((a) => a.name).join(" / ")}</dd>
            {manga.original_authors.length > 0 && (
              <>
                <dt className="text-black/50">原作</dt>
                <dd>{manga.original_authors.map((a) => a.name).join(" / ")}</dd>
              </>
            )}
            <dt className="text-black/50">出版社</dt>
            <dd>{publisher?.name ?? manga.publisher}</dd>
            {magazine && (
              <>
                <dt className="text-black/50">連載誌</dt>
                <dd>{magazine.name}</dd>
              </>
            )}
            <dt className="text-black/50">分野</dt>
            <dd>{demographic?.name ?? manga.demographic}</dd>
            <dt className="text-black/50">ジャンル</dt>
            <dd>{genreNames.join(" / ")}</dd>
          </dl>

          {manga.synopsis && (
            <p className="mt-6 text-sm leading-relaxed text-black/80">{manga.synopsis}</p>
          )}

          <div className="mt-8">
            <AffiliateLink
              manga={manga}
              className="inline-block px-5 py-2.5 rounded bg-[var(--color-accent)] text-white font-semibold hover:opacity-90"
            >
              Amazonで1巻を見る
            </AffiliateLink>
            <p className="text-[11px] text-black/45 mt-2">
              リンクは Amazon アソシエイト・プログラムによる紹介です。
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
