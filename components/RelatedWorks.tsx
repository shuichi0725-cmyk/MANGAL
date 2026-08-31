import Link from "next/link";
import CoverImage from "@/components/CoverImage";
import MarqueeTitle from "@/components/MarqueeTitle";
import { coverUrl, type Manga } from "@/lib/schema";

/** 関連作品 = ①シリーズ/フランチャイズ(題名の前方一致) ②同作者(作画/原作の名前共有)
 *  ③穴埋め(同誌/同ジャンル×近い年 2026-08-31 SEO)。
 *  説明と版リストの間に置く想定(= 横スクロール1行・高さ最小で購買導線を圧迫しない)。
 *  ★選定ロジックは lib/related.ts(vitest が JSX 変換なし構成のため .tsx から分離)。 */
export { computeRelated } from "@/lib/related";

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
