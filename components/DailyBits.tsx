"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { jstDayIndex } from "./SansedaiDaily";

/** ホームの小さな日替わりパーツ群(2026-08-04 見直しで発見した「偽日替わり」の恒久修正)。
 *  旧: page.tsx(サーバ)で daySalt=new Date() を使って選定 → ★静的書き出しでは
 *  **ビルド時に凍結**され、週次ビルドごとにしか変わっていなかった。
 *  新: プール/候補はサーバから受け取り、**どれを出すかはクライアントがJSTの日で選ぶ**
 *  (= FeaturedDaily/日替わり特集と同じ型)。マウント前は初日分を出す=hydration不一致なし。 */

function useDay(): number {
  const [d, setD] = useState(0);
  useEffect(() => {
    setD(jstDayIndex());
  }, []);
  return d;
}

/** ことばカード = あらすじの一文だけ大きく(縦読みの「息継ぎ」) */
export function KotobaDaily({ pool }: { pool: Array<{ slug: string; title: string; line: string }> }) {
  const day = useDay();
  if (pool.length === 0) return null;
  const k = pool[day % pool.length];
  return (
    <section className="mt-4 px-4">
      <Link href={`/manga/${k.slug}`} className="block rounded-xl bg-ink px-5 py-6 text-center shadow-md spring-press">
        <p className="text-[15px] font-bold leading-relaxed text-white">「{k.line}。」</p>
        <p className="mt-2 text-[11px] text-white/60">— 今日のことば: 『{k.title}』のあらすじから</p>
      </Link>
    </section>
  );
}

/** きょうの数字(トリビア) */
export function TriviaDaily({ items }: { items: string[] }) {
  const day = useDay();
  if (items.length === 0) return null;
  return <>{items[day % items.length]}</>;
}

/** ジャンルルーレット */
export function GenreRouletteDaily({ genres }: { genres: Array<{ key: string; name: string }> }) {
  const day = useDay();
  if (genres.length === 0) return null;
  const g = genres[day % genres.length];
  return (
    <Link
      href={`/browse?genre=${encodeURIComponent(g.key)}`}
      className="block rounded-xl bg-gradient-to-r from-[var(--color-accent)] to-[var(--color-accent)]/80 px-4 py-3.5 text-[var(--color-on-accent)] shadow-md spring-press"
    >
      <p className="text-[13px] font-bold leading-snug">
        🎡 今日のジャンルルーレット: <span className="text-[16px] whitespace-nowrap">{g.name}</span>
      </p>
      <p className="mt-0.5 text-right text-[11px] opacity-85">回ったジャンルの棚へ →</p>
    </Link>
  );
}
