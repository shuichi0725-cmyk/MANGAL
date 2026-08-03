"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import type { TokushuDay, TokushuItem } from "@/components/DailyFeatureCorner";

/** 日替わり特集・案2「本棚型」のテーマ別演出(2026-08-03 ユーザ要望「ジャンル毎に変えたい。SFっぽい/ホラーっぽい」)。
 *  テーマはその日の browse クエリ(day.q)の genre から導出 = ★凍結済みstockにもデータ変更なしで効く。
 *  装飾は CSS グラデーション+絵文字のみ(外部アセットなし・軽量)。?t=<theme> で確認用に強制切替可。 */

export type ThemeKey = "wood" | "sf" | "horror" | "wa" | "love" | "pop" | "fantasy" | "cafe";

const GENRE_THEME: Record<string, ThemeKey> = {
  "sci-fi": "sf", mecha: "sf",
  horror: "horror", yokai: "horror", supernatural: "horror", suspense: "horror", mystery: "horror",
  historical: "wa", samurai: "wa", war: "wa",
  romance: "love", romcom: "love", bl: "love", "mahou-shoujo": "love",
  gag: "pop", comedy: "pop", "4-koma": "pop", ecchi: "pop",
  fantasy: "fantasy", isekai: "fantasy",
  "slice-of-life": "cafe", school: "cafe", essay: "cafe", gourmet: "cafe",
};

export function themeOf(q: string, override?: string | null): ThemeKey {
  if (override && ["wood", "sf", "horror", "wa", "love", "pop", "fantasy", "cafe"].includes(override)) {
    return override as ThemeKey;
  }
  const m = /(?:^|&)genre=([a-z0-9-]+)/.exec(q || "");
  return (m && GENRE_THEME[m[1]]) || "wood";
}

type Th = {
  page: string;           // ページ背景
  frame: string;          // 棚の外枠
  board: string;          // 棚板
  cap: string; capSub: string; // 題名/著者の文字色
  badge4: string;         // 4位以降のバッジ色
  decor: ReactNode;       // ページ全体の飾り(絵文字・光 등)
  sign: (title: string, sub: string) => ReactNode; // 看板
  note: string;           // 棚下の一言の文字色
};

const shelfBoard = (top: string, bottom: string, glow = "rgba(255,255,255,.25)") =>
  `linear-gradient(180deg, ${top}, ${bottom})`;

function buildThemes(day: TokushuDay, dateLabel: string, isPast: boolean): Record<ThemeKey, Th> {
  const kicker = `日替わり特集 ─ ${dateLabel}${isPast ? "号" : ""}`;
  const plainSign = (bgTop: string, bgBottom: string, border: string, extra?: ReactNode) =>
    function Sign(title: string, sub: string) {
      return (
        <div className="relative mx-auto w-[310px] pt-5 text-center">
          {extra}
          <div className="rounded-md border-2 py-2.5 text-white shadow-md" style={{ background: `linear-gradient(180deg, ${bgTop}, ${bgBottom})`, borderColor: border }}>
            <p className="text-[10px] font-bold tracking-[.3em] opacity-85">{kicker}</p>
            <h1 className="mt-0.5 text-[20px] font-black tracking-wide">{title}</h1>
          </div>
          <p className="mb-3 mt-1.5 text-[11px] font-bold opacity-80">{sub}</p>
        </div>
      );
    };
  return {
    // ── 既定: 木の本棚 ──
    wood: {
      page: "#efe9dd",
      frame: "rounded-[10px] border-[3px] border-[#5d3f21] bg-gradient-to-b from-[#8a6338] to-[#7a5630] shadow-[0_10px_24px_rgba(60,40,15,.35),inset_0_0_40px_rgba(0,0,0,.25)]",
      board: shelfBoard("#a97f4d", "#8a6338"),
      cap: "#ffefd9", capSub: "rgba(255,239,217,.7)", badge4: "#4a4f57", note: "rgba(15,17,21,.55)",
      decor: <span className="pointer-events-none absolute left-3 top-2 text-lg opacity-60">📚</span>,
      sign: plainSign(day.c.a, day.c.d, day.c.d),
    },
    // ── SF: 宇宙ステーションの鋼鉄ラック ──
    sf: {
      page: "radial-gradient(1px 1px at 20% 15%, #fff 50%, transparent 51%), radial-gradient(1px 1px at 70% 8%, #fff 50%, transparent 51%), radial-gradient(1.5px 1.5px at 45% 30%, #9cc4ff 50%, transparent 51%), radial-gradient(1px 1px at 85% 45%, #fff 50%, transparent 51%), radial-gradient(1px 1px at 12% 60%, #9cc4ff 50%, transparent 51%), radial-gradient(1.5px 1.5px at 60% 75%, #fff 50%, transparent 51%), radial-gradient(1px 1px at 30% 88%, #fff 50%, transparent 51%), linear-gradient(180deg, #060a1c, #0b1330 55%, #101a3e)",
      frame: "rounded-lg border-2 border-[#3b4a7a] bg-gradient-to-b from-[#1a2344] to-[#121a36] shadow-[0_0_22px_rgba(80,140,255,.35),inset_0_0_30px_rgba(0,0,0,.5)]",
      board: "linear-gradient(180deg, #8fa3c8, #4a5a80 45%, #2c3a55)",
      cap: "#cfe0ff", capSub: "rgba(160,190,255,.65)", badge4: "#31406e", note: "rgba(207,224,255,.7)",
      decor: (
        <>
          <span className="pointer-events-none absolute right-4 top-3 text-xl">🪐</span>
          <span className="pointer-events-none absolute left-4 top-10 text-sm">🛰️</span>
        </>
      ),
      sign: (title, sub) => (
        <div className="mx-auto w-[310px] pt-5 text-center">
          <div className="rounded-md border py-2.5 text-[#dff0ff] shadow-[0_0_18px_rgba(80,160,255,.5)]" style={{ background: "linear-gradient(180deg,#0e1c46,#0a1332)", borderColor: "#4d6fd9" }}>
            <p className="text-[10px] font-bold tracking-[.35em] text-[#7fa8ff]">{kicker}</p>
            <h1 className="mt-0.5 text-[20px] font-black tracking-[.06em] [text-shadow:0_0_10px_rgba(120,180,255,.9)]">{title}</h1>
            <div className="mx-auto mt-1.5 h-px w-3/4 bg-gradient-to-r from-transparent via-[#6f9dff] to-transparent" />
          </div>
          <p className="mb-3 mt-1.5 text-[11px] font-bold text-[#9db8e8]">{sub}</p>
        </div>
      ),
    },
    // ── ホラー: 洋館の夜の書架 ──
    horror: {
      page: "radial-gradient(ellipse at 50% 0%, rgba(120,80,160,.25), transparent 60%), linear-gradient(180deg, #0d0a12, #16101f 60%, #1a1226)",
      frame: "rounded-md border-[3px] border-[#241a30] bg-gradient-to-b from-[#2c1f3a] to-[#1c1428] shadow-[0_14px_30px_rgba(0,0,0,.7),inset_0_0_46px_rgba(0,0,0,.75)]",
      board: "linear-gradient(180deg, #4a3760, #2e2140)",
      cap: "#d9c8f0", capSub: "rgba(200,175,235,.6)", badge4: "#3a2b50", note: "rgba(217,200,240,.65)",
      decor: (
        <>
          <span className="pointer-events-none absolute left-2 top-2 text-xl opacity-80">🕸️</span>
          <span className="pointer-events-none absolute right-3 top-9 text-base opacity-90">🕯️</span>
          <span className="pointer-events-none absolute bottom-24 left-3 text-base opacity-70">🦇</span>
        </>
      ),
      sign: (title, sub) => (
        <div className="mx-auto w-[310px] pt-5 text-center">
          <div className="rounded-sm border-2 py-2.5 text-[#efe6ff] shadow-[0_6px_18px_rgba(0,0,0,.8)]" style={{ background: "linear-gradient(180deg,#3a2b50,#241a35)", borderColor: "#584070" }}>
            <p className="text-[10px] font-bold tracking-[.3em] text-[#b79ce0]">{kicker}</p>
            <h1 className="mt-0.5 font-serif text-[21px] font-black tracking-widest [text-shadow:0_0_12px_rgba(200,60,60,.8),0_2px_3px_#000]">{title}</h1>
          </div>
          <p className="mb-3 mt-1.5 text-[11px] font-bold text-[#a68cc9]">{sub}</p>
        </div>
      ),
    },
    // ── 和: 時代劇の書棚(畳と木札) ──
    wa: {
      page: "repeating-linear-gradient(90deg, rgba(120,110,70,.08) 0 2px, transparent 2px 14px), linear-gradient(180deg, #efe7cf, #e7dcbd)",
      frame: "rounded-sm border-[3px] border-[#4a3a22] bg-gradient-to-b from-[#7a5f38] to-[#634b28] shadow-[0_10px_22px_rgba(60,45,15,.4),inset_0_0_36px_rgba(0,0,0,.3)]",
      board: "linear-gradient(180deg, #9a7c4e, #7a5f38)",
      cap: "#f7ecd4", capSub: "rgba(247,236,212,.7)", badge4: "#5d4a2b", note: "rgba(74,58,34,.75)",
      decor: (
        <>
          <span className="pointer-events-none absolute right-4 top-3 text-lg opacity-80">⛩️</span>
          <span className="pointer-events-none absolute left-4 top-3 text-lg opacity-70">🏮</span>
        </>
      ),
      sign: (title, sub) => (
        <div className="mx-auto w-[310px] pt-5 text-center">
          <div className="relative mx-auto w-fit rounded-[3px] border-2 border-[#4a3a22] bg-[#f4ead2] px-6 py-2.5 shadow-[3px_3px_0_rgba(74,58,34,.35)]">
            <span className="absolute -top-2 left-1/2 h-2 w-8 -translate-x-1/2 rounded-t bg-[#4a3a22]" />
            <p className="text-[10px] font-bold tracking-[.3em] text-[#8a6d3c]">{kicker}</p>
            <h1 className="mt-0.5 font-serif text-[21px] font-black tracking-[.14em] text-[#2c2213]">{title}</h1>
            <span className="mx-auto mt-1 block h-[3px] w-16" style={{ background: day.c.a }} />
          </div>
          <p className="mb-3 mt-1.5 text-[11px] font-bold text-[#6d5732]">{sub}</p>
        </div>
      ),
    },
    // ── 恋愛: パステルの白い棚 ──
    love: {
      page: "radial-gradient(circle at 15% 20%, rgba(255,255,255,.8), transparent 30%), linear-gradient(180deg, #fdeef3, #fbe3ec)",
      frame: "rounded-2xl border-[3px] border-[#f0c0d2] bg-gradient-to-b from-[#fff] to-[#fdeff4] shadow-[0_10px_24px_rgba(210,63,111,.18),inset_0_0_24px_rgba(240,192,210,.35)]",
      board: "linear-gradient(180deg, #ffffff, #f3d3de)",
      cap: "#7c3a52", capSub: "rgba(124,58,82,.65)", badge4: "#c78aa2", note: "rgba(124,58,82,.7)",
      decor: (
        <>
          <span className="pointer-events-none absolute left-3 top-3 text-base">💐</span>
          <span className="pointer-events-none absolute right-3 top-6 text-base">💕</span>
        </>
      ),
      sign: (title, sub) => (
        <div className="mx-auto w-[310px] pt-5 text-center">
          <div className="relative rounded-full border-2 py-2.5 text-white shadow-md" style={{ background: `linear-gradient(180deg, ${day.c.a}, ${day.c.d})`, borderColor: "#fff" }}>
            <span className="absolute -left-1 -top-2 text-lg">🎀</span>
            <p className="text-[10px] font-bold tracking-[.3em] opacity-90">{kicker}</p>
            <h1 className="mt-0.5 text-[20px] font-black tracking-wide">{title}</h1>
          </div>
          <p className="mb-3 mt-1.5 text-[11px] font-bold text-[#a05a76]">{sub}</p>
        </div>
      ),
    },
    // ── ポップ: ギャグ/コメディ(ハーフトーン) ──
    pop: {
      page: "radial-gradient(rgba(210,120,20,.18) 1.5px, transparent 2px), linear-gradient(180deg, #ffe895, #ffd95e)",
      frame: "rounded-xl border-[4px] border-[#1a1c20] bg-gradient-to-b from-[#ff8a3d] to-[#f2702a] shadow-[6px_6px_0_#1a1c20]",
      board: "linear-gradient(180deg, #ffc46b, #f09b3e)",
      cap: "#2b1a05", capSub: "rgba(43,26,5,.65)", badge4: "#1a1c20", note: "rgba(43,26,5,.7)",
      decor: (
        <>
          <span className="pointer-events-none absolute left-3 top-3 rotate-[-8deg] text-xl">💥</span>
          <span className="pointer-events-none absolute right-3 top-8 text-lg">😂</span>
        </>
      ),
      sign: (title, sub) => (
        <div className="mx-auto w-[310px] pt-5 text-center">
          <div className="rotate-[-1.5deg] rounded-lg border-[3px] border-[#1a1c20] bg-white px-3 py-2.5 shadow-[5px_5px_0_#1a1c20]">
            <p className="text-[10px] font-black tracking-[.3em]" style={{ color: day.c.d }}>{kicker}</p>
            <h1 className="mt-0.5 text-[21px] font-black tracking-wide" style={{ color: "#1a1c20", textShadow: `2px 2px 0 ${day.c.a}55` }}>{title}</h1>
          </div>
          <p className="mb-3 mt-2 text-[11px] font-black text-[#6b4a12]">{sub}</p>
        </div>
      ),
    },
    // ── ファンタジー: 魔法図書館 ──
    fantasy: {
      page: "radial-gradient(1.5px 1.5px at 25% 20%, #ffe9a0 50%, transparent 51%), radial-gradient(1px 1px at 75% 12%, #fff 50%, transparent 51%), radial-gradient(1.5px 1.5px at 60% 55%, #b9f0dd 50%, transparent 51%), linear-gradient(180deg, #06251f, #0a3a2f 60%, #0d4436)",
      frame: "rounded-t-[26px] rounded-b-lg border-[3px] border-[#caa04a] bg-gradient-to-b from-[#174b3b] to-[#0e352a] shadow-[0_0_22px_rgba(202,160,74,.35),inset_0_0_36px_rgba(0,0,0,.5)]",
      board: "linear-gradient(180deg, #caa04a, #8f6d2a)",
      cap: "#eadfbe", capSub: "rgba(234,223,190,.65)", badge4: "#1f5c48", note: "rgba(234,223,190,.7)",
      decor: (
        <>
          <span className="pointer-events-none absolute left-3 top-3 text-lg">🔮</span>
          <span className="pointer-events-none absolute right-3 top-7 text-base">✨</span>
        </>
      ),
      sign: (title, sub) => (
        <div className="mx-auto w-[310px] pt-5 text-center">
          <div className="rounded-t-3xl rounded-b-md border-2 py-3 text-[#f6ecc8] shadow-[0_0_18px_rgba(202,160,74,.4)]" style={{ background: "linear-gradient(180deg,#14523f,#0c3a2c)", borderColor: "#caa04a" }}>
            <p className="text-[10px] font-bold tracking-[.3em] text-[#d9c184]">{kicker}</p>
            <h1 className="mt-0.5 font-serif text-[21px] font-black tracking-widest [text-shadow:0_0_10px_rgba(255,230,150,.55)]">{title}</h1>
          </div>
          <p className="mb-3 mt-1.5 text-[11px] font-bold text-[#bfd9c4]">{sub}</p>
        </div>
      ),
    },
    // ── カフェ: 日常/学園/グルメ(明るい木と緑) ──
    cafe: {
      page: "linear-gradient(180deg, #faf6ec, #f2ecd9)",
      frame: "rounded-xl border-[3px] border-[#b9986a] bg-gradient-to-b from-[#e0c496] to-[#cfae7a] shadow-[0_10px_22px_rgba(140,110,60,.25),inset_0_0_28px_rgba(120,90,40,.18)]",
      board: "linear-gradient(180deg, #f0dcb4, #d8bd8a)",
      cap: "#4a3a22", capSub: "rgba(74,58,34,.65)", badge4: "#8a704a", note: "rgba(74,58,34,.7)",
      decor: (
        <>
          <span className="pointer-events-none absolute left-3 top-3 text-lg">🌿</span>
          <span className="pointer-events-none absolute right-3 top-6 text-base">☕</span>
        </>
      ),
      sign: plainSign(day.c.a, day.c.d, "#fff",
        <span className="absolute right-8 top-3 text-base">🪴</span>),
    },
  };
}

export default function TokushuShelf({
  day, dateLabel, isPast, shown, theme, footer,
}: {
  day: TokushuDay; dateLabel: string; isPast: boolean; shown: TokushuItem[];
  theme: ThemeKey; footer: ReactNode;
}) {
  const th = buildThemes(day, dateLabel, isPast)[theme];
  const shelves: TokushuItem[][] = [];
  for (let i = 0; i < shown.length; i += 5) shelves.push(shown.slice(i, i + 5));
  const sub = isPast ? "過去の号(内容は当日のまま)" : "明日は別のお題に掛け替わります";
  return (
    <div className="relative" style={{ background: th.page }}>
      {th.decor}
      {th.sign(day.t, sub)}
      <div className={`mx-3 mb-4 px-2.5 pb-3 pt-3.5 ${th.frame}`}>
        {shelves.map((row, si) => (
          <div key={si} className="mb-1 px-1">
            <div className="flex items-end justify-between px-0.5">
              {row.map((it, i) => {
                const rank = si * 5 + i + 1;
                return (
                  <Link key={it[0]} href={`/manga/${it[0]}`} className="spring-press relative w-[62px] text-center">
                    <span
                      className="absolute -left-1.5 -top-2 z-10 flex h-6 w-6 items-center justify-center rounded-full border-2 border-white text-[12px] font-black text-white shadow"
                      style={{ background: rank === 1 ? day.c.a : rank === 2 ? "#8a8f98" : rank === 3 ? "#b0713a" : th.badge4 }}
                    >
                      {rank}
                    </span>
                    {it[3] && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={it[3]} alt={it[1]} loading="lazy" className="h-[88px] w-[62px] rounded-[2px_4px_4px_2px] border border-black/25 bg-white object-cover shadow-[-3px_4px_6px_rgba(0,0,0,.4)]" />
                    )}
                  </Link>
                );
              })}
              {row.length < 5 && Array.from({ length: 5 - row.length }).map((_, i) => <span key={i} className="w-[62px]" />)}
            </div>
            <div className="mt-2 h-3 rounded-[2px] shadow-[0_3px_5px_rgba(0,0,0,.35),inset_0_1px_0_rgba(255,255,255,.25)]" style={{ background: th.board }} />
            <div className="flex justify-between px-0.5 pb-2 pt-1">
              {row.map((it) => (
                <div key={it[0]} className="w-[62px] text-center text-[9px] font-bold leading-tight [text-shadow:0_1px_2px_rgba(0,0,0,.35)]" style={{ color: th.cap }}>
                  <span className="line-clamp-2 block">{it[1]}</span>
                  <span className="block text-[8px] font-normal" style={{ color: th.capSub }}>{it[2]}</span>
                </div>
              ))}
              {row.length < 5 && Array.from({ length: 5 - row.length }).map((_, i) => <span key={i} className="w-[62px]" />)}
            </div>
          </div>
        ))}
      </div>
      <div className="pb-2 text-center" style={{ color: th.note }}>{footer}</div>
    </div>
  );
}
