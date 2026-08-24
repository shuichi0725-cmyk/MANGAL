"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useMangaIndex } from "@/lib/useMangaIndex";
import { dotGothic } from "@/lib/fonts";

/** 今月の新刊・全冊一覧(2026-08-25 ユーザ採用=案E):
 *  横スクロール・展開ボタン一切なし=上下スクロールだけで月の全冊を見る。
 *  - データ: /shinkan/{ym}.json ([slug, vol, title, cover|null]。_gen-shinkan-data.py が生成・週次で更新)
 *  - 日付ヘッダーはsticky(長い日でも今どこか見える)
 *  - 書影なしは題字タイル(=歯抜けにしない・全冊主義)
 *  - ★死リンク防止: 一覧索引に居る作品だけ<Link>化(preview=subsetでも安全)。索引外は素のタイル */
type Item = [string, number | null, string, string | null];
type MonthData = { days: Record<string, Item[]>; unknown: Item[] };

const WEEK = ["日", "月", "火", "水", "木", "金", "土"];

function jstYm(offset = 0): string {
  const t = new Date(Date.now() + 9 * 3600 * 1000);
  const m = t.getUTCMonth() + offset;
  const y = t.getUTCFullYear() + Math.floor(m / 12);
  return `${y}-${String(((m % 12) + 12) % 12 + 1).padStart(2, "0")}`;
}

function weekday(ym: string, day: string): string {
  // JST正午で固定=端末TZに依らず正しい曜日
  return WEEK[new Date(`${ym}-${day.padStart(2, "0")}T12:00:00+09:00`).getUTCDay()];
}

export default function ShinkanClient() {
  const [ym, setYm] = useState(jstYm());
  const [data, setData] = useState<Record<string, MonthData | null>>({});
  const index = useMangaIndex();
  const known = useMemo(() => new Set((index ?? []).map((it) => it.slug)), [index]);

  useEffect(() => {
    if (data[ym] !== undefined) return;
    fetch(`/shinkan/${ym}.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setData((p) => ({ ...p, [ym]: d })))
      .catch(() => setData((p) => ({ ...p, [ym]: null })));
  }, [ym, data]);

  const tabs = [jstYm(-1), jstYm(0), jstYm(1), jstYm(2)];
  const month = data[ym];
  const days = month ? Object.keys(month.days).sort((a, b) => Number(a) - Number(b)) : [];
  const total = month ? days.reduce((s, d) => s + month.days[d].length, 0) + (month.unknown?.length ?? 0) : 0;

  const Tile = ({ it }: { it: Item }) => {
    const [slug, vol, title, cover] = it;
    const inner = cover ? (
      <>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={cover} alt={title} loading="lazy" className="block h-full w-full object-cover" />
        {vol ? <span className="absolute bottom-0 left-0 bg-[var(--color-accent)] px-1 text-[9px] font-black text-[#0d0d0d]">{vol}巻</span> : null}
      </>
    ) : (
      <>
        <span className="line-clamp-6 px-1 text-center text-[9.5px] font-bold leading-[1.35] text-ink/70">{title}</span>
        {vol ? <span className="absolute bottom-0 left-0 bg-[var(--color-accent)] px-1 text-[9px] font-black text-[#0d0d0d]">{vol}巻</span> : null}
      </>
    );
    const cls = `relative block aspect-[5/7.2] overflow-hidden bg-[#1a1a1a] ${cover ? "" : "flex items-center justify-center border border-[#2c2c2c]"}`;
    return known.has(slug) ? (
      <Link href={`/manga/${slug}`} className={`${cls} spring-press`} title={title}>{inner}</Link>
    ) : (
      <div className={cls} title={title}>{inner}</div>
    );
  };

  return (
    <div className="mx-auto w-full max-w-[960px] pb-12">
      <div className="border-b-[3px] border-[var(--color-accent)] px-4 py-3">
        <h1 className={`${dotGothic.className} text-[22px] font-black`}>
          📦 {ym.slice(0, 4)}年{Number(ym.slice(5))}月の新刊
        </h1>
        <p className="mt-0.5 text-[11px] text-ink/55">
          発売日ごとに全{total.toLocaleString()}冊。スクロールだけで全部見られます。
        </p>
        <div className="mt-2 flex gap-1.5">
          {tabs.map((t) => (
            <button
              key={t}
              onClick={() => setYm(t)}
              className={`px-2.5 py-1 text-[11.5px] font-black ${t === ym ? "bg-[var(--color-accent)] text-[#0d0d0d]" : "border border-[var(--color-line)] text-ink/70"}`}
            >
              {Number(t.slice(5))}月
            </button>
          ))}
        </div>
      </div>

      {month === undefined || (month === null && data[ym] === undefined) ? (
        <p className="p-6 text-[12px] text-ink/50">読み込み中…</p>
      ) : month === null ? (
        <p className="p-6 text-[12px] text-ink/50">この月のデータはまだありません。</p>
      ) : (
        <>
          {days.map((d) => (
            <section key={d}>
              <div className="sticky top-0 z-10 flex items-baseline gap-2 border-b-2 border-[var(--color-accent)] bg-[color-mix(in_srgb,var(--color-bg)_92%,transparent)] px-3.5 pb-1.5 pt-2 backdrop-blur-[2px]">
                <span className={`${dotGothic.className} text-[19px] font-black text-[var(--color-accent)]`}>
                  {Number(ym.slice(5))}/{d.padStart(2, "0")}
                </span>
                <span className="text-[11px] text-ink/55">({weekday(ym, d)})</span>
                <span className="ml-auto text-[11px] text-ink/45">{month.days[d].length}冊</span>
              </div>
              <div className="grid grid-cols-[repeat(auto-fill,minmax(72px,1fr))] gap-[3px] px-2 py-1.5">
                {month.days[d].map((it, i) => (
                  <Tile key={`${it[0]}-${i}`} it={it} />
                ))}
              </div>
            </section>
          ))}
          {month.unknown?.length > 0 && (
            <section>
              <div className="sticky top-0 z-10 flex items-baseline gap-2 border-b-2 border-[var(--color-accent)] bg-[color-mix(in_srgb,var(--color-bg)_92%,transparent)] px-3.5 pb-1.5 pt-2 backdrop-blur-[2px]">
                <span className={`${dotGothic.className} text-[15px] font-black text-[var(--color-accent)]`}>日付未定</span>
                <span className="ml-auto text-[11px] text-ink/45">{month.unknown.length}冊</span>
              </div>
              <div className="grid grid-cols-[repeat(auto-fill,minmax(72px,1fr))] gap-[3px] px-2 py-1.5">
                {month.unknown.map((it, i) => (
                  <Tile key={`u-${it[0]}-${i}`} it={it} />
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
