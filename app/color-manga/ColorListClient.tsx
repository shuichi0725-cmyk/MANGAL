import CoverImage from "@/components/CoverImage";
import { kindleSearchUrl } from "@/lib/kindleLink";
import { loadColorEditions } from "@/lib/cornerData";

/** ★2026-09-18 server化: 旧は "use client" + fetch("/data/color-editions.json") で、
 *  配信HTMLが「読み込み中…」だけ=作品リンク0本だった(番人 _check-ssr-content.py が検出)。
 *  この頁は絞り込みも並び替えも無い純粋なリストなので、client のままにする理由が無い。
 *  同じJSONを build 時に fs で読んで全件をHTMLに焼く。 */
export default function ColorListClient() {
  const data = loadColorEditions();
  const rows = Object.entries(data).sort((a, b) => b[1].v - a[1].v || (a[1].t ?? "").localeCompare(b[1].t ?? "", "ja"));
  return (
    <div className="px-4 pb-8">
      <p className="mb-2 text-[11px] text-ink/50">{rows.length}作品</p>
      <ul className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-6">
        {rows.map(([slug, e]) => {
          // ★書影タップ=Kindle購入リンクへ直行(2026-08-12 ユーザ裁定。ホームのカラー版コーナーと同じ)。
          //   作品頁には飛ばさない=作品頁は紙の書誌でカラー版を出していないため。ブラウザ起動はopenKindleInBrowser。
          const href = kindleSearchUrl(e.t ?? slug);
          return (
          <li key={slug}>
            <a
              href={href}
              target="_blank"
              rel="nofollow sponsored noopener"
              aria-label={`${e.t ?? slug} をKindleで見る`}
              className="spring-press block"
            >
              <div
                className="relative overflow-hidden rounded-md border border-[var(--color-line)] bg-[var(--color-surface-2)]"
                style={{ aspectRatio: "2 / 3" }}
              >
                {e.c ? (
                  <CoverImage src={e.c} alt={e.t ?? slug} sizes="(max-width: 640px) 33vw, 16vw" />
                ) : (
                  <span className="flex h-full w-full items-center justify-center text-[9px] text-ink/40">no image</span>
                )}
              </div>
              <p className="mt-1 line-clamp-2 text-[11px] font-bold leading-snug">{e.t ?? slug}</p>
              <p className="text-[10px] text-ink/55">全{e.v}巻</p>
            </a>
          </li>
          );
        })}
      </ul>
      <p className="mt-4 text-[10px] text-ink/40">[PR] 各作品のリンクにはアフィリエイト広告を含みます(Kindleストアへ移動します)</p>
    </div>
  );
}
