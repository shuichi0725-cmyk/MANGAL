"use client";

import { dotGothic } from "@/lib/fonts";

/** D3ヒーロー → E融合型(2026-08-15 ユーザ指示「ヘッダーから検索窓までEを取り入れる」):
 *  - コピーは固定「次の一冊が、見つかる。」(E案採用。旧ランダムコピー16種は退役=履歴はgit)
 *  - サブテキストは「N作品・M冊の書誌を収録。」まで(ユーザ指示「書影以降はいらない」)
 *  - 検索窓=ターミナル式 mangal> プロンプト+点滅カーソル。素のGETフォーム=JS前でも検索できる
 *    (ボタンは無し=Enter/検索キーで送信。E案の見た目を優先)
 *  - 走査線背景(E案)。SEO対策=巨大タイポはh1にしない(h1相当はページ側のsr-only) */
export default function HeroD3({ total, books }: { total: number; books: number }) {
  return (
    <section
      className="relative overflow-hidden border-b-[3px] border-[var(--color-accent)] px-4 pb-6 pt-7"
      style={{
        background:
          "repeating-linear-gradient(0deg, transparent 0px, transparent 3px, rgba(217,248,67,0.02) 3px, rgba(217,248,67,0.02) 4px)",
      }}
    >
      <div className="mb-3 text-[9.5px] tracking-[0.24em] text-ink/50">// 日本の漫画データベース</div>
      {/* 装飾タイポ(h1ではない) */}
      <p className={`${dotGothic.className} text-[37px] leading-[1.32] text-ink`}>
        次の一冊が、
        <br />
        見つかる<span className="text-[var(--color-accent)]">。</span>
      </p>
      <p className="mt-3 text-[11px] leading-relaxed text-ink/65">
        {total.toLocaleString()}作品・{books.toLocaleString()}冊の書誌を収録。
      </p>
      {/* 素のGETフォーム=JS前でも検索できる(/browseのシェルと同じ思想) */}
      <form
        action="/browse"
        method="get"
        className="mt-5 flex items-center gap-2 border-2 border-[var(--color-accent)] bg-[#050505] px-3.5 py-3 shadow-[3px_3px_0_rgba(217,248,67,0.14)]"
      >
        <span className="shrink-0 text-[12.5px] font-bold text-[var(--color-accent)]">mangal&gt;</span>
        <input
          type="search"
          name="q"
          placeholder="作品名・著者名で検索"
          aria-label="作品を検索"
          className="d3-plain min-w-0 flex-1 text-[14px] font-bold text-[var(--color-ink)] outline-none"
        />
        <span aria-hidden="true" className="d3-blink h-[15px] w-2 shrink-0 bg-[var(--color-accent)]" />
      </form>
    </section>
  );
}
