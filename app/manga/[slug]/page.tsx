import Link from "next/link";
import { notFound } from "next/navigation";
import CoverImage from "@/components/CoverImage";
import VolumeRow from "@/components/VolumeRow";
import { yearStatusLabel } from "@/lib/format";
import { loadAllManga } from "@/lib/loadData";
import { primaryVolume } from "@/lib/schema";
import { jaCategory, jaGenre, jaTag } from "@/lib/anilist-i18n";

export function generateStaticParams() {
  const slugs = loadAllManga().manga.map((m) => ({ slug: m.slug }));
  // empty state (= データ準備中) でも build を通すための placeholder。
  // detail page 側で `manga not found` → 404 にフォールバックする。
  return slugs.length > 0 ? slugs : [{ slug: "_empty" }];
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
          {/* 副題 (= MADB の ` : ` 右側、 ない時は β 案で空白行を保持) */}
          <p className="text-base text-black/75 mt-1 min-h-[1.5rem]">
            {manga.subtitle ?? " "}
          </p>
          <p className="text-sm text-black/60 mt-1">
            {manga.title_kana}
            {manga.subtitle_kana ? ` : ${manga.subtitle_kana}` : ""}
          </p>

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
          {manga.synonyms && manga.synonyms.length > 0 && (
            <p className="text-[11px] text-black/45 mt-1 leading-relaxed">
              他言語・別名: {manga.synonyms.join(" / ")}
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
              {(() => {
                // 種3 既存 ジャンル (= filter link 付き) + AniList 由来 (= filter なし) を 統合
                const seenNames = new Set<string>();
                const items: Array<{ name: string; key?: string }> = [];
                for (const g of manga.genres) {
                  const name = data.genres.find((x) => x.key === g)?.name ?? g;
                  if (seenNames.has(name)) continue;
                  seenNames.add(name);
                  items.push({ name, key: g });
                }
                // AniList genres (= 19 種類)
                for (const g of manga.genres_anilist ?? []) {
                  const ja = jaGenre(g);
                  if (seenNames.has(ja)) continue;
                  // 種3 マスター に 同名 key があれば filter 付ける
                  const masterKey = data.genres.find((x) => x.name === ja)?.key;
                  seenNames.add(ja);
                  items.push({ name: ja, key: masterKey });
                }
                // AniList tags (= 案2 filter 後)
                // mainstream で 情報価値の低い tag は 除外
                const NOISE_TAGS = new Set([
                  "Heterosexual", // mainstream default
                  "Male Protagonist", // 当然
                  "Female Protagonist",
                  "Primarily Adult Cast",
                  "Primarily Child Cast",
                  "Primarily Teen Cast",
                ]);
                for (const t of manga.tags ?? []) {
                  // 読者層 (= Demographic) は 「分野」 行で 既出のため 除外
                  if (t.category === "Demographic") continue;
                  if (NOISE_TAGS.has(t.name)) continue;
                  const ja = jaTag(t.name);
                  if (seenNames.has(ja)) continue;
                  const masterKey = data.genres.find((x) => x.name === ja)?.key;
                  seenNames.add(ja);
                  items.push({ name: ja, key: masterKey });
                }
                return items.map((it, i) => (
                  <span key={it.name}>
                    {i > 0 && " / "}
                    {it.key ? (
                      <FilterLink href={`/?genre=${encodeURIComponent(it.key)}`}>
                        {it.name}
                      </FilterLink>
                    ) : (
                      <span className="text-black/70">{it.name}</span>
                    )}
                  </span>
                ));
              })()}
            </dd>
          </dl>

          {manga.synopsis && (
            <p className="mt-6 text-sm leading-relaxed text-black/80">{manga.synopsis}</p>
          )}

          {manga.anilist_id && (
            <p className="mt-3 text-[11px] text-black/40">
              ジャンル 補助データ:{" "}
              <a
                href={`https://anilist.co/manga/${manga.anilist_id}`}
                target="_blank"
                rel="noopener nofollow"
                className="underline decoration-dotted underline-offset-2 hover:text-black/60"
              >
                AniList #{manga.anilist_id}
              </a>
            </p>
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
