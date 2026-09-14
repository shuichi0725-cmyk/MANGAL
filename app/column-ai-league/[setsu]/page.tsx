import Link from "next/link";
import { notFound } from "next/navigation";
import { loadAiReviews } from "@/lib/loadData";
import AiReviewSectionView from "@/components/AiReviewSection";

export async function generateMetadata({ params }: { params: Promise<{ setsu: string }> }) {
  const { setsu } = await params;
  // ★節ごとに固有の title/description を出す(2026-09-15)。旧実装は canonical だけで、
  //   全節が既定title「MANGAL — 日本の漫画データベース」を共有していた
  //   (= Bing Webmaster の「同一のメタディスクリプションが多すぎる」に効いていた層)。
  const s = loadAiReviews().find((x) => String(x.setsu) === setsu);
  if (!s) return { alternates: { canonical: `/column-ai-league/${setsu}` } };
  const n = s.reviews.length;
  return {
    title: `『${s.title}』を${n}つのAIが読んだら — AI書評家リーグ第${s.setsu}節`,
    description:
      `${s.author}『${s.title}』を課題図書に、${n}つの実在AIが同じ依頼文で書評を書きました。` +
      `読み比べると、AIごとに何を面白がるかが違います。AI書評家リーグ第${s.setsu}節。`,
    alternates: { canonical: `/column-ai-league/${setsu}` },
  };
}

/** AI書評家リーグ 過去ログ個別ページ(節ごと)。 三世代の過去ログと同様。 */
export function generateStaticParams() {
  const params = loadAiReviews().map((s) => ({ setsu: String(s.setsu) }));
  return params.length > 0 ? params : [{ setsu: "_empty" }];
}

export default async function AiLeagueArchivePage({
  params,
}: {
  params: Promise<{ setsu: string }>;
}) {
  const { setsu } = await params;
  const section = loadAiReviews().find((s) => String(s.setsu) === setsu);
  if (!section) notFound();

  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-16">
      <div className="mx-auto max-w-xl px-5 pt-8 lg:max-w-[860px] lg:mx-0">
        <Link href="/column-ai-league" className="spring-press text-[12px] text-[var(--color-accent)]">
          ← AI書評家リーグ（最新・過去ログ一覧）
        </Link>
        <div className="mt-3">
          <AiReviewSectionView section={section} />
        </div>
      </div>
    </div>
  );
}
