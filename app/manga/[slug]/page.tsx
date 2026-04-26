import Link from "next/link";
import { notFound } from "next/navigation";
import AffiliateLink from "@/components/AffiliateLink";
import CoverImage from "@/components/CoverImage";
import VolumeRow from "@/components/VolumeRow";
import { openBdCoverUrl } from "@/lib/amazon";
import { yearStatusLabel } from "@/lib/format";
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

  const v1 = manga.volumes[0];
  const cover = v1?.cover_url || openBdCoverUrl(v1?.isbn13 ?? null);

  const publisher = data.publishers.find((p) => p.key === manga.publisher);
  const magazine = data.magazines.find((m) => m.key === manga.magazine);
  const demographic = data.demographics.find((d) => d.key === manga.demographic);

  // 試行: ONE PIECE のみ詳細項目を「クリックでフィルタ済みトップへ」化
  const interactive = manga.slug === "one-piece";

  const FilterLink = ({ href, children }: { href: string; children: React.ReactNode }) =>
    interactive ? (
      <Link
        href={href}
        className="hover:text-[var(--color-accent)] underline decoration-dotted underline-offset-2"
      >
        {children}
      </Link>
    ) : (
      <>{children}</>
    );

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <Link href="/" className="text-sm text-black/60 hover:text-black">
        ← 一覧へ戻る
      </Link>
      <div className="mt-6 grid md:grid-cols-[260px_1fr] gap-8">
        <div className="relative aspect-[2/3] bg-black/5 rounded overflow-hidden">
          <CoverImage src={cover} alt={`${manga.title} 1巻 表紙`} sizes="260px" size="detail" />
        </div>
        <div>
          <h1 className="text-2xl md:text-3xl font-bold">{manga.title}</h1>
          <p className="text-sm text-black/60 mt-1">{manga.title_kana}</p>

          <dl className="mt-6 grid grid-cols-[6em_1fr] gap-y-1.5 text-sm">
            <dt className="text-black/50">出版年</dt>
            <dd>
              <FilterLink
                href={`/?yearMin=${manga.year_started}&yearMax=${manga.year_started}`}
              >
                {yearStatusLabel(manga)}
              </FilterLink>
            </dd>
            <dt className="text-black/50">著者</dt>
            <dd>
              {manga.authors.map((a, i) => (
                <span key={a.name}>
                  {i > 0 && " / "}
                  <FilterLink href={`/?author=${encodeURIComponent(a.name)}`}>
                    {a.name}
                  </FilterLink>
                </span>
              ))}
            </dd>
            {manga.original_authors.length > 0 && (
              <>
                <dt className="text-black/50">原作</dt>
                <dd>
                  {manga.original_authors.map((a, i) => (
                    <span key={a.name}>
                      {i > 0 && " / "}
                      <FilterLink
                        href={`/?originalAuthor=${encodeURIComponent(a.name)}`}
                      >
                        {a.name}
                      </FilterLink>
                    </span>
                  ))}
                </dd>
              </>
            )}
            <dt className="text-black/50">出版社</dt>
            <dd>
              <FilterLink href={`/?publisher=${encodeURIComponent(manga.publisher)}`}>
                {publisher?.name ?? manga.publisher}
              </FilterLink>
            </dd>
            {magazine && (
              <>
                <dt className="text-black/50">連載誌</dt>
                <dd>
                  <FilterLink href={`/?magazine=${encodeURIComponent(magazine.key)}`}>
                    {magazine.name}
                  </FilterLink>
                </dd>
              </>
            )}
            <dt className="text-black/50">分野</dt>
            <dd>
              <FilterLink href={`/?demographic=${encodeURIComponent(manga.demographic)}`}>
                {demographic?.name ?? manga.demographic}
              </FilterLink>
            </dd>
            <dt className="text-black/50">ジャンル</dt>
            <dd>
              {manga.genres.map((g, i) => {
                const name = data.genres.find((x) => x.key === g)?.name ?? g;
                return (
                  <span key={g}>
                    {i > 0 && " / "}
                    <FilterLink href={`/?genre=${encodeURIComponent(g)}`}>
                      {name}
                    </FilterLink>
                  </span>
                );
              })}
            </dd>
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

          <VolumeRow manga={manga} />
        </div>
      </div>
    </div>
  );
}
