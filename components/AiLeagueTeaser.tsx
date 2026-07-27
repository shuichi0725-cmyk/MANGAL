"use client";

import { useEffect, useState } from "react";
import { visibleSectionCount } from "@/lib/aiLeagueSchedule";

/** ホームのAI書評リーグteaser: 週次順出しと同じ計算で「今週の課題図書」を表示。
 *  親(server)からslim情報のみ受ける(本文は渡さない=軽量)。
 *  ★公開週の計算は lib/aiLeagueSchedule に一本化(重複実装が過去2バグの根因)。 */
export type TeaserSection = { setsu: number; title: string; models: string[] };

export default function AiLeagueTeaser({ sections }: { sections: TeaserSection[] }) {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => setNow(Date.now()), []);
  const visibleCount = now === null ? 1 : visibleSectionCount(now);
  const cur = sections.filter((s) => s.setsu <= visibleCount).sort((a, b) => b.setsu - a.setsu)[0] ?? sections[0];
  if (!cur) return null;
  return (
    <>
      <div className="border-b-2 border-ink/75 px-4 pb-2 pt-3">
        <p className="text-[9px] font-bold tracking-[0.25em] text-[var(--color-accent)]">AI書評家リーグ ・ 週刊 ・ 完結作だけ、ネタバレなし</p>
        <h2 className="mt-1 text-[16px] font-black leading-snug">
          今週の課題図書『{cur.title}』を、AI書評家{cur.models.length}人が読んだら。
        </h2>
      </div>
      <div className="px-4 py-3">
        <div className="flex flex-wrap gap-1.5 text-[10px]">
          {cur.models.map((n) => (
            <span key={n} className="rounded-full border border-[var(--color-line)] bg-[var(--color-surface-2)] px-2 py-0.5 font-semibold text-ink/70">{n}</span>
          ))}
        </div>
        <p className="mt-2 text-[12px] leading-relaxed text-ink/75">
          同じ本、同じ依頼文——それでも書評はこんなに違う。実在の各社AIに同じお題を渡して読み比べ。
        </p>
        <p className="mt-2 text-right text-[11px] font-semibold text-[var(--color-accent)]">{cur.models.length}本読み比べる →</p>
      </div>
    </>
  );
}
