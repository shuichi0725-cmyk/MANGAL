"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import CoverImage from "./CoverImage";

/** 版もののホームコーナー2本(2026-09-06 ユーザ裁定でカラー版コーナーと同じ作りに統一):
 *  ①📚 愛蔵版・合本(/aizouban) ②🎁 特装版・限定版(/tokusouban)。
 *  ★週替わりを廃止し **表示のたびランダム4点**(= ColorCorner と同方式。リロードで変わる)。
 *  ★「中に入ると全部見られる」= 見出しの「全部見る →」から一覧頁へ。
 *  ★価格は絶対に表示しない(静的価格=規約違反+誤データ [[feedback-no-static-prices]])。
 *  データ= public/data/aizouban-stock.json / tokusouban-stock.json(_gen-corner-auto.py・週次再生成)。 */
export type AizItem = {
  s: string; t: string; a?: string; e: string; l: string; v: number; sv: number; c: string; d?: string;
};
export type TksItem = {
  s: string; t: string; a?: string; v: number | null; l: string; c: string; d?: string;
};

export const TYPE_JA: Record<string, string> = {
  aizoban: "愛蔵版",
  kanzenban: "完全版",
  wideban: "ワイド版",
  shinsoban: "新装版",
  deluxe: "デラックス版",
  other: "特装",
};

/** 表示のたびランダムにN点(Fisher-Yates)。マウント後に決めるのでhydration不一致なし。 */
function usePicks<T>(url: string, n: number): { picks: T[]; total: number } | null {
  const [state, setState] = useState<{ picks: T[]; total: number } | null>(null);
  useEffect(() => {
    fetch(url)
      .then((r) => (r.ok ? r.json() : []))
      .then((rows: T[]) => {
        const pool = [...(rows || [])];
        for (let i = pool.length - 1; i > 0; i--) {
          const j = Math.floor(Math.random() * (i + 1));
          [pool[i], pool[j]] = [pool[j], pool[i]];
        }
        setState({ picks: pool.slice(0, n), total: rows?.length ?? 0 });
      })
      .catch(() => setState({ picks: [], total: 0 }));
  }, [url, n]);
  return state;
}

function Frame({
  emoji, title, note, href, children,
}: {
  emoji: string; title: string; note: string; href: string; children: React.ReactNode;
}) {
  return (
    <section className="mt-4 px-4">
      <div className="rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-3.5 shadow-sm">
        <div className="flex items-baseline justify-between gap-2">
          <h2 className="dot-heading text-[14px] font-extrabold">{emoji} {title}</h2>
          <Link href={href} className="spring-press shrink-0 text-[11px] font-bold text-[var(--color-accent)]">
            全部見る →
          </Link>
        </div>
        <p className="pt-0.5 text-[10.5px] text-ink/55">{note}</p>
        <div className="mt-2.5 grid grid-cols-4 gap-2.5">{children}</div>
      </div>
    </section>
  );
}

function Card({
  slug, cover, alt, badge, title, sub,
}: {
  slug: string; cover: string; alt: string; badge: string; title: string; sub: React.ReactNode;
}) {
  return (
    <Link href={`/manga/${slug}`} className="spring-press block">
      <div
        className="relative overflow-hidden rounded-md border border-[var(--color-line)] bg-[var(--color-surface-2)]"
        style={{ aspectRatio: "2 / 3" }}
      >
        <CoverImage src={cover} alt={alt} sizes="120px" />
        <span className="absolute left-0 top-0 max-w-full truncate rounded-br-md bg-[var(--color-accent)] px-1 py-[1px] text-[9px] font-bold text-[var(--color-on-accent)]">
          {badge}
        </span>
      </div>
      <p className="mt-1 truncate text-[10.5px] font-semibold">{title}</p>
      <p className="truncate text-[9.5px] tabular-nums text-ink/50">{sub}</p>
    </Link>
  );
}

/** 📚 愛蔵版・合本 = 通常版より冊数が減った合本だけ(選別は生成器側) */
export function AizoubanCorner() {
  const s = usePicks<AizItem>("/data/aizouban-stock.json", 4);
  if (!s || s.picks.length === 0) return null;
  return (
    <Frame
      emoji="📚"
      title="愛蔵版・合本"
      note={`全巻がぐっと少ない冊数にまとまった版。${s.total}点から毎回ランダムで4点。`}
      href="/aizouban"
    >
      {s.picks.map((p) => (
        <Card
          key={`${p.s}-${p.e}-${p.v}`}
          slug={p.s}
          cover={p.c}
          alt={`${p.t} ${TYPE_JA[p.e] ?? p.e}`}
          badge={TYPE_JA[p.e] ?? p.e}
          title={p.t}
          sub={<>全{p.sv}巻 → <b className="text-ink/70">{p.v}巻</b></>}
        />
      ))}
    </Frame>
  );
}

/** 🎁 特装版・限定版 = 巻のvariant(フィギュア・小冊子つき等) */
export function TokusoubanCorner() {
  const s = usePicks<TksItem>("/data/tokusouban-stock.json", 4);
  if (!s || s.picks.length === 0) return null;
  return (
    <Frame
      emoji="🎁"
      title="特装版・限定版"
      note={`小冊子・グッズつきなどの特別仕様。${s.total}点から毎回ランダムで4点。`}
      href="/tokusouban"
    >
      {s.picks.map((p) => (
        <Card
          key={`${p.s}-${p.v}-${p.l}`}
          slug={p.s}
          cover={p.c}
          alt={`${p.t} ${p.l}`}
          badge={p.l}
          title={p.t}
          sub={<>{p.v ? `${p.v}巻` : "特装"}{p.d ? `・${p.d}年` : ""}</>}
        />
      ))}
    </Frame>
  );
}
