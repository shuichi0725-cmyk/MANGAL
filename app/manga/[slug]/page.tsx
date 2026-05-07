import Link from "next/link";
import { notFound } from "next/navigation";
import CoverImage from "@/components/CoverImage";
import VolumeRow from "@/components/VolumeRow";
import { yearStatusLabel } from "@/lib/format";
import { loadAllManga } from "@/lib/loadData";
import { primaryVolume } from "@/lib/schema";

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

  const v1 = primaryVolume(manga);
  // 表紙は volume.cover_url のみ。openBD/NDL fallback は使わない方針。
  const cover = v1?.cover_url ?? null;

  const publisher = data.publishers.find((p) => p.key === manga.publisher);
  const magazine = data.magazines.find((m) => m.key === manga.magazine);
  const demographic = data.demographics.find((d) => d.key === manga.demographic);

  // 各メタ項目をクリックすると、フィルタ済みトップページへ飛ぶ
  const interactive = true;

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
      <div className={`mt-6 grid gap-8 ${cover ? "md:grid-cols-[260px_1fr]" : ""}`}>
        {cover && (
          <div className="relative aspect-[2/3] bg-black/5 rounded overflow-hidden">
            <CoverImage src={cover} alt={`${manga.title} 1巻 表紙`} sizes="260px" size="detail" />
          </div>
        )}
        <div>
          <div className="flex items-start gap-3 flex-wrap">
            <h1 className="text-2xl md:text-3xl font-bold">{manga.title}</h1>
            {manga.anime_adapted && (
              <span className="inline-block mt-2 px-2 py-0.5 text-[11px] font-semibold rounded bg-amber-100 text-amber-800 border border-amber-200">
                アニメ化
                {manga.anime_first_year ? ` ${manga.anime_first_year}` : ""}
              </span>
            )}
          </div>
          <p className="text-sm text-black/60 mt-1">{manga.title_kana}</p>

          {manga.alternative_titles && (
            <p className="text-xs text-black/55 mt-1.5">
              {[
                manga.alternative_titles.en,
                manga.alternative_titles.fr,
                manga.alternative_titles.de,
                manga.alternative_titles.it,
                manga.alternative_titles.pt,
              ]
                .filter(Boolean)
                .join(" / ")}
            </p>
          )}

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

          {manga.awards && manga.awards.length > 0 && (
            <div className="mt-6">
              <p className="text-xs font-semibold text-black/70 mb-2">受賞歴</p>
              <ul className="flex flex-wrap gap-1.5">
                {manga.awards.map((a) => (
                  <li
                    key={a}
                    className="px-2 py-0.5 text-[11px] rounded bg-emerald-50 text-emerald-800 border border-emerald-200"
                  >
                    {a}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <VolumeRow manga={manga} />

          {manga.wikidata_qid && (
            <p className="mt-6 text-[11px] text-black/40">
              データ参照:{" "}
              <a
                href={`https://www.wikidata.org/wiki/${manga.wikidata_qid}`}
                target="_blank"
                rel="noopener nofollow"
                className="underline decoration-dotted underline-offset-2 hover:text-black/60"
              >
                Wikidata {manga.wikidata_qid}
              </a>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
