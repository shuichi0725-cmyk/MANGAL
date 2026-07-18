import Link from "next/link";
import { notFound } from "next/navigation";
import CoverImage from "@/components/CoverImage";
import Badge from "@/components/ui/Badge";
import { loadAllManga } from "@/lib/loadData";
import { buildAmazonUrlForArtBook } from "@/lib/amazon";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return { alternates: { canonical: `/art-books/${slug}` } };
}

export function generateStaticParams() {
  const slugs = loadAllManga().artBooks.map((a) => ({ slug: a.slug }));
  // empty state (= データ準備中) でも build を通すための placeholder。
  return slugs.length > 0 ? slugs : [{ slug: "_empty" }];
}

/**
 * 画集の作品ページ (= 漫画 /manga/[slug] と同構造の軽量版)。
 * ★画集はあらすじ/ジャンルを持たないので、 ジャンルは「画集」固定タグのみ・あらすじ無し。
 *   分かる情報(作画家・出版社・出版年・巻ISBN)を出し、 巻ごとに購入リンク。
 */
export default async function ArtBookDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const { artBooks } = loadAllManga();
  const ab = artBooks.find((a) => a.slug === slug);
  if (!ab) notFound();

  const tag = process.env.NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG ?? "";
  const locale = process.env.NEXT_PUBLIC_AMAZON_LOCALE ?? "jp";
  const cover = ab.volumes[0]?.cover_url ?? null;

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <Link href="/?artBooks=true" className="text-sm text-ink/60 hover:text-ink">
        ← 画集一覧へ戻る
      </Link>
      <div className="mt-6 grid gap-8 md:grid-cols-[260px_1fr]">
        <div className="relative aspect-[2/3] bg-[var(--color-surface-2)] rounded overflow-hidden">
          {cover ? (
            <CoverImage src={cover} alt={`${ab.title} 表紙`} sizes="260px" size="detail" />
          ) : (
            <span className="flex h-full items-center justify-center text-5xl text-ink/15" aria-hidden="true">
              🎨
            </span>
          )}
        </div>
        <div>
          <div className="flex items-start gap-3 flex-wrap">
            <h1 className="text-2xl md:text-3xl font-bold">{ab.title}</h1>
            <span className="mt-2">
              <Badge tone="accent">画集</Badge>
            </span>
          </div>
          <p className="text-sm text-ink/60 mt-1">{ab.title_kana}</p>

          <dl className="mt-6 grid grid-cols-[5.5em_1fr] gap-y-2.5 items-start text-sm">
            <dt className="font-semibold text-ink/65 pt-1">作画家</dt>
            <dd className="flex flex-wrap gap-1.5">
              <Link
                href={`/browse?artBooks=true&q=${encodeURIComponent(ab.artist)}`}
                className="inline-flex items-center rounded-[var(--radius-tag)] border border-[var(--color-line)] bg-[var(--color-surface)] px-2.5 py-1 text-[13px] font-medium text-ink/85 transition duration-100 hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] active:scale-[0.94]"
              >
                {ab.artist}
              </Link>
            </dd>
            {ab.publisher && (
              <>
                <dt className="font-semibold text-ink/65 pt-1">出版社</dt>
                <dd className="pt-1 text-ink/85">{ab.publisher}</dd>
              </>
            )}
            {ab.year && (
              <>
                <dt className="font-semibold text-ink/65 pt-1">出版年</dt>
                <dd className="pt-1 text-ink/85">{ab.year}年</dd>
              </>
            )}
            <dt className="font-semibold text-ink/65 pt-1">ジャンル</dt>
            <dd className="flex flex-wrap gap-1.5">
              <span className="inline-flex items-center rounded-[var(--radius-tag)] px-3 py-1.5 text-xs font-medium bg-[var(--color-surface-2)] border border-[var(--color-line)] text-ink/55">
                画集
              </span>
            </dd>
          </dl>

          {/* 巻 + 購入リンク (= 漫画 VolumeRow 相当の軽量版) */}
          <div className="mt-8">
            <p className="text-xs font-semibold text-ink/70 mb-2">巻</p>
            <ul className="space-y-1.5">
              {ab.volumes.map((v, i) => {
                const href = buildAmazonUrlForArtBook(ab, { associateTag: tag, locale }, v);
                return (
                  <li
                    key={v.isbn13 ?? i}
                    className="flex items-center justify-between gap-3 rounded-card border border-[var(--color-line)] bg-[var(--color-surface)] px-3 py-2 text-sm"
                  >
                    <span className="text-ink/80">
                      {ab.volumes.length > 1 ? `第${v.number}巻` : "本体"}
                      {v.release_date ? ` ・ ${v.release_date}` : ""}
                      {v.isbn13 ? ` ・ ${v.isbn13}` : ""}
                    </span>
                    <a
                      href={href}
                      target="_blank"
                      rel="nofollow sponsored noopener"
                      className="shrink-0 text-xs font-semibold text-[var(--color-accent)] hover:underline"
                    >
                      Amazonで見る →
                    </a>
                  </li>
                );
              })}
            </ul>
          </div>

          {ab.wikidata_qid && (
            <div className="mt-8 text-[11px] text-ink/45">
              <span className="font-semibold text-ink/40">外部リンク</span>{" "}
              <a
                href={`https://www.wikidata.org/wiki/${ab.wikidata_qid}`}
                target="_blank"
                rel="noopener nofollow"
                className="underline decoration-dotted underline-offset-2 hover:text-[var(--color-accent)]"
              >
                作画家: Wikidata {ab.wikidata_qid}
              </a>
            </div>
          )}
        </div>
      </div>

      <div className="mt-10 border-t border-[var(--color-line)] pt-6 text-center">
        <Link
          href="/?artBooks=true"
          className="tactile-chip inline-flex items-center rounded-card px-4 py-2 text-sm font-medium active:scale-[0.96] transition"
        >
          ← 画集一覧へ戻る
        </Link>
      </div>
    </div>
  );
}
