"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AiReviewSectionView from "@/components/AiReviewSection";
import type { AiReviewSection } from "@/lib/loadData";

import { visibleSectionCount } from "@/lib/aiLeagueSchedule";

/** 週次順出し(2026-07-03): 第1節から毎週日曜に1節ずつ公開。
 *  ★公開週の計算は lib/aiLeagueSchedule に一本化(2026-07-27。teaserとの重複実装が
 *  節番号二重系・週+2ズレの2バグを生んだため、以後この式の再実装は禁止)。 */
export default function AiLeagueClient({
  sections,
  initialNow,
}: {
  sections: AiReviewSection[];
  /** ★サーバー(ビルド時)の現在時刻。SSRの初期描画に使う(2026-09-15 SEO穴の是正)。 */
  initialNow: number;
}) {
  // ★旧実装は `useState<number|null>(null)` + `if (now === null) return null` で、
  //   **サーバー描画では必ず null を返していた** = 静的HTMLが空(h1もh2も本文もゼロ)。
  //   クローラーには空ページに見えていた([[browse_ssr_shell_and_seo]] と同じ型)。
  //   ★直し方: サーバーのビルド時刻を初期値として受け取り、初回クライアント描画でも
  //   同じ値を使う(= hydration mismatch なし)。マウント後に実時刻へ更新するので
  //   「再ビルド不要で毎週1節ずつ増える」性質は従来どおり保たれる。
  const [now, setNow] = useState<number>(initialNow);
  useEffect(() => setNow(Date.now()), []);
  const visibleCount = visibleSectionCount(now);
  const visible = sections.filter((s) => s.setsu <= visibleCount).sort((a, b) => b.setsu - a.setsu);
  const current = visible[0];
  const past = visible.slice(1);
  if (!current) return <p className="text-[13px] text-ink/60">準備中です。</p>;
  return (
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
                    <span className="text-ink/45">第{s.setsu}節 ・ </span>
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
  );
}
