import { loadAiReviews } from "@/lib/loadData";
import AiLeagueClient from "./AiLeagueClient";

export const metadata = {
  // ★title/description を明示(2026-09-15): 旧実装は canonical しか無く、既定title
  //   「MANGAL — 日本の漫画データベース」のままだった = 他頁と同一のメタ情報になる。
  //   ★説明文は「今週の課題図書」に寄せない(週で変わる=canonical頁の説明が毎週ぶれる)。
  title: "AI書評家リーグ — 同じ漫画を5つのAIが読み比べ",
  description:
    "同じ課題図書と同じ依頼文を複数の実在AIに渡し、書評を読み比べる週刊企画。" +
    "毎週日曜に1節ずつ公開。過去の課題図書もすべて読めます。",
  alternates: { canonical: "/column-ai-league" },
};

/** AI書評家リーグ: 同じ課題図書・同じ依頼文を複数の実在AIに渡し読み比べる週刊企画。
 *  ★週次順出し(2026-07-03): 第1節から毎週日曜に1節ずつ公開(client計算=再ビルド不要)。
 *  ★2026-09-15: サーバーのビルド時刻を initialNow として渡し、**静的HTMLにも中身が入る**ように
 *  した(旧実装はクライアント時刻待ちでサーバー描画が空=クローラーに空ページだった)。
 *  クライアントはマウント後に実時刻で描き直すので、再ビルド不要の性質は変わらない。
 *  データ= data/seeds/ai-reviews.yml。 [[ai_review_league_operation]] */
export default function AiLeaguePage() {
  const sections = loadAiReviews();
  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-16">
      <div className="mx-auto max-w-xl px-5 pt-8 lg:max-w-[860px] lg:mx-0">
        <AiLeagueClient sections={sections} initialNow={Date.now()} />
      </div>
    </div>
  );
}
