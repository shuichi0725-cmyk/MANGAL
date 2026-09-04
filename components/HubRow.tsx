import Link from "next/link";
import { authorKeyFor } from "@/lib/authors";
import { hubHrefIfExists, magazineName, publisherName, type HubKind } from "@/lib/hubs";
import type { MangaListItem } from "@/lib/schema";

/** ハブ面(雑誌別/出版社別/年別)の1行(server)。 題→作品頁、著者→著者頁(keyが解決できる時)、
 *  連載誌→雑誌ハブ(在る時)。 年・出版社は文字のみ(= 同じハブへの重複リンクを300行ぶん撒かない)。
 *  書影は出さない(300行×画像で頁が重くなる。 索引面は題名索引と同じ文字行)。 */
export default function HubRow({ m, omit }: { m: MangaListItem; omit?: HubKind }) {
  const vols = m.max_edition_volumes || 0;
  const volLabel = vols > 0 ? (m.status === "completed" ? `全${vols}巻` : `既刊${vols}巻`) : null;
  const status = m.status === "ongoing" ? "連載中" : m.status === "hiatus" ? "休載中" : null;
  const year = omit !== "year" && m.year_started > 0 ? `${m.year_started}年` : null;
  const mag =
    omit !== "magazine" && m.magazine
      ? { name: magazineName(m.magazine), href: hubHrefIfExists("magazine", m.magazine) }
      : null;
  const pub = omit !== "publisher" && m.publisher ? publisherName(m.publisher) : null;
  return (
    <li className="border-b border-[var(--color-line)] py-2">
      <Link href={`/manga/${m.slug}`} className="text-[14px] font-bold hover:text-[var(--color-accent)]">
        {m.title}
      </Link>
      {m.title_kana && <span className="ml-2 text-[10.5px] text-ink/40">{m.title_kana}</span>}
      <p className="mt-0.5 flex flex-wrap gap-x-2 text-[11.5px] text-ink/55">
        {m.authors.length > 0 && (
          <span>
            {m.authors.map((a, i) => {
              const k = authorKeyFor(a.name);
              return (
                <span key={`${a.name}-${i}`}>
                  {i > 0 && "・"}
                  {k ? (
                    <Link href={`/author/${k}`} className="hover:text-ink">
                      {a.name}
                    </Link>
                  ) : (
                    a.name
                  )}
                </span>
              );
            })}
          </span>
        )}
        {year && <span>{year}</span>}
        {status && <span>{status}</span>}
        {volLabel && <span>{volLabel}</span>}
        {mag?.name && (
          <span>
            {mag.href ? (
              <Link href={mag.href} className="hover:text-ink">
                {mag.name}
              </Link>
            ) : (
              mag.name
            )}
          </span>
        )}
        {pub && <span>{pub}</span>}
      </p>
    </li>
  );
}
