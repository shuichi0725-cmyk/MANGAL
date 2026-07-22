import Link from "next/link";
import CoverImage from "@/components/CoverImage";
import MarqueeTitle from "@/components/MarqueeTitle";
import { coverUrl, type Manga } from "@/lib/schema";

/** 関連作品 = ①シリーズ/フランチャイズ(題名の前方一致) ②同作者(作画/原作の名前共有)。
 *  説明と版リストの間に置く想定(= 横スクロール1行・高さ最小で購買導線を圧迫しない)。 */
export function computeRelated(manga: Manga, all: Manga[], limit = 10) {
  // ★空白違いの同一人物を束ねる(authorKey相当。蟹沢ちひろ分裂対策 2026-07-21)
  const nk = (s: string) => s.replace(/[\s　]+/g, "");
  const names = new Set(
    [...manga.authors, ...manga.original_authors].map((a) => nk(a.name)),
  );
  // ★多人数名義ガード(2026-07-15 ソーサリアン型=単巻読切連番の統合頁・著者14人):
  //   著者5人以上の頁は「同作者」スコアを使わない(各作家の全作品が無関係に並ぶため)。pin/シリーズ一致のみ。
  const manyAuthors = names.size >= 5;
  const t = manga.title;
  // ★pin: related_pin の slug は順序保持で最優先(例: ドラえもん→大長編ドラえもん)
  const pinRank = new Map((manga.related_pin ?? []).map((s, i) => [s, i]));
  const scored: Array<{ m: Manga; score: number; why: string }> = [];
  for (const m of all) {
    if (m.slug === manga.slug) continue;
    if (pinRank.has(m.slug)) {
      scored.push({ m, score: 1000 - (pinRank.get(m.slug) ?? 0), why: "シリーズ" });
      continue;
    }
    let score = 0;
    let why = "";
    // シリーズ/スピンオフ = 題名の前方一致(4字以上)
    const pre = t.length >= 4 && m.title.startsWith(t.slice(0, Math.min(t.length, 6)));
    const pre2 = m.title.length >= 4 && t.startsWith(m.title.slice(0, Math.min(m.title.length, 6)));
    if (pre || pre2) {
      score += 10;
      why = "シリーズ";
    }
    const shared = !manyAuthors && [...m.authors, ...m.original_authors].some((a) => names.has(nk(a.name)));
    if (shared) {
      score += 5;
      if (!why) why = "同作者";
    }
    if (score > 0) scored.push({ m, score, why });
  }
  scored.sort((a, b) => b.score - a.score || (b.m.year_started ?? 0) - (a.m.year_started ?? 0));
  return scored.slice(0, limit);
}

export default function RelatedWorks({
  items,
}: {
  items: Array<{ m: Manga; why: string }>;
}) {
  if (items.length === 0) return null;
  return (
    <section className="mt-6">
      <h2 className="text-sm font-semibold text-ink/70 mb-2">関連作品</h2>
      <ul className="flex gap-3 overflow-x-auto no-scrollbar pb-2 -mx-1 px-1 snap-x scroll-pl-1">
        {items.map(({ m, why }) => {
          // 検索索引・詳細ページ本体と同じフォールバック(1巻に書影が無ければ表紙のある巻へ)。
          // 主版1巻だけ書影未取得の作品(うる星やつら型)が関連欄で欠落するのを防ぐ。
          const cover = coverUrl(m);
          return (
            <li key={m.slug} className="shrink-0 w-[104px] snap-start">
              <Link href={`/manga/${m.slug}`} className="block group">
                <div className="relative aspect-[2/3] rounded overflow-hidden bg-[var(--color-surface-2)] border border-[var(--color-line)]">
                  {cover ? (
                    <CoverImage src={cover} alt={m.title} sizes="104px" size="card" />
                  ) : (
                    <div className="absolute inset-0 flex items-center justify-center p-1.5 text-center text-[10px] leading-tight text-ink/45">
                      {m.title.slice(0, 24)}
                    </div>
                  )}
                  <span className="absolute top-1 left-1 rounded bg-black/55 px-1 py-px text-[9px] font-medium text-white">
                    {why}
                  </span>
                </div>
                <MarqueeTitle
                  text={m.title}
                  className="mt-1 text-[11px] leading-snug text-ink/80 group-hover:text-[var(--color-accent)]"
                />
                <p className="truncate text-[10px] text-ink/45">
                  {m.authors.map((a) => a.name).join("・")}
                  {m.year_started ? ` ・ ${m.year_started}` : ""}
                </p>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
