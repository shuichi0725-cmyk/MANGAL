import Link from "next/link";
import { notFound } from "next/navigation";
import { DesignNav } from "@/lib/homeDesign";
import { loadAiReviews } from "@/lib/loadData";
import AiReviewSectionView from "@/components/AiReviewSection";

export async function generateMetadata({ params }: { params: Promise<{ setsu: string }> }) {
  const { setsu } = await params;
  return { alternates: { canonical: `/column-ai-league/${setsu}` } };
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
      <DesignNav current={11} />
      <div className="mx-auto max-w-xl px-5 pt-8">
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
