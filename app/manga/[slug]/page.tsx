import Link from "next/link";
import { notFound } from "next/navigation";
import CoverImage from "@/components/CoverImage";
import VolumeRow from "@/components/VolumeRow";
import ArtBookCard from "@/components/ArtBookCard";
import Badge from "@/components/ui/Badge";
import { ChipLink } from "@/components/ui/Chip";
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

  // ★この作家の画集 = 作者名(作画家)一致のみ。 特定漫画への作品名一致紐付けはしない
  //   (特定漫画に紐付かない一般イラスト集も多く誤紐付けになるため)。 原作者には紐付けない。
  const authorNames = new Set(manga.authors.map((a) => a.name));
  const artistArtBooks = data.artBooks.filter((ab) => authorNames.has(ab.artist));

  // 各メタ項目をクリックすると、フィルタ済みトップページへ飛ぶ。
  // 押せる値は「アウトライン枠タグ」(= ジャンルの淡塗りチップとは別系統、 hoverでaccent)。
  const FilterLink = ({ href, children }: { href: string; children: React.ReactNode }) => (
    <Link
      href={href}
      className="inline-flex items-center rounded-[var(--radius-tag)] border border-[var(--color-line)] bg-[var(--color-surface)] px-2.5 py-1 text-[13px] font-medium text-ink/85 transition duration-100 hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] active:scale-[0.94] active:bg-[var(--color-surface-2)] active:border-[var(--color-accent)]"
    >
      {children}
    </Link>
  );

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <Link href="/" className="text-sm text-ink/60 hover:text-ink">
        ← 一覧へ戻る
      </Link>
      <div className={`mt-6 grid gap-8 ${cover ? "md:grid-cols-[260px_1fr]" : ""}`}>
        {cover && (
          <div className="relative aspect-[2/3] bg-[var(--color-surface-2)] rounded overflow-hidden">
            <CoverImage src={cover} alt={`${manga.title} 1巻 表紙`} sizes="260px" size="detail" />
          </div>
        )}
        <div>
          <div className="flex items-start gap-3 flex-wrap">
            <h1 className="text-2xl md:text-3xl font-bold">{manga.title}</h1>
            {manga.anime_adapted && (
              <span className="mt-2">
                <Badge tone="warm">
                  アニメ化
                  {manga.anime_first_year ? ` ${manga.anime_first_year}` : ""}
                </Badge>
              </span>
            )}
          </div>
          {/* 副題 (= MADB の ` : ` 右側、 ない時は β 案で空白行を保持) */}
          <p className="text-base text-ink/75 mt-1 min-h-[1.5rem]">
            {manga.subtitle ?? " "}
          </p>
          <p className="text-sm text-ink/60 mt-1">
            {manga.title_kana}
            {manga.subtitle_kana ? ` : ${manga.subtitle_kana}` : ""}
          </p>

          {manga.alternative_titles && (
            <p className="text-xs text-ink/55 mt-1.5">
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
            <p className="text-[11px] text-ink/45 mt-1 leading-relaxed">
              他言語・別名: {manga.synonyms.join(" / ")}
            </p>
          )}

          <dl className="mt-6 grid grid-cols-[5.5em_1fr] gap-y-2.5 items-start text-sm">
            <dt className="font-semibold text-ink/65 pt-1">出版年</dt>
            <dd className="flex flex-wrap gap-1.5">
              <FilterLink
                href={`/?yearMin=${manga.year_started}&yearMax=${manga.year_started}`}
              >
                {yearStatusLabel(manga)}
              </FilterLink>
            </dd>
            <dt className="font-semibold text-ink/65 pt-1">著者</dt>
            <dd className="flex flex-wrap gap-1.5">
              {manga.authors.map((a) => (
                <span key={a.name}>
                  <FilterLink href={`/?author=${encodeURIComponent(a.name)}`}>
                    {a.name}
                  </FilterLink>
                </span>
              ))}
            </dd>
            {manga.original_authors.length > 0 && (
              <>
                <dt className="font-semibold text-ink/65 pt-1">原作</dt>
                <dd className="flex flex-wrap gap-1.5">
                  {manga.original_authors.map((a) => (
                    <span key={a.name}>
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
            {manga.credits.length > 0 && (
              <>
                <dt className="font-semibold text-ink/65 pt-1">その他</dt>
                <dd className="flex flex-wrap gap-x-3 gap-y-1 text-sm text-ink/70">
                  {Object.entries(
                    manga.credits.reduce<Record<string, string[]>>((acc, c) => {
                      (acc[c.role] = acc[c.role] || []).push(c.name);
                      return acc;
                    }, {}),
                  ).map(([role, names]) => (
                    <span key={role}>
                      <span className="text-ink/50">{role}: </span>
                      {names.join(" / ")}
                    </span>
                  ))}
                </dd>
              </>
            )}
            <dt className="font-semibold text-ink/65 pt-1">出版社</dt>
            <dd className="flex flex-wrap gap-1.5">
              <FilterLink href={`/?publisher=${encodeURIComponent(manga.publisher)}`}>
                {publisher?.name ?? manga.publisher}
              </FilterLink>
            </dd>
            {magazine && (
              <>
                <dt className="font-semibold text-ink/65 pt-1">連載誌</dt>
                <dd className="flex flex-wrap gap-1.5">
                  <FilterLink href={`/?magazine=${encodeURIComponent(magazine.key)}`}>
                    {magazine.name}
                  </FilterLink>
                </dd>
              </>
            )}
            <dt className="font-semibold text-ink/65 pt-1">分野</dt>
            <dd className="flex flex-wrap gap-1.5">
              <FilterLink href={`/?demographic=${encodeURIComponent(manga.demographic)}`}>
                {demographic?.name ?? manga.demographic}
              </FilterLink>
            </dd>
            <dt className="font-semibold text-ink/65 pt-1">ジャンル</dt>
            <dd className="flex flex-wrap gap-1.5">
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
                return items.map((it) =>
                  it.key ? (
                    <ChipLink key={it.name} href={`/?genre=${encodeURIComponent(it.key)}`}>
                      {it.name}
                    </ChipLink>
                  ) : (
                    <span
                      key={it.name}
                      className="inline-flex items-center rounded-[var(--radius-tag)] px-3 py-1.5 text-xs font-medium bg-[var(--color-surface-2)] border border-[var(--color-line)] text-ink/55"
                    >
                      {it.name}
                    </span>
                  ),
                );
              })()}
            </dd>
          </dl>

          {manga.synopsis && (
            <p className="mt-6 text-sm leading-relaxed text-ink/80">{manga.synopsis}</p>
          )}

          {manga.awards && manga.awards.length > 0 && (
            <div className="mt-6">
              <p className="text-xs font-semibold text-ink/70 mb-2">受賞歴</p>
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

          {/* 外部リンク = 存在するものだけ作品/著者を明示して下部に集約。
              ・作品 AniList = anilist_id(連携済み作品のみ)
              ・作品 Wikidata = work_wikidata_qid(AniList漫画ID経由で一意取得)
              ・著者 Wikidata = wikidata_qid(= series.qid は著者QIDなので「著者」と明示) */}
          {(manga.anilist_id || manga.work_wikidata_qid || manga.wikidata_qid) && (
            <div className="mt-8 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-ink/45">
              <span className="font-semibold text-ink/40">外部リンク</span>
              {manga.anilist_id && (
                <a
                  href={`https://anilist.co/manga/${manga.anilist_id}`}
                  target="_blank"
                  rel="noopener nofollow"
                  className="underline decoration-dotted underline-offset-2 hover:text-[var(--color-accent)]"
                >
                  作品: AniList #{manga.anilist_id}
                </a>
              )}
              {manga.work_wikidata_qid && (
                <a
                  href={`https://www.wikidata.org/wiki/${manga.work_wikidata_qid}`}
                  target="_blank"
                  rel="noopener nofollow"
                  className="underline decoration-dotted underline-offset-2 hover:text-[var(--color-accent)]"
                >
                  作品: Wikidata {manga.work_wikidata_qid}
                </a>
              )}
              {manga.wikidata_qid && (
                <a
                  href={`https://www.wikidata.org/wiki/${manga.wikidata_qid}`}
                  target="_blank"
                  rel="noopener nofollow"
                  className="underline decoration-dotted underline-offset-2 hover:text-[var(--color-accent)]"
                >
                  著者: Wikidata {manga.wikidata_qid}
                </a>
              )}
            </div>
          )}
        </div>
      </div>

      {/* この作家の画集 (= 作画家一致のみ。 作品単位でなく作家単位で出す) */}
      {artistArtBooks.length > 0 && (
        <section className="mt-12 border-t border-[var(--color-line)] pt-8">
          <h2 className="text-base font-semibold text-ink mb-3">この作家の画集</h2>
          <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {artistArtBooks.map((ab) => (
              <li key={ab.slug}>
                <ArtBookCard artBook={ab} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* 巻リスト末尾の戻る導線(上部のリンクと同機能、 下までスクロールしても戻れる) */}
      <div className="mt-10 border-t border-[var(--color-line)] pt-6 text-center">
        <Link
          href="/"
          className="tactile-chip inline-flex items-center rounded-card px-4 py-2 text-sm font-medium active:scale-[0.96] transition"
        >
          ← 一覧へ戻る
        </Link>
      </div>
    </div>
  );
}
