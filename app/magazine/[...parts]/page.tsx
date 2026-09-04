import Link from "next/link";
import { notFound } from "next/navigation";
import HubListPage from "@/components/HubListPage";
import {
  demographicName,
  hubDefs,
  hubHref,
  hubHrefIfExists,
  hubMeta,
  hubStaticParams,
  publisherName,
  resolveHubParts,
} from "@/lib/hubs";

/** 雑誌別 連載作品一覧(2026-09-04 SEO ハブ面)。 /magazine/<key>(1頁目) と /magazine/<key>/<n>(続き)。
 *  対象・頁割り・文言は lib/hubs.ts が単一ソース。 sitemap は out/ の実在HTMLから拾う。 */

const KIND = "magazine" as const;
const SITE = "https://mangal-db.com";

export const dynamicParams = false;

export function generateStaticParams() {
  return hubStaticParams(KIND);
}

type P = { params: Promise<{ parts: string[] }> };

export async function generateMetadata({ params }: P) {
  const { parts } = await params;
  const r = resolveHubParts(KIND, parts);
  if (!r) return {};
  const { title, description } = hubMeta(r.def, r.page);
  const url = `${SITE}${hubHref(KIND, r.def.key, r.page)}`;
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: { title, description, url, type: "website", siteName: "MANGAL" },
  };
}

export default async function MagazineHubPage({ params }: P) {
  const { parts } = await params;
  const r = resolveHubParts(KIND, parts);
  if (!r) notFound();
  const { def, page } = r!;
  const pub = publisherName(def.publisher);
  const pubHref = hubHrefIfExists("publisher", def.publisher);
  const demo = demographicName(def.demographic);
  const siblings = hubDefs(KIND).filter((d) => d.publisher === def.publisher && d.key !== def.key);
  const lead = `全${def.count.toLocaleString()}作品（完結${def.completed.toLocaleString()}）・連載開始年順${demo ? `・${demo}向け` : ""}`;
  const extra = (
    <>
      {pub && (
        <p>
          出版社:{" "}
          {pubHref ? (
            <Link href={pubHref} className="text-[var(--color-accent)] hover:underline">{pub}</Link>
          ) : (
            pub
          )}
        </p>
      )}
      {siblings.length > 0 && (
        <p>
          同じ出版社の雑誌:{" "}
          {siblings.map((d, i) => (
            <span key={d.key}>
              {i > 0 && " / "}
              <Link href={hubHref(KIND, d.key)} className="text-[var(--color-accent)] hover:underline">{d.name}</Link>
            </span>
          ))}
        </p>
      )}
    </>
  );
  return <HubListPage def={def} page={page} lead={lead} extra={extra} />;
}
