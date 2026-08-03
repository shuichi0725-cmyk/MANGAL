"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  fetchTokushuDay,
  fetchTokushuIndex,
  jstToday,
  type TokushuDay,
  type TokushuIndex,
  type TokushuItem,
} from "@/components/DailyFeatureCorner";

/** 日替わり特集ページ本体(2026-08-03 ユーザ採用)。見た目は日替わりで
 *  案1(特集扉=色帯ヒーロー+TOP3大カード) / 案2(本棚=木の棚に順位バッジ)。色=題材色。
 *  ?d=YYYY-MM-DD で過去の号も表示(凍結stockなので内容は永久固定=過去ログ)。
 *  データは /data/tokushu/*.json の自己完結型=索引不要(preview subsetでも完全動作)。 */
export default function TokushuClient() {
  const sp = useSearchParams();
  const today = jstToday();
  const reqD = sp.get("d");
  const dkey = reqD && /^\d{4}-\d{2}-\d{2}$/.test(reqD) && reqD <= today ? reqD : today;
  const [day, setDay] = useState<TokushuDay | null | undefined>(undefined);
  const [idx, setIdx] = useState<TokushuIndex | null>(null);
  const [limit, setLimit] = useState(10);
  useEffect(() => {
    setLimit(10);
    fetchTokushuDay(dkey).then((d) => setDay(d));
    fetchTokushuIndex().then(setIdx);
  }, [dkey]);

  if (day === undefined) return <p className="py-14 text-center text-sm text-ink/50">読み込み中…</p>;
  if (day === null) return <p className="py-14 text-center text-sm text-ink/50">この日の特集はありません。</p>;

  const shown = day.items.slice(0, limit);
  const dt = new Date(dkey + "T00:00:00");
  const dateLabel = `${dt.getMonth() + 1}/${dt.getDate()}`;
  const isPast = dkey !== today;
  const past = Object.keys(idx?.days ?? {}).filter((k) => k < today).sort().reverse().slice(0, 30);

  const pastLog = (
    <section className="mx-3.5 mb-10 mt-8">
      <h2 className="mb-2 text-[13px] font-extrabold text-ink/60">🗒️ 過去の特集</h2>
      <div className="overflow-hidden rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)]">
        {past.length === 0 && <p className="p-3 text-[12px] text-ink/45">まだ過去の号はありません(毎日たまっていきます)。</p>}
        {past.map((k) => (
          <Link key={k} href={`/tokushu?d=${k}`} className="flex items-baseline gap-3 border-b border-[var(--color-line)] px-3 py-2 last:border-b-0 hover:bg-[var(--color-surface-2)]/60">
            <span className="w-[52px] shrink-0 text-[11px] tabular-nums text-ink/45">{k.slice(5).replace("-", "/")}</span>
            <span className="min-w-0 truncate text-[13px] font-bold">{idx!.days[k].t}</span>
            <span className="ml-auto shrink-0 text-[10px]" style={{ color: idx!.days[k].c.a }}>●</span>
          </Link>
        ))}
      </div>
      {isPast && (
        <Link href="/tokushu" className="mt-2 block text-center text-[12px] font-bold underline underline-offset-4" style={{ color: day.c.a }}>
          今日の特集にもどる
        </Link>
      )}
    </section>
  );

  const moreBtn = limit < day.items.length && (
    <button
      type="button"
      onClick={() => setLimit((v) => (v === 10 ? 30 : 100))}
      className="spring-press mx-auto mt-3 block rounded-full border border-[var(--color-line)] bg-[var(--color-surface)] px-8 py-2.5 text-[13px] font-extrabold shadow-[var(--shadow-soft)]"
      style={{ color: day.c.a }}
    >
      {Math.min(limit, day.items.length)}位まで表示中 ─ さらに見る ▾
    </button>
  );
  const browseLink = (
    <Link href={`/browse?${day.q}`} className="mx-auto mt-3 block w-fit pb-1 text-[12px] font-bold text-ink/50 underline underline-offset-4">
      この条件で検索面でも見る →
    </Link>
  );
  const yearLabel = (it: TokushuItem) =>
    `${it[4] ?? "?"}${it[5] ? `〜${it[5]}` : "〜"}${it[6] === "completed" ? "・完結" : ""}`;

  if (day.sty.p === 1) {
    // ── 案1: 特集扉型 ──
    return (
      <div>
        <div className="relative overflow-hidden px-4 pb-8 pt-6 text-white" style={{ background: day.c.a }}>
          <span className="pointer-events-none absolute -top-5 right-0 select-none text-[110px] font-black italic tracking-tighter text-white/10">{dateLabel}</span>
          <span className="inline-block rounded-[2px] border border-white/60 px-2.5 py-0.5 text-[11px] font-extrabold tracking-[.25em]">
            日替わり特集 ─ {dateLabel}{isPast ? "号" : ""}
          </span>
          <h1 className="mb-2 mt-3 text-[30px] font-black leading-tight [text-shadow:0_2px_0_rgba(0,0,0,.12)]">{day.t}</h1>
          <p className="text-[12px] leading-relaxed text-white/90">{day.lead}</p>
          <div className="mt-3 flex gap-2">
            <span className="rounded-full bg-black/20 px-2.5 py-0.5 text-[11px] font-extrabold">全{day.n}作</span>
            {isPast && <span className="rounded-full bg-black/20 px-2.5 py-0.5 text-[11px] font-extrabold">過去の号</span>}
          </div>
        </div>
        <div className="px-3.5 pt-4">
          {shown.map((it, i) =>
            i < 3 ? (
              <Link key={it[0]} href={`/manga/${it[0]}`} className="spring-press relative mb-3 flex gap-3 rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)] p-3 shadow-[var(--shadow-soft)]">
                <span
                  className="absolute -left-1.5 -top-3 text-[40px] font-black italic leading-none [text-shadow:2px_2px_0_#fff,-1px_-1px_0_#fff]"
                  style={{ color: [day.c.a, "#8a8f98", "#b0713a"][i] }}
                >
                  {i + 1}
                </span>
                {it[3] && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={it[3]} alt="" loading="lazy" className="h-[116px] w-[82px] rounded border border-[var(--color-line)] object-cover" />
                )}
                <div className="min-w-0 pt-1.5">
                  <h3 className="text-[16px] font-black leading-snug">{it[1]}</h3>
                  <p className="mt-0.5 text-[12px] text-ink/60">{it[2]}</p>
                  <p className="mt-0.5 text-[11px] text-ink/45">{yearLabel(it)}</p>
                </div>
              </Link>
            ) : (
              <Link key={it[0]} href={`/manga/${it[0]}`} className="spring-press mb-1.5 flex items-center gap-2.5 rounded-md border border-[var(--color-line)] bg-[var(--color-surface)] px-2.5 py-1.5">
                <span className="w-7 shrink-0 text-center text-[16px] font-black italic text-ink/35">{i + 1}</span>
                {it[3] && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={it[3]} alt="" loading="lazy" className="h-12 w-[34px] rounded-[2px] border border-[var(--color-line)] object-cover" />
                )}
                <div className="min-w-0">
                  <p className="truncate text-[13px] font-bold leading-snug">{it[1]}</p>
                  <p className="text-[10.5px] text-ink/55">{it[2]} ｜ {it[4]}</p>
                </div>
              </Link>
            ),
          )}
          {moreBtn}
          {browseLink}
        </div>
        {pastLog}
      </div>
    );
  }

  // ── 案2: 本棚型 ──
  const shelves: TokushuItem[][] = [];
  for (let i = 0; i < shown.length; i += 5) shelves.push(shown.slice(i, i + 5));
  return (
    <div style={{ background: "#efe9dd" }}>
      <div className="mx-auto w-[300px] pt-5 text-center">
        <div className="rounded-md border-2 py-2.5 text-white shadow-md" style={{ background: `linear-gradient(180deg, ${day.c.a}, ${day.c.d})`, borderColor: day.c.d }}>
          <p className="text-[10px] font-bold tracking-[.3em] opacity-85">日替わり特集 ─ {dateLabel}{isPast ? "号" : ""}</p>
          <h1 className="mt-0.5 text-[20px] font-black tracking-wide">{day.t}</h1>
        </div>
        <p className="mb-3 mt-1.5 text-[11px] font-bold text-ink/55">{isPast ? "過去の号(内容は当日のまま)" : "明日は別のお題に掛け替わります"}</p>
      </div>
      <div className="mx-3 mb-4 rounded-[10px] border-[3px] border-[#5d3f21] bg-gradient-to-b from-[#8a6338] to-[#7a5630] px-2.5 pb-3 pt-3.5 shadow-[0_10px_24px_rgba(60,40,15,.35),inset_0_0_40px_rgba(0,0,0,.25)]">
        {shelves.map((row, si) => (
          <div key={si} className="mb-1 px-1">
            <div className="flex items-end justify-between px-0.5">
              {row.map((it, i) => {
                const rank = si * 5 + i + 1;
                return (
                  <Link key={it[0]} href={`/manga/${it[0]}`} className="spring-press relative w-[68px] text-center">
                    <span
                      className="absolute -left-1.5 -top-2 z-10 flex h-6 w-6 items-center justify-center rounded-full border-2 border-white text-[12px] font-black text-white shadow"
                      style={{ background: rank === 1 ? day.c.a : rank === 2 ? "#8a8f98" : rank === 3 ? "#b0713a" : "#4a4f57" }}
                    >
                      {rank}
                    </span>
                    {it[3] && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={it[3]} alt={it[1]} loading="lazy" className="h-[96px] w-[68px] rounded-[2px_4px_4px_2px] border border-black/25 bg-white object-cover shadow-[-3px_4px_6px_rgba(0,0,0,.4)]" />
                    )}
                  </Link>
                );
              })}
              {row.length < 5 && Array.from({ length: 5 - row.length }).map((_, i) => <span key={i} className="w-[68px]" />)}
            </div>
            <div className="mt-2 h-3 rounded-[2px] bg-gradient-to-b from-[#a97f4d] to-[#8a6338] shadow-[0_3px_5px_rgba(0,0,0,.35),inset_0_1px_0_rgba(255,255,255,.25)]" />
            <div className="flex justify-between px-0.5 pb-2 pt-1">
              {row.map((it) => (
                <div key={it[0]} className="w-[68px] text-center text-[9px] font-bold leading-tight text-[#ffefd9] [text-shadow:0_1px_2px_rgba(0,0,0,.5)]">
                  <span className="line-clamp-2 block">{it[1]}</span>
                  <span className="block text-[8px] font-normal text-[#ffefd9]/70">{it[2]}</span>
                </div>
              ))}
              {row.length < 5 && Array.from({ length: 5 - row.length }).map((_, i) => <span key={i} className="w-[68px]" />)}
            </div>
          </div>
        ))}
      </div>
      <div className="pb-2 text-center">
        {limit < day.items.length && (
          <button
            type="button"
            onClick={() => setLimit((v) => (v === 10 ? 30 : 100))}
            className="spring-press rounded-full border border-[var(--color-line)] bg-[var(--color-surface)] px-7 py-2.5 text-[13px] font-extrabold shadow"
            style={{ color: day.c.a }}
          >
            {Math.min(limit, day.items.length)}冊まで棚に出し中 ─ もっと出す ▾
          </button>
        )}
        {browseLink}
      </div>
      {pastLog}
    </div>
  );
}
