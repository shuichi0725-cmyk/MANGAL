"use client";

import { useEffect, useState } from "react";

/** ホームのAI書評リーグteaser: 週次順出しと同じ計算で「今週の課題図書」を表示。
 *  親(server)からslim情報のみ受ける(本文は渡さない=軽量)。 */
const EPOCH_SUNDAY_JST = Date.UTC(2026, 6, 5) - 9 * 3600_000; // AiLeagueClientと同一

export type TeaserSection = { setsu: number; title: string; models: string[] };

export default function AiLeagueTeaser({ sections }: { sections: TeaserSection[] }) {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => setNow(Date.now()), []);
  const weeks = now === null ? 0 : Math.floor((now - EPOCH_SUNDAY_JST) / (7 * 86400_000));
  // ★AiLeagueClient と同一式(weeks+1)に統一。旧 weeks+2 はコラム面より1節先の課題図書を
  //   予告してしまい「トップ=約ネバ/コラム=鬼滅」のズレを毎週再生産していた(2026-07-27ユーザ発見)
  const visibleCount = Math.max(1, weeks + 1);
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
