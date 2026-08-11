"use client";

import { useEffect, useState } from "react";

/** D3ヒーロー(2026-08-11 トップ改装トライアル)。
 *  ★コピーはリロード毎ランダム(ユーザ裁定)。SEO対策= この巨大タイポはh1にしない(装飾p扱い)。
 *  h1相当の固定文言はページ側に置く。CLS対策=枠高さ固定+候補は全て2行×最大8字に揃える。 */

const COPIES: Array<[string, string]> = [
  ["ぜんぶ、", "載ってる。"],
  ["探せない漫画は、", "ない。"],
  ["", "収蔵。"], // 先頭要素は総数で動的生成(下で差し替え)
  ["漫画の", "全記録。"],
  ["今日も、", "増えてる。"],
  ["全巻・全版・", "全日付。"],
  ["1945年から、", "現在まで。"],
  ["絶版だって、", "載ってる。"],
  ["何巻まで?に", "即答。"],
  ["漫画の", "記憶装置。"],
  ["52万冊、", "整列済み。"],
  ["本棚の、", "その先へ。"],
  ["一巻から、", "最終巻まで。"],
  ["漫画史、", "全部入り。"],
  ["次の一冊、", "ここで決まる。"],
  ["昨日の新刊も、", "載ってる。"],
];

export default function HeroD3({ total }: { total: number }) {
  // SSR/初回は既定コピー(=hydration不一致を避ける)。マウント後に抽選で差し替え。
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    setIdx(Math.floor(Math.random() * COPIES.length));
  }, []);
  const totalStr = total.toLocaleString();
  const [l1, l2] = idx === 2 ? [`${totalStr}作品、`, "収蔵。"] : COPIES[idx];
  return (
    <section className="relative overflow-hidden border-b-[3px] border-[var(--color-accent)] px-4 pb-5 pt-7">
      <div aria-hidden="true" className="pointer-events-none absolute -bottom-7 -right-8 select-none text-[120px] font-black leading-none text-white opacity-5">
        DB
      </div>
      {/* 装飾タイポ(h1ではない=リロード毎に変えてもSEOシグナル不変) */}
      <p className="min-h-[104px] text-[40px] font-black leading-[1.06] tracking-tight">
        {l1}
        <br />
        <span
          className="text-transparent"
          style={{ WebkitTextStroke: "2px var(--color-accent)" }}
        >
          {l2}
        </span>
      </p>
      <span className="mt-3 inline-block bg-[var(--color-accent)] px-3 py-1.5 text-[11px] font-black tracking-[0.16em] text-[#0d0d0d]">
        JAPANESE MANGA DATABASE
      </span>
      {/* 素のGETフォーム=JS前でも検索できる(/browseのシェルと同じ思想) */}
      <form action="/browse" method="get" className="mt-5 flex border-[3px] border-[var(--color-accent)] bg-[var(--color-surface)] shadow-[6px_6px_0_rgba(217,248,67,0.25)]">
        <input
          type="search"
          name="q"
          placeholder="タイトル・よみがな・ローマ字…"
          aria-label="作品を検索"
          className="min-w-0 flex-1 bg-transparent px-3.5 py-3 text-[14px] font-bold text-[var(--color-ink)] outline-none"
        />
        <button type="submit" className="bg-[var(--color-accent)] px-5 text-[14px] font-black text-[#0d0d0d]">
          検索
        </button>
      </form>
    </section>
  );
}
