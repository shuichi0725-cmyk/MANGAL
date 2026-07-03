"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AiReviewSectionView from "@/components/AiReviewSection";
import type { AiReviewSection } from "@/lib/loadData";

/** 週次順出し(2026-07-03): 第1節から毎週日曜に1節ずつ公開。
 *  EPOCH=第1節の公開日曜。 visible = 経過週+1 (静的ビルドでも client 計算で進む)。 */
const EPOCH_SUNDAY_JST = Date.UTC(2026, 6, 5) - 9 * 3600_000; // 2026-07-05 00:00 JST

export default function AiLeagueClient({ sections }: { sections: AiReviewSection[] }) {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => setNow(Date.now()), []);
  if (now === null) return null;
  const weeks = Math.floor((now - EPOCH_SUNDAY_JST) / (7 * 86400_000));
  const visibleCount = Math.max(1, weeks + 2); // 公開前=1節のみ、EPOCH日曜で2節目…
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
