import Link from "next/link";
import { authorKeyFor } from "@/lib/authors";
import { hubHrefIfExists } from "@/lib/hubs";
import { notFound } from "next/navigation";
import RelatedWorks, { computeRelated } from "@/components/RelatedWorks";
import ShareButtons from "@/components/ShareButtons";
import VolumeRow from "@/components/VolumeRow";
// import ColorEditionNote from "@/components/ColorEditionNote"; // 帯=表示停止中(2026-08-02裁定。下のマウント跡を参照)
import ArtBookCard from "@/components/ArtBookCard";
import Badge from "@/components/ui/Badge";
import { ChipLink } from "@/components/ui/Chip";
import { yearStatusLabel } from "@/lib/format";
import { loadAllManga, loadTagI18n, loadWameiTags } from "@/lib/loadData";
import { coverUrl } from "@/lib/schema";
import { jaGenre, jaTag } from "@/lib/anilist-i18n";

export function generateStaticParams() {
  // ★機能蒸留ビルド(コードのみ本番反映= _deploy-feature.py): 漫画詳細66kは生成しない。
  //   placeholder 1頁のみ(= 同期側で manga/** は除外されるので本番に出ない)。
  if (process.env.MANGAL_FEATURE_BUILD === "1") return [{ slug: "_empty" }];
  const slugs = loadAllManga().manga.map((m) => ({ slug: m.slug }));
  // empty state (= データ準備中) でも build を通すための placeholder。
  // detail page 側で `manga not found` → 404 にフォールバックする。
  return slugs.length > 0 ? slugs : [{ slug: "_empty" }];
}

const SITE = "https://mangal-db.com";

/** ★SEO(2026-07-04): 頁別 title/description + canonical + OGP。66k頁が全て同一メタだった問題の根治 */
// ★SEO強化①②③(2026-08-06 チェンソーマンでテスト→リッチリザルト検証OK→ユーザGOで全展開):
//   ①title/descに巻数・完結・最新刊 ②JSON-LD強化+BreadcrumbList ③別題露出
const SEO_TEST = (_slug: string) => true;

/** 巻数・完結・最新刊のSEO文(①): 「全24巻で完結。最新刊24巻は2026年6月22日発売。」 */
function seoVolPhrase(m: import("@/lib/schema").Manga): { phrase: string; nVols: number; latest: { n: number | null; date: string } | null } {
  const nums = new Set<number>();
  for (const e of m.editions) for (const v of e.volumes) {
    if (v.number != null) nums.add(v.number);
  }
  const nVols = nums.size ? Math.max(...nums) : 0;
  // ★「最終巻N巻」は **巻番号が最大の巻** の日付で言う(2026-09-11 是正)。
  //   旧実装は「発売日が最も新しい巻」を latest にしていたため、後ろの巻の日付が
  //   年月精度や欠落だと途中巻が最終巻を名乗り「全14巻で完結。最終巻7巻は…」と食い違った
  //   (実測 2,749頁=6.1%。うち1,588頁は版が1つだけ=版混在ではなく日付の粗さが原因)。
  //   最大巻に完全な日付が無ければ **文ごと出さない**(嘘を言わない)。
  let latest: { n: number | null; date: string } | null = null;
  if (nVols) {
    for (const e of m.editions) for (const v of e.volumes) {
      if (v.number !== nVols) continue;
      const d = String(v.release_date ?? "");
      if (d && (!latest || d > latest.date)) latest = { n: nVols, date: d };
    }
  }
  const parts: string[] = [];
  if (nVols) parts.push(m.status === "completed" ? `全${nVols}巻で完結。` : `既刊${nVols}巻・連載中。`);
  if (latest && latest.n && latest.date.length >= 10) {
    const [y, mo, dy] = latest.date.split("-").map(Number);
    // ★2026-09-01 SEO(発売日の意図): 未来日は「発売予定」、完結作は「最終巻」の発売日を出す
    //   (「作品名 最新刊 発売日」「作品名 最終巻 いつ」のロングテール)。
    const todayJst = new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10);
    const verb = latest.date > todayJst ? "発売予定" : "発売";
    const label = m.status === "completed" ? "最終巻" : "最新刊";
    parts.push(`${label}${latest.n}巻は${y}年${mo}月${dy}日${verb}。`);
  }
  return { phrase: parts.join(""), nVols, latest };
}

/** ★catch/synopsis が無い頁の description を、頁が持つ**事実**で差別化する(④)。
 *  (2026-09-11 ユーザ相談「メタディスクリプションが同じのが多過ぎ?」→ 実測で判明)
 *
 *  旧実装の穴: desc = `${巻数フレーズ}${catch || synopsis || ""}` で、題名入りの定型文は
 *  **nVols===0 の時しか使われなかった**。巻はあるが catch が無い頁(全体の42.5%)は
 *  巻数フレーズだけが残り、しかも発売日が年月精度(旧作)だと日付の文も付かないため
 *  「全1巻で完結。」だけになる。実測 = 8,845頁がこの1文字列を共有、重複頁は全体の31.8%。
 *  → 事実(著者/ジャンル/掲載誌/出版社/刊行年)を足して固有率 72.1% → 100.0%(実測)。
 *  ★catch/synopsis が在る頁の挙動は一切変えない(57.5%は現状維持)。 */
function seoFactSentence(
  m: import("@/lib/schema").Manga,
  authors: string,
  genreNames: string[],
  publisherName: string | null,
  magazineName: string | null,
): string {
  const g = genreNames.slice(0, 2).join("・");
  // ★題名を必ず含める: 同じ著者×ジャンル×出版社×年の作品が固まるため(実測=赤塚不二夫で24頁)。
  const head = `『${m.title}』は${authors ? `${authors}による` : ""}${g ? `${g}漫画` : "漫画"}。`;
  const tail: string[] = [];
  // ★publisher/magazine は**キー**(shogakukan / big-comic)。必ず masters の表示名に直す
  //   (2026-09-11: 直前の実装がキーを素で出していた)。
  if (magazineName) tail.push(`${magazineName}連載`);
  if (publisherName) tail.push(`${publisherName}刊`);
  const yr = m.year_started
    ? `${m.year_started}年〜${m.year_ended && m.year_ended !== m.year_started ? `${m.year_ended}年` : ""}`
    : "";
  if (yr) tail.push(yr);
  const s = `${head}${tail.length ? `${tail.join("、")}。` : ""}`;
  // 余白がある時だけ、頁が何を載せているかを添える(埋まっていれば切り捨てられるだけなので付けない)
  return s.length <= 62 ? `${s}全巻の発売日・ISBN・書影を掲載。` : s;
}

/** ★④ description の余白を書誌で埋める(2026-09-14)。上限120字に対し実測で
 *  45%が80字未満・11%が60字未満だった(catch が短い頁)。catch を持つ頁にだけ、
 *  余白が大きい時に限って「掲載誌・出版社・刊行年」を足す。
 *  catch が無い頁は seoFactSentence が既に同じ事実を含むので**足さない**(重複回避)。 */
function seoBiblioTail(
  publisherName: string | null,
  magazineName: string | null,
  yearStarted?: number | null,
  yearEnded?: number | null,
): string {
  const t: string[] = [];
  if (magazineName) t.push(`${magazineName}連載`);
  if (publisherName) t.push(`${publisherName}刊`);
  if (yearStarted) t.push(`${yearStarted}年〜${yearEnded && yearEnded !== yearStarted ? `${yearEnded}年` : ""}`);
  return t.length ? `${t.join("、")}。` : "";
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const data = loadAllManga();
  const m = data.manga.find((x) => x.slug === slug);
  if (!m) return {};
  const authorList = (m.authors ?? []).map((a) => a.name).filter(Boolean);
  const authors = authorList.join("・");
  // ★title の著者は2名まで(2026-09-14)。アンソロジーで20名以上並び、実測で最長272文字の
  //   title が出ていた。日本語SERPの表示は概ね30〜35文字なので、長い著者列は「表示されない
  //   のに、稼ぎ頭の語(全N巻/発売日)を表示外へ押し出す」だけの純損失。
  const authorsShort = authorList.length > 2 ? `${authorList.slice(0, 2).join("・")}ほか` : authors;
  let title = `${m.title} 全巻一覧・発売日${authorsShort ? ` | ${authorsShort}` : ""}`;
  let desc = (m.catch || m.synopsis ||
    `${m.title}(${authors})の漫画全巻一覧・発売日・ISBN・出版社情報。楽天ブックス等の購入リンクつき。`)
    .slice(0, 120);
  if (SEO_TEST(m.slug)) {
    // ★①: 「何巻まで/完結/最新刊いつ」クエリ対応(2026-08-06 テスト=チェンソーマン)
    const sv = seoVolPhrase(m);
    // ★語順(2026-09-14): 旧 `題名 | 著者 - 全N巻の…` は、著者名の長さぶんだけ「全N巻」「発売日」が
    //   表示外に落ちていた(実測 中央値48文字=全頁が35文字超)。検索者のクリックを決める語を
    //   題名の直後へ出す。サフィックス「| 漫画・コミックのMANGAL」は裁定済のため維持
    //   ([[seo_title_suffix_decision]] A案)。
    if (sv.nVols) title = `${m.title} 全${sv.nVols}巻の発売日・全巻一覧${authorsShort ? ` | ${authorsShort}` : ""}`;
    // ★④(2026-09-11): catch/synopsis が無ければ「巻数フレーズだけ」で終わらせず事実文で埋める
    const genreNames = (m.genres ?? []).map((k) => data.genres.find((x) => x.key === k)?.name ?? k);
    const pubName = data.publishers.find((p) => p.key === m.publisher)?.name ?? null;
    const magName = data.magazines.find((x) => x.key === m.magazine)?.name ?? null;
    const hasText = Boolean(m.catch || m.synopsis);
    const body = m.catch || m.synopsis || seoFactSentence(m, authors, genreNames, pubName, magName);
    let d = `${sv.phrase}${body}`;
    // ★④: catch を持つ頁で余白が大きい時だけ書誌を足す(catch 無しは事実文に既に入っている)
    if (hasText && d.length < 84) d = `${d}${seoBiblioTail(pubName, magName, m.year_started, m.year_ended)}`;
    desc = d.slice(0, 120) || desc;
  }
  const cover = coverUrl(m);
  return {
    title,
    description: desc,
    alternates: { canonical: `${SITE}/manga/${m.slug}` },
    openGraph: {
      title,
      description: desc,
      url: `${SITE}/manga/${m.slug}`,
      siteName: "MANGAL",
      type: "book",
      // ★書影が無い頁(実測10,837件=15.7%)も既定OG画像で覆う(2026-09-14 SEO穴③)。
      //   ルートの openGraph.images を継承させるより、頁側で明示した方が上書き規則に依存しない。
      images: cover
        ? [{ url: cover }]
        : [{ url: `${SITE}/og-default.png`, width: 1200, height: 630, alt: "MANGAL — 日本の漫画データベース" }],
    },
    twitter: { card: "summary_large_image" },
  };
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

  // 表紙は volume.cover_url のみ。openBD/NDL fallback は使わない方針。
  // 1巻に無ければ表紙のある巻にフォールバック。
  const cover = coverUrl(manga);

  const publisher = data.publishers.find((p) => p.key === manga.publisher);
  const magazine = data.magazines.find((m) => m.key === manga.magazine);
  const tagI18n = loadTagI18n();
  const wamei = loadWameiTags();
  const demographic = data.demographics.find((d) => d.key === manga.demographic);

  // ★この作家の画集 = 作者名(作画家)一致のみ。 特定漫画への作品名一致紐付けはしない
  //   (特定漫画に紐付かない一般イラスト集も多く誤紐付けになるため)。 原作者には紐付けない。
  const authorNames = new Set(manga.authors.map((a) => a.name));
  const artistArtBooks = data.artBooks.filter((ab) => authorNames.has(ab.artist));

  // 関連作品 = シリーズ(題名前方一致) + 同作者。 説明と版リストの間(2026-06-12 ユーザ指定位置)
  const related = computeRelated(manga, data.manga);

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

  // ★構造化データ(JSON-LD): ComicSeries — 検索リッチ化(2026-07-04 SEO)
  const seoTest = SEO_TEST(manga.slug);
  const svMain = seoTest ? seoVolPhrase(manga) : null;
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "ComicSeries",
    name: manga.title,
    url: `https://mangal-db.com/manga/${manga.slug}`,
    ...(cover ? { image: cover } : {}),
    author: (manga.authors ?? []).map((a) => ({ "@type": "Person", name: a.name })),
    ...(publisher ? { publisher: { "@type": "Organization", name: publisher.name } } : {}),
    ...(manga.year_started ? { startDate: String(manga.year_started) } : {}),
    ...(manga.synopsis ? { description: String(manga.synopsis).slice(0, 200) } : {}),
    // ★②強化(テストゲート内): 巻数/終了年/ジャンル/別題/巻Book(先頭3+最新)
    ...(seoTest && svMain
      ? {
          ...(svMain.nVols ? { numberOfItems: svMain.nVols } : {}),
          ...(manga.status === "completed" && manga.year_ended ? { endDate: String(manga.year_ended) } : {}),
          ...(manga.genres?.length ? { genre: manga.genres } : {}),
          ...(manga.alternative_titles?.en ? { alternateName: [manga.alternative_titles.en, ...(manga.synonyms ?? [])] } : {}),
          workExample: (() => {
            const std = manga.editions.find((e) => e.type === "standard") ?? manga.editions[0];
            const vs = (std?.volumes ?? []).filter((v) => v.number != null && v.isbn13);
            const pick = [...vs.slice(0, 3), ...(vs.length > 3 ? [vs[vs.length - 1]] : [])];
            return pick.map((v) => ({
              "@type": "Book",
              name: `${manga.title} ${v.number}`,
              isbn: String(v.isbn13),
              position: v.number,
              ...(v.release_date ? { datePublished: String(v.release_date) } : {}),
              ...(publisher ? { publisher: { "@type": "Organization", name: publisher.name } } : {}),
              bookFormat: "https://schema.org/Paperback",
            }));
          })(),
        }
      : {}),
  };
  const breadcrumbLd = seoTest
    ? {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "ホーム", item: "https://mangal-db.com/" },
          ...(manga.genres?.[0]
            ? [{ "@type": "ListItem", position: 2, name: data.genres.find((g) => g.key === manga.genres![0])?.name ?? manga.genres[0], item: `https://mangal-db.com/genre/${manga.genres[0]}` }]
            : []),
          { "@type": "ListItem", position: manga.genres?.[0] ? 3 : 2, name: manga.title, item: `https://mangal-db.com/manga/${manga.slug}` },
        ],
      }
    : null;

  return (
    <div>
      {/* ★共通ナビヘッダー(2026-07-06 ユーザ要望: 「←ホームへ戻る」でなく他頁と同じヘッダーを出す) */}
      <div className="mx-auto max-w-4xl px-4 py-8 lg:mx-0">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      {breadcrumbLd && (
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbLd) }} />
      )}
      <div className="mt-6 grid gap-8">
        {/* ヒーロー表紙は撤去(2026-08-03 ユーザ指定: PCでタイトル左に大きく出て、
            書影の有無で段組がズレる。書影は巻コーフロー+ライトボックス拡大が担う) */}
        <div className="min-w-0">
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
          {manga.synonyms &&
            manga.synonyms.length > 0 &&
            (() => {
              // ★日本語別名と他言語を分離(2026-06-13)。 題名と同一の synonym は除外。
              const isJa = (s: string) => /[぀-ヿ㐀-鿿]/.test(s);
              const norm = (s: string) => s.replace(/\s+/g, "").toLowerCase();
              const titles = new Set(
                [manga.title, manga.title_kana, manga.alternative_titles?.en]
                  .filter(Boolean)
                  .map((s) => norm(s as string)),
              );
              const uniq = manga.synonyms.filter((s) => !titles.has(norm(s)));
              const ja = uniq.filter(isJa);
              const other = uniq.filter((s) => !isJa(s));
              return (
                <>
                  {ja.length > 0 && (
                    <p className="text-[11px] text-ink/45 mt-1 leading-relaxed">
                      別名: {ja.join(" / ")}
                    </p>
                  )}
                  {other.length > 0 && (
                    <p className="text-[11px] text-ink/45 mt-1 leading-relaxed">
                      他言語: {other.join(" / ")}
                    </p>
                  )}
                </>
              );
            })()}

          <dl className="mt-6 grid grid-cols-[5.5em_1fr] gap-y-2.5 items-start text-sm">
            <dt className="font-semibold text-ink/65 pt-1">出版年</dt>
            <dd className="flex flex-wrap gap-1.5">
              {/* ★SEO(2026-09-04): 年別/出版社別/連載誌別ハブ(/year /publisher /magazine)が在る時はそこへ。
                  無い時(閾値未満)は従来の /browse? フィルタへフォールバック。 */}
              <FilterLink
                href={
                  hubHrefIfExists("year", manga.year_started) ??
                  `/browse?yearMin=${manga.year_started}&yearMax=${manga.year_started}`
                }
              >
                {yearStatusLabel(manga)}
              </FilterLink>
            </dd>
            <dt className="font-semibold text-ink/65 pt-1">著者</dt>
            <dd className="flex flex-wrap gap-1.5">
              {manga.authors.map((a) => {
                {/* ★著者静的ページへ(2026-08-10 SEO⑤)。romaji無し著者のみ従来のクエリ絞込へ */}
                const ak = authorKeyFor(a.name);
                return (
                  <span key={a.name}>
                    <FilterLink href={ak ? `/author/${ak}` : `/browse?author=${encodeURIComponent(a.name)}`}>
                      {a.name}
                    </FilterLink>
                  </span>
                );
              })}
            </dd>
            {manga.original_authors.length > 0 && (
              <>
                <dt className="font-semibold text-ink/65 pt-1">原作</dt>
                <dd className="flex flex-wrap gap-1.5">
                  {manga.original_authors.map((a) => {
                    const ak = authorKeyFor(a.name);
                    return (
                    <span key={a.name}>
                          <FilterLink
                        href={ak ? `/author/${ak}` : `/browse?originalAuthor=${encodeURIComponent(a.name)}`}
                      >
                        {a.name}
                      </FilterLink>
                    </span>
                    );
                  })}
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
              <FilterLink
                href={hubHrefIfExists("publisher", manga.publisher) ?? `/browse?publisher=${encodeURIComponent(manga.publisher)}`}
              >
                {publisher?.name ?? manga.publisher}
              </FilterLink>
            </dd>
            {magazine && (
              <>
                <dt className="font-semibold text-ink/65 pt-1">連載誌</dt>
                <dd className="flex flex-wrap gap-1.5">
                  <FilterLink
                    href={hubHrefIfExists("magazine", magazine.key) ?? `/browse?magazine=${encodeURIComponent(magazine.key)}`}
                  >
                    {magazine.name}
                  </FilterLink>
                </dd>
              </>
            )}
            {manga.demographic && (
              <>
                <dt className="font-semibold text-ink/65 pt-1">分野</dt>
                <dd className="flex flex-wrap gap-1.5">
                  <FilterLink href={`/browse?demographic=${encodeURIComponent(manga.demographic)}`}>
                    {demographic?.name ?? manga.demographic}
                  </FilterLink>
                </dd>
              </>
            )}
            {(() => {
              // ★ジャンル(= masterジャンル + Wiki/AniList/AI 由来。 filter link 付き)と
              //   要素(= AniListタグの和訳。 filter 無しの素チップ)を分離。
              //   ・ジャンル欄 = master genres ∪ genres_anilist(jaGenre)
              //   ・要素欄    = tags の和訳。 除外= ①Demographic(分野欄に既出) ②スポーツ競技
              //                (野球/サッカー以外は不採用) ③ジャンル名と完全一致(畳む) ④ノイズtag
              const genreNames = new Set<string>();
              const genreItems: Array<{ name: string; key?: string }> = [];
              for (const g of manga.genres) {
                const name = data.genres.find((x) => x.key === g)?.name ?? g;
                if (genreNames.has(name)) continue;
                genreNames.add(name);
                genreItems.push({ name, key: g });
              }
              for (const g of manga.genres_anilist ?? []) {
                const ja = jaGenre(g);
                if (genreNames.has(ja)) continue;
                const masterKey = data.genres.find((x) => x.name === ja)?.key;
                genreNames.add(ja);
                genreItems.push({ name: ja, key: masterKey });
              }

              const NOISE_TAGS = new Set([
                "Heterosexual",
                "Male Protagonist",
                "Female Protagonist",
                "Primarily Adult Cast",
                "Primarily Child Cast",
                "Primarily Teen Cast",
              ]);
              const elemNames = new Set<string>();
              const elemItems: string[] = [];
              for (const t of manga.tags ?? []) {
                if (t.category === "Demographic") continue; // 分野欄に既出
                if (t.category.startsWith("Theme-Game-Sport")) continue; // スポーツ競技は不採用
                if (NOISE_TAGS.has(t.name)) continue;
                // 和訳がある tag のみ採用(英語のまま出さない)。 tag-i18n.yml 優先、 旧辞書 fallback。
                const fromYml = tagI18n[t.name]?.ja;
                const fromDict = jaTag(t.name);
                let ja = fromYml ?? (fromDict !== t.name ? fromDict : undefined);
                if (!ja) {
                  // 和名タグ(楽天あらすじAI付与)= wamei-tags.yml のゲートで通す(2026-08-11)
                  if (wamei.exclude.has(t.name)) continue;
                  if (wamei.alias[t.name]) ja = wamei.alias[t.name];
                  else if (wamei.allow.has(t.name)) ja = t.name;
                  else continue;
                }
                if (genreNames.has(ja)) continue; // ジャンル名と完全一致 → 畳む
                if (elemNames.has(ja)) continue;
                elemNames.add(ja);
                elemItems.push(ja);
              }

              return (
                <>
                  <dt className="font-semibold text-ink/65 pt-1">ジャンル</dt>
                  <dd className="flex flex-wrap gap-1.5">
                    {genreItems.map((it) =>
                      it.key ? (
                        // ★SEO(2026-09-04): /browse?genre= はクライアント描画の行き止まり。 実在する
                        //   ジャンル面 /genre/[key] へ向け、 66k頁→32ハブの内部リンクにする(元は可視0本)。
                        <ChipLink key={it.name} href={`/genre/${encodeURIComponent(it.key)}`}>
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
                    )}
                  </dd>
                  {elemItems.length > 0 && (
                    <>
                      <dt className="font-semibold text-ink/65 pt-1">要素</dt>
                      <dd className="flex flex-wrap gap-1.5">
                        {elemItems.map((name) => (
                          <ChipLink
                            key={name}
                            href={`/browse?theme=${encodeURIComponent(name)}`}
                          >
                            {name}
                          </ChipLink>
                        ))}
                      </dd>
                    </>
                  )}
                </>
              );
            })()}
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

          {/* 共有(X/LINE/OS共有) = 説明の直後(2026-07-12 ユーザ指定位置)。
              ★2026-09-15 関連作品を巻セクションの下へ移した後も**共有はここに据え置き**(ユーザ裁定):
              共有は本題(巻)に触れる前でも押される導線で、深い位置に下げると押されなくなるため。 */}
          <ShareButtons title={manga.title} url={`${SITE}/manga/${manga.slug}`} />

          {/* 電子カラー版帯=表示停止のまま(2026-08-02 ユーザ裁定「勝手につけられた」)。
              2026-08-12 ホームのカラー版コーナー新設で color-editions.json を再充填したため、
              データ側で止まっていた本帯が復活しないようマウント自体を外す(再開はユーザGOで)。
          <ColorEditionNote slug={manga.slug} /> */}

          <VolumeRow manga={manga} />

          {/* ★関連作品 = 巻セクション(各版の最後は「📱電子書籍で買う」)の**下**
              (2026-09-15 ユーザ裁定で旧位置=「説明と巻の間」から移動)。
              理由: 頁が約束しているのは「全N巻の発売日・全巻一覧」で、検索から来た読者が
              最初に見たいのは巻。関連作品は読み終えた後の「次の一手」なので本題の後ろに置く。
              ★関連作品の閲覧数が落ちるのは承知のうえ(ユーザ確認済)。
              ★SEOへの影響は無い: Googlebotは全HTMLを読むので内部リンクの価値は頁内位置に依らない。 */}
          <RelatedWorks items={related} />

          {/* ★③別題露出(テストゲート内 2026-08-06): 英題・略称・他言語題を検索エンジン可視に */}
          {seoTest && (manga.alternative_titles?.en || manga.synonyms?.length) && (
            <div className="mt-6 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-ink/45">
              <span className="font-semibold text-ink/40">別題</span>
              {[manga.alternative_titles?.en, ...(manga.synonyms ?? [])].filter(Boolean).map((t) => (
                <span key={String(t)}>{String(t)}</span>
              ))}
            </div>
          )}

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
          ← ホームへ戻る
        </Link>
      </div>
      </div>
    </div>
  );
}
