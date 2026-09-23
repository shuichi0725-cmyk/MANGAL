import Link from "next/link";
import { notFound } from "next/navigation";
import { authorsPages } from "@/lib/authors";
import { parsePart } from "@/lib/authorsIndex";

/** 著者索引の分割ページ(2026-09-23)。part = "<行key>-<頁番号>"(例 ka-3)。
 *  頁割りは lib/authorsIndex.ts が単一ソース(/authors 目次と共有。sitemap は out/authors の実在HTMLから拾う)。 */

const SITE = "https://mangal-db.com";

export const dynamicParams = false;

export function generateStaticParams() {
  const keys = Object.keys(authorsPages().parts).map((part) => ({ part }));
  // ★空ガード(/titles/[part] と同型): output: export は params 0件でビルドが落ちるため placeholder を返す
  return keys.length > 0 ? keys : [{ part: "_empty" }];
}

function partMeta(part: string) {
  const ap = authorsPages();
  const rows = ap.parts[part];
  const pp = parsePart(part);
  if (!rows || !pp) return null;
  const gyo = ap.gyo.find((g) => g.key === pp.gyoKey);
  if (!gyo) return null;
  return { rows, gyoKey: pp.gyoKey, page: pp.page, gyo };
}

export async function generateMetadata({ params }: { params: Promise<{ part: string }> }) {
  const { part } = await params;
  const pm = partMeta(part);
  if (!pm) return {};
  const rep = pm.rows.slice(0, 3).map((a) => a.name).join("・");
  return {
    title: `著者一覧 ${pm.gyo.label}(${pm.page}/${pm.gyo.pages}ページ)`,
    description:
      `名前が${pm.gyo.label}で始まる漫画家・原作者の一覧、その${pm.page}。` +
      `${rep}など${pm.rows.length}名を50音順で掲載。各著者の全作品(全巻一覧・発売日)へ。`,
    alternates: { canonical: `${SITE}/authors/${part}` },
  };
}

export default async function AuthorsPartPage({ params }: { params: Promise<{ part: string }> }) {
  const { part } = await params;
  const pm = partMeta(part);
  if (!pm) notFound();
  const { rows, gyoKey, page, gyo } = pm!;
  const prev = page > 1 ? `/authors/${gyoKey}-${page - 1}` : null;
  const next = page < gyo.pages ? `/authors/${gyoKey}-${page + 1}` : null;
  const pager = (
    <nav className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[13px] font-bold">
      {prev ? (
        <Link href={prev} className="hover:text-[var(--color-accent)]">← 前の頁</Link>
      ) : (
        <span className="text-ink/30">← 前の頁</span>
      )}
      {/* 同じ行の全頁番号 = 深い頁も1クリック(ハブ面の頁送りと同じ考え方) */}
      <span className="flex flex-wrap gap-1">
        {Array.from({ length: gyo.pages }, (_, i) =>
          i + 1 === page ? (
            <span key={i} className="rounded bg-[var(--color-accent)] px-2 py-0.5 text-[12px] text-white">{i + 1}</span>
          ) : (
            <Link
              key={i}
              href={`/authors/${gyoKey}-${i + 1}`}
              className="rounded border border-[var(--color-line)] px-2 py-0.5 text-[12px] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
            >
              {i + 1}
            </Link>
          ),
        )}
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
      <div className="mx-auto max-w-4xl px-4 py-8 lg:max-w-none">
        <nav className="text-[12px] text-ink/55">
          <Link href="/" className="hover:text-ink">ホーム</Link> ›{" "}
          <Link href="/authors" className="hover:text-ink">著者一覧</Link> › {gyo.label} {page}
        </nav>
        <h1 className="mt-2 text-2xl font-extrabold">
          著者一覧 {gyo.label}
          <span className="ml-2 text-[12px] font-semibold text-ink/45">
            {page}/{gyo.pages}ページ
          </span>
        </h1>
        <div className="mt-3">{pager}</div>
        <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1.5">
          {rows.map((a) => (
            <Link key={a.key} href={`/author/${a.key}`} className="text-[13px] hover:text-[var(--color-accent)]">
              {a.name}
              <span className="ml-1 text-[10px] text-ink/40">{a.n}</span>
            </Link>
          ))}
        </div>
        <div className="mt-6">{pager}</div>
      </div>
    </div>
  );
}
