import Link from "next/link";
import type { Metadata } from "next";
import view from "@/data/anime-seasons-view.json";
import { currentSeasonKey, seasonLabel, type AnimeSeasonsView } from "@/lib/animeSeason";

const V = view as unknown as AnimeSeasonsView;

export const metadata: Metadata = {
  title: "アニメ化された漫画・季節別一覧 - MANGAL",
  description: "1960年代から現在までのTV・配信アニメの原作漫画を放送季ごとに一覧。",
};

export default function AnimeSeasonsIndexPage() {
  const current = currentSeasonKey(V.order);
  // 年→季の逆時系列で並べる
  const byYear = new Map<string, string[]>();
  for (const k of V.order) {
    const y = k.split("-")[0];
    byYear.set(y, [...(byYear.get(y) ?? []), k]);
  }
  const years = [...byYear.keys()].sort((a, b) => Number(b) - Number(a));

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <Link href="/" className="text-sm text-ink/60 hover:text-ink">
        ← トップへ戻る
      </Link>

      <h1 className="mt-4 text-2xl font-bold">📺 アニメの原作漫画(季節別)</h1>
      <p className="mt-1 text-xs text-ink/55">
        放送季を選ぶと、その季に始まったアニメの原作漫画一覧へ。{seasonLabel(V.order[0])}〜
        {seasonLabel(V.order[V.order.length - 1])}。
      </p>

      <Link
        href={`/anime/${current}`}
        className="mt-4 block rounded-xl bg-[var(--color-accent-warm)] px-4 py-3.5 text-white shadow-md spring-press"
      >
        <p className="text-[14px] font-bold">今季: {seasonLabel(current)}アニメの原作を見る →</p>
      </Link>

      <div className="mt-6 space-y-3">
        {years.map((y) => (
          <div key={y} className="flex items-baseline gap-3">
            <span className="w-12 shrink-0 text-sm font-bold text-ink/70">{y}</span>
            <div className="flex flex-wrap gap-1.5">
              {(byYear.get(y) ?? []).map((k) => (
                <Link
                  key={k}
                  href={`/anime/${k}`}
                  className={`rounded-[var(--radius-tag)] border px-2.5 py-1 text-xs font-medium ${
                    k === current
                      ? "border-[var(--color-accent-warm)] bg-[var(--color-accent-warm)] text-white"
                      : "border-[var(--color-line)] bg-[var(--color-surface-2)] text-ink/70"
                  }`}
                >
                  {seasonLabel(k).slice(-1)}
                  <span className="ml-1 text-[9px] opacity-60">{V.seasons[k].length}</span>
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
