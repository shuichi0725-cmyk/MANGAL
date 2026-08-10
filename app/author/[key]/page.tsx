import Link from "next/link";
import { notFound } from "next/navigation";
import { allAuthorKeys, getAuthor, type AuthorWork } from "@/lib/authors";
import CoverImage from "@/components/CoverImage";
import { DesignNav } from "@/lib/homeDesign";

/** 著者静的ページ(2026-08-10 preview試作)。
 *  「著者名 作品一覧」検索の受け皿+内部リンクハブ(/browse?author= クエリの静的置換)。 */

const SITE = "https://mangal-db.com";

export const dynamicParams = false;

export async function generateStaticParams() {
  return allAuthorKeys().map((key) => ({ key }));
}

export async function generateMetadata({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const a = getAuthor(key);
  if (!a) return {};
  const n = a.works.length + a.originals.length;
  const rep = [...a.works, ...a.originals].slice(0, 3).map((w) => w.title).join("、");
  const title = `${a.name}の漫画作品一覧(${n}作品)`;
  return {
    title,
    description: `${a.name}${a.kana ? `(${a.kana})` : ""}の漫画作品${n}作を発表年順に掲載。${rep}など。各作品の全巻一覧・発売日・ISBN情報つき。`,
    alternates: { canonical: `${SITE}/author/${key}` },
  };
}

function WorkGrid({ works }: { works: AuthorWork[] }) {
  return (
    <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-6">
      {works.map((w) => (
        <Link key={`${w.slug}-${w.role}`} href={`/manga/${w.slug}`} className="group">
          <div className="relative overflow-hidden rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-2)]" style={{ aspectRatio: "2 / 3" }}>
            {w.cover ? (
              <CoverImage src={w.cover} alt={w.title} sizes="140px" />
            ) : (
              <span className="flex h-full w-full items-center justify-center p-1 text-center text-[10px] text-ink/50">{w.title}</span>
            )}
          </div>
          <div className="mt-1 line-clamp-2 text-[11.5px] font-semibold leading-tight group-hover:text-[var(--color-accent)]">{w.title}</div>
          {w.year && <div className="text-[10px] text-ink/45">{w.year}年</div>}
        </Link>
      ))}
    </div>
  );
}

export default async function AuthorPage({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const a = getAuthor(key);
  if (!a) notFound();
  const n = a.works.length + a.originals.length;
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Person",
    name: a.name,
    url: `${SITE}/author/${key}`,
    jobTitle: "漫画家",
  };
  const breadcrumbLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "ホーム", item: `${SITE}/` },
      { "@type": "ListItem", position: 2, name: "著者一覧", item: `${SITE}/authors` },
      { "@type": "ListItem", position: 3, name: a.name, item: `${SITE}/author/${key}` },
    ],
  };
  return (
    <div>
      <DesignNav />
      <div className="mx-auto max-w-4xl px-4 py-8">
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbLd) }} />
        <nav className="text-[11px] text-ink/45">
          <Link href="/" className="hover:text-ink">ホーム</Link> › <Link href="/authors" className="hover:text-ink">著者一覧</Link> › {a.name}
        </nav>
        <h1 className="mt-2 text-2xl font-extrabold">{a.name}</h1>
        {a.kana && <p className="text-[12px] text-ink/50">{a.kana}</p>}
        <p className="mt-1 text-[13px] text-ink/70">漫画作品 {n}作</p>

        {a.works.length > 0 && (
          <section className="mt-6">
            <h2 className="mb-3 text-[15px] font-bold">作品({a.works.length})</h2>
            <WorkGrid works={a.works} />
          </section>
        )}
        {a.originals.length > 0 && (
          <section className="mt-8">
            <h2 className="mb-3 text-[15px] font-bold">原作を担当した作品({a.originals.length})</h2>
            <WorkGrid works={a.originals} />
          </section>
        )}
      </div>
    </div>
  );
}
