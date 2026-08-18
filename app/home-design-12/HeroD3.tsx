"use client";

import { useEffect } from "react";
import { dotGothic } from "@/lib/fonts";

/** ★索引アイドル先読み(2026-08-18 ユーザ裁定②): ホームの検索はGET遷移で/browseに飛ぶため、
 *  遷移先で6MB(br)の一覧索引DLがコールドスタートの主犯だった。ホーム表示後の手すきで
 *  fetchしてHTTPキャッシュ(max-age=4h)を温めておく=遷移後はディスクキャッシュから瞬時。
 *  - 主トリガー: requestIdleCallback(初描画を邪魔しない) / 保険: 検索窓フォーカス時に即開始
 *  - 節度: saveData/2G回線ではアイドル先読みをスキップ(フォーカス=明示的な検索意思の時だけ)
 *  - デコードはしない(MPA遷移でメモリは引き継がれないためDLキャッシュだけが価値) */
let _warmed = false;
function warmIndex(): void {
  if (_warmed) return;
  _warmed = true;
  fetch("/manga-list-index.json").then((r) => r.blob()).catch(() => {
    _warmed = false; // 失敗時は再試行可
  });
}
function warmIndexIdle(): void {
  type NetInfo = { saveData?: boolean; effectiveType?: string };
  const conn = (navigator as { connection?: NetInfo }).connection;
  if (conn?.saveData || /2g/.test(conn?.effectiveType ?? "")) return;
  if (typeof requestIdleCallback === "function") requestIdleCallback(() => warmIndex(), { timeout: 4000 });
  else setTimeout(warmIndex, 1500);
}

/** D3ヒーロー → E融合型(2026-08-15 ユーザ指示「ヘッダーから検索窓までEを取り入れる」):
 *  - コピーは固定「次の一冊が、見つかる。」(E案採用。旧ランダムコピー16種は退役=履歴はgit)
 *  - サブテキストは「N作品・M冊の書誌を収録。」まで(ユーザ指示「書影以降はいらない」)
 *  - 検索窓=ターミナル式 mangal> プロンプト+点滅カーソル。素のGETフォーム=JS前でも検索できる
 *    (ボタンは無し=Enter/検索キーで送信。E案の見た目を優先)
 *  - 走査線背景(E案)。SEO対策=巨大タイポはh1にしない(h1相当はページ側のsr-only) */
export default function HeroD3({ total, books }: { total: number; books: number }) {
  useEffect(() => {
    warmIndexIdle();
  }, []);
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
          onFocus={warmIndex}
          className="d3-plain min-w-0 flex-1 text-[14px] font-bold text-[var(--color-ink)] outline-none"
        />
        <span aria-hidden="true" className="d3-blink h-[15px] w-2 shrink-0 bg-[var(--color-accent)]" />
      </form>
    </section>
  );
}
