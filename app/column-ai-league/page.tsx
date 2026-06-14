import Link from "next/link";
import { DesignNav } from "@/lib/homeDesign";
import { loadAiReviews } from "@/lib/loadData";
import AiReviewSectionView from "@/components/AiReviewSection";

/** AI書評家リーグ: 同じ課題図書・同じ依頼文を複数の実在AIに渡し読み比べる週刊企画。
 *  最新節を表示し、 下に過去ログ(全節)へのリンク。 データ= data/seeds/ai-reviews.yml。
 *  [[ai_review_league_operation]] */
export default function AiLeaguePage() {
  const sections = loadAiReviews();
  const current = sections[0]; // 最新(setsu最大)
  const past = sections.slice(1);

  return (
    <div className="min-h-screen bg-[var(--color-bg)] pb-16">
      <DesignNav current={11} />
      <div className="mx-auto max-w-xl px-5 pt-8">
        {current ? (
          <>
            <AiReviewSectionView section={current} />
            {past.length > 0 && (
              <div className="mt-10">
                <h2 className="text-[13px] font-bold text-ink/70">過去ログ（これまでの課題図書）</h2>
                <ul className="mt-3 divide-y divide-[var(--color-line)] rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)]">
                  {past.map((s) => (
                    <li key={s.setsu}>
                      <Link
                        href={`/column-ai-league/${s.setsu}`}
                        className="spring-press flex items-center justify-between px-4 py-3"
                      >
                        <span className="text-[13px]">
                          <span className="text-ink/45">第{s.setsu - 1}節 ・ </span>
                          <span className="font-semibold">『{s.title}』</span>
                          <span className="text-ink/50"> {s.author}</span>
                        </span>
                        <span className="shrink-0 text-[11px] text-[var(--color-accent)]">{s.reviews.length}AI →</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        ) : (
          <p className="text-[13px] text-ink/60">準備中です。</p>
        )}
      </div>
    </div>
  );
}
