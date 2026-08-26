"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import CoverImage from "./CoverImage";
import MarqueeTitle from "./MarqueeTitle";
import { useMangaIndex } from "@/lib/useMangaIndex";

const SHOW = 12;

export type MonthPick = {
  slug: string;
  title: string;
  authors: string;
  number: number | null; // 当月に出る巻番号(リンクの #v フォーカス用)
  sub: string; // 「3巻・7/18発売」等の表示文字列(server側で組立済)
  cover: string | null;
};

/** /shinkan/{ym}.json の行 = [slug, vol, title, cover, isbn13, authors, publisher, imprint] */
type ShinkanItem = [string, number | null, string, string | null, string | null, string, string, string];

function jstToday(): { ym: string; day: number } {
  const t = new Date(Date.now() + 9 * 3600 * 1000);
  return { ym: `${t.getUTCFullYear()}-${String(t.getUTCMonth() + 1).padStart(2, "0")}`, day: t.getUTCDate() };
}

function shuffle<T>(a: T[]): T[] {
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/** 📦 今月の新刊の表示部(client)。
 *  ★2026-08-27 ユーザ要望で「当月ランダム」→「**当日発売**をランダム表示」に変更:
 *  マウント後に /shinkan/{当月}.json(発売日ごと全冊・週次蒸留step1で再生成)を読み、
 *  JSTの今日の発売分だけをシャッフルして出す(=静的ビルドのままでも毎日中身が変わる)。
 *  今日に発売が無い日は**直近の発売日へ遡って**その日付を明示(「8/25発売」)。
 *  月初で過去が無い月は月内の次の発売日。fetch失敗/索引未着はSSRの当月poolのまま(従来表示)。
 *  死リンク防止: 一覧索引に居るslugだけ表示(preview=subsetでも安全)。
 *  リンクは #v<巻番号> 付き=作品ページで当月巻(最新刊)にフォーカス。 */
export default function MonthReleasesClient({ pool }: { pool: MonthPick[] }) {
  const [picks, setPicks] = useState<MonthPick[]>(pool.slice(0, SHOW));
  const [dayLabel, setDayLabel] = useState<string | null>(null);
  const index = useMangaIndex();

  useEffect(() => {
    let dead = false;
    const { ym, day } = jstToday();
    fetch(`/shinkan/${ym}.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { days?: Record<string, ShinkanItem[]> } | null) => {
        if (dead) return;
        const known = index ? new Set(index.map((it) => it.slug)) : null;
        const days = d?.days ?? {};
        const pick = (guard: boolean) => {
          const usable = (n: number) => {
            const items = (days[String(n).padStart(2, "0")] ?? days[String(n)] ?? []).filter(
              (it) => it[3] && (!guard || !known || known.has(it[0])),
            );
            return items.length >= 1 ? items : null;
          };
          // 今日→過去へ遡り→(月初で無ければ)未来へ、最初に発売のある日
          for (let n = day; n >= 1; n--) {
            const items = usable(n);
            if (items) return { n, items };
          }
          for (let n = day + 1; n <= 31; n++) {
            const items = usable(n);
            if (items) return { n, items };
          }
          return null;
        };
        // 索引guardで全滅(=preview subset等)の時だけguard無しで再選定(本番はguard付きで確定)
        const hit = pick(true) ?? pick(false);
        if (!hit) {
          setPicks(shuffle(pool.slice()).slice(0, SHOW));
          return;
        }
        const label = `${Number(ym.slice(5))}/${hit.n}発売`;
        setDayLabel(hit.n === day ? `きょう ${label}` : label);
        setPicks(
          shuffle(hit.items.slice()).slice(0, SHOW).map((it) => ({
            slug: it[0],
            title: it[2],
            authors: it[5] ?? "",
            number: it[1],
            sub: `${it[1] ? `${it[1]}巻` : "新刊"}・${label}`,
            cover: it[3],
          })),
        );
      })
      .catch(() => {
        if (!dead) setPicks(shuffle(pool.slice()).slice(0, SHOW));
      });
    return () => {
      dead = true;
    };
  }, [pool, index]);

  if (picks.length === 0) return null;

  return (
    <>
      {dayLabel && (
        <p className="mt-1 text-[11px] font-bold text-[var(--color-accent)]">
          🗓 {dayLabel}の新刊 {picks.length}冊
        </p>
      )}
      {/* ★scroll-pl: snapは左paddingを無視して端に吸着する→スナップ位置にも14px余白(2026-07-16 ユーザ指摘) */}
      <ul className="-mx-3.5 mt-2.5 flex gap-3 overflow-x-auto no-scrollbar px-3.5 pb-1 snap-x scroll-pl-3.5">
        {picks.map((r) => (
          <li key={r.slug} className="w-[96px] shrink-0 snap-start">
            <Link
              href={`/manga/${r.slug}${r.number ? `#v${r.number}` : ""}`}
              className="block group spring-press"
            >
              <div className="relative aspect-[2/3] w-full overflow-hidden rounded border border-[var(--color-line)] bg-[var(--color-surface-2)]">
                {r.cover ? (
                  <CoverImage src={r.cover} alt={r.title} sizes="96px" size="card" />
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center p-2 text-center text-[11px] leading-tight text-ink/45">
                    {r.title.slice(0, 28)}
                  </div>
                )}
              </div>
              <MarqueeTitle text={r.title} className="mt-1 text-[12px] leading-snug text-ink/85 group-hover:text-[var(--color-accent)]" />
              <p className="truncate text-[10px] font-semibold text-[var(--color-accent)]">{r.sub}</p>
              <p className="truncate text-[10px] text-ink/50">{r.authors}</p>
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
