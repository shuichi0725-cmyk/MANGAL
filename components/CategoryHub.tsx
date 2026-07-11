"use client";

import { useSearchParams } from "next/navigation";
import Card from "@/components/ui/Card";
import type { ListBundle } from "@/lib/schema";

type Props = { data: ListBundle };

type Category = {
  href: string;
  label: string;
  count: number;
  icon: string;
};

/**
 * ホーム top の カテゴリエントリ grid。 mobile 2 列 / desktop 4-6 列で
 * scale。 カウント 0 のカテゴリは非表示 (= データ無いのに見せても無意味)。
 *
 * 各リンクは home page の URL 検索パラメータで filter を適用させる
 * (`/?anime=true` 等)、 SearchParams → FilterState 復元は
 * `lib/filters.ts:filtersFromSearchParams` で対応。
 */
export default function CategoryHub({ data }: Props) {
  // ★選択中タイルの可視化(2026-07-11 ユーザ指摘: どれが押されているか分からない)
  const searchParams = useSearchParams();
  const isActive = (href: string) => {
    const target = new URLSearchParams(href.split("?")[1] || "");
    for (const [k, v] of target.entries()) {
      if (searchParams.get(k) !== v) return false;
    }
    return true;
  };
  const total = data.manga.length;
  const animeCount = data.manga.filter((m) => m.anime_adapted).length;
  const awardCount = data.manga.filter(
    (m) => m.awards && m.awards.length > 0,
  ).length;
  const completedCount = data.manga.filter(
    (m) => m.status === "completed",
  ).length;
  const ongoingCount = data.manga.filter((m) => m.status === "ongoing").length;
  const shounenCount = data.manga.filter(
    (m) => m.demographic === "shounen",
  ).length;
  const seinenCount = data.manga.filter(
    (m) => m.demographic === "seinen",
  ).length;
  const shoujoCount = data.manga.filter(
    (m) => m.demographic === "shoujo",
  ).length;
  const joseiCount = data.manga.filter((m) => m.demographic === "josei").length;

  const categories: Category[] = [
    {
      href: "/browse?anime=true",
      label: "アニメ化作品",
      count: animeCount,
      icon: "🎞️",
    },
    {
      href: "/browse?hasAwards=true",
      label: "受賞作品",
      count: awardCount,
      icon: "🏆",
    },
    {
      href: "/browse?status=completed",
      label: "完結作品",
      count: completedCount,
      icon: "✅",
    },
    {
      href: "/browse?status=ongoing",
      label: "連載中",
      count: ongoingCount,
      icon: "📖",
    },
    {
      href: "/browse?demographic=shounen",
      label: "少年",
      count: shounenCount,
      icon: "👦",
    },
    {
      href: "/browse?demographic=seinen",
      label: "青年",
      count: seinenCount,
      icon: "👨",
    },
    {
      href: "/browse?demographic=shoujo",
      label: "少女",
      count: shoujoCount,
      icon: "👧",
    },
    {
      href: "/browse?demographic=josei",
      label: "女性",
      count: joseiCount,
      icon: "👩",
    },
    // 並び順 (= filter ではなく sort、 全件対象なので count = total)
    {
      href: "/browse?sort=popularity",
      label: "人気順",
      count: total,
      icon: "🔥",
    },
    {
      href: "/browse?sort=year-desc",
      label: "新しい順",
      count: total,
      icon: "🆕",
    },
    {
      href: "/browse?sort=year-asc",
      label: "古い順",
      count: total,
      icon: "📜",
    },
    {
      href: "/browse?sort=volumes",
      label: "巻数順",
      count: total,
      icon: "📚",
    },
    {
      href: "/browse?sort=title",
      label: "五十音順",
      count: total,
      icon: "🅰️",
    },
  ].filter((c) => c.count > 0);

  if (categories.length === 0) return null;

  return (
    <section className="mb-7">
      <h2 className="text-[11px] font-semibold tracking-[0.18em] uppercase text-ink/50 mb-3">
        カテゴリで探す
      </h2>
      <ul className="grid grid-cols-4 sm:grid-cols-5 lg:grid-cols-6 gap-2">
        {categories.map((c) => {
          const active = isActive(c.href);
          return (
            <li key={c.href}>
              <Card
                href={active ? "/browse" : c.href}
                className={`h-full px-1 py-2.5 text-center ${
                  active ? "!bg-[var(--color-accent)] !text-white ring-2 ring-[var(--color-accent)]" : ""
                }`}
              >
                <span className="flex flex-col items-center justify-center gap-1">
                  <span className="text-base leading-none" aria-hidden="true">
                    {c.icon}
                  </span>
                  <span className="text-[11px] font-semibold leading-tight">
                    {active ? "✓ " : ""}{c.label}
                  </span>
                  <span className={`text-[10px] font-medium leading-none tabular-nums ${active ? "text-white/75" : "text-ink/40"}`}>
                    {c.count}
                  </span>
                </span>
              </Card>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
