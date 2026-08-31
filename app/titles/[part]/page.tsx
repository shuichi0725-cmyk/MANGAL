import Link from "next/link";
import { notFound } from "next/navigation";
import { loadTitlesPages, type TitlesEntry } from "@/lib/loadData";
import { DesignNav } from "@/lib/homeDesign";

/** 題名索引の分割ページ(2026-08-31 SEO)。part = "<行key>-<頁番号>"(例 ka-3)。
 *  頁割り・並び順は data/titles-pages.json(_gen-titles-pages.py)が単一ソース=sitemapと不整合しない。 */

const SITE = "https://mangal-db.com";

export const dynamicParams = false;

export function generateStaticParams() {
  const keys = Object.keys(loadTitlesPages().parts).map((part) => ({ part }));
  // ★空ガード(/author/[key] と同型): output: export は params 0件でビルドが落ちるため
  //   placeholder を返す(頁側は parts 不在→404 フォールバック)。
  return keys.length > 0 ? keys : [{ part: "_empty" }];
}

function partMeta(part: string) {
  const tp = loadTitlesPages();
  const rows = tp.parts[part];
  if (!rows) return null;
  const i = part.lastIndexOf("-");
  const gyoKey = part.slice(0, i);
  const page = Number(part.slice(i + 1));
  const gyo = tp.gyo.find((g) => g.key === gyoKey);
  if (!gyo) return null;
  return { tp, rows, gyoKey, page, gyo };
}

export async function generateMetadata({ params }: { params: Promise<{ part: string }> }) {
  const { part } = await params;
  const pm = partMeta(part);
  if (!pm) return {};
  const rep = pm.rows.slice(0, 3).map((r) => `『${r[1]}』`).join("");
  return {
    title: `題名索引 ${pm.gyo.label}(${pm.page}/${pm.gyo.pages}ページ)`,
    description: `題名が${pm.gyo.label}で始まる漫画作品の一覧、その${pm.page}。${rep}など${pm.rows.length}作品を50音順で掲載。`,
    alternates: { canonical: `${SITE}/titles/${part}` },
  };
}

function Row({ e }: { e: TitlesEntry }) {
  const [slug, title, kana, authors, year, vols] = e;
  const sub = [authors, year ? `${year}年` : null, vols ? `全${vols}巻` : null]
    .filter(Boolean)
    .join(" ・ ");
  return (
    <li className="border-b border-[var(--color-line)] py-2">
      <Link
        href={`/manga/${slug}`}
        className="text-[14px] font-bold hover:text-[var(--color-accent)]"
      >
        {title}
      </Link>
      {kana && <span className="ml-2 text-[10.5px] text-ink/40">{kana}</span>}
      {sub && <p className="mt-0.5 text-[11.5px] text-ink/55">{sub}</p>}
    </li>
  );
}

export default async function TitlesPartPage({ params }: { params: Promise<{ part: string }> }) {
  const { part } = await params;
  const pm = partMeta(part);
  if (!pm) notFound();
  const { rows, gyoKey, page, gyo } = pm!;
  const prev = page > 1 ? `/titles/${gyoKey}-${page - 1}` : null;
  const next = page < gyo.pages ? `/titles/${gyoKey}-${page + 1}` : null;
  const pager = (
    <nav className="flex items-center gap-3 text-[13px] font-bold">
      {prev ? (
        <Link href={prev} className="hover:text-[var(--color-accent)]">← 前の頁</Link>
      ) : (
        <span className="text-ink/30">← 前の頁</span>
      )}
      <span className="text-[11.5px] font-semibold text-ink/50">
        {page} / {gyo.pages}
      </span>
      {next ? (
        <Link href={next} className="hover:text-[var(--color-accent)]">次の頁 →</Link>
      ) : (
        <span className="text-ink/30">次の頁 →</span>
      )}
    </nav>
  );
  return (
    <div>
      <DesignNav />
      <div className="mx-auto max-w-4xl px-4 py-8">
        <nav className="text-[12px] text-ink/55">
          <Link href="/" className="hover:text-ink">ホーム</Link> ›{" "}
          <Link href="/titles" className="hover:text-ink">題名索引</Link> › {gyo.label} {page}
        </nav>
        <h1 className="mt-2 text-2xl font-extrabold">
          題名索引 {gyo.label}
          <span className="ml-2 text-[12px] font-semibold text-ink/45">
            {page}/{gyo.pages}ページ
          </span>
        </h1>
        <div className="mt-3">{pager}</div>
        <ol className="mt-4">
          {rows.map((e) => (
            <Row key={e[0]} e={e} />
          ))}
        </ol>
        <div className="mt-5">{pager}</div>
      </div>
    </div>
  );
}
