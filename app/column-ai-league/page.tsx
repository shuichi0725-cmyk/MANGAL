import { DesignNav } from "@/lib/homeDesign";
import { loadAiReviews } from "@/lib/loadData";
import AiLeagueClient from "./AiLeagueClient";

export const metadata = { alternates: { canonical: "/column-ai-league" } };

/** AI書評家リーグ: 同じ課題図書・同じ依頼文を複数の実在AIに渡し読み比べる週刊企画。
 *  ★週次順出し(2026-07-03): 第1節から毎週日曜に1節ずつ公開(client計算=再ビルド不要)。
 *  データ= data/seeds/ai-reviews.yml。 [[ai_review_league_operation]] */
export default function AiLeaguePage() {
  const sections = loadAiReviews();
  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-16">
      <DesignNav current={11} />
      <div className="mx-auto max-w-xl px-5 pt-8">
        <AiLeagueClient sections={sections} />
      </div>
    </div>
  );
}
