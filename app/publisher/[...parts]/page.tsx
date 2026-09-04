import Link from "next/link";
import { notFound } from "next/navigation";
import HubListPage from "@/components/HubListPage";
import { hubDefs, hubHref, hubMeta, hubStaticParams, resolveHubParts } from "@/lib/hubs";

/** 出版社別 漫画一覧(2026-09-04 SEO ハブ面)。 /publisher/<key>(1頁目) と /publisher/<key>/<n>(続き)。
 *  対象は HUB_MIN.publisher(50作)以上の社 ≈ 100社。 それ未満の社は作品頁チップが /browse? にフォールバック。 */

const KIND = "publisher" as const;
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

export default async function PublisherHubPage({ params }: P) {
  const { parts } = await params;
  const r = resolveHubParts(KIND, parts);
  if (!r) notFound();
  const { def, page } = r!;
  const mags = hubDefs("magazine").filter((d) => d.publisher === def.key);
  const lead = `全${def.count.toLocaleString()}作品（完結${def.completed.toLocaleString()}）・人気順`;
  const extra =
    mags.length > 0 ? (
      <p>
        主な連載誌:{" "}
        {mags.map((d, i) => (
          <span key={d.key}>
            {i > 0 && " / "}
            <Link href={hubHref("magazine", d.key)} className="text-[var(--color-accent)] hover:underline">{d.name}</Link>
          </span>
        ))}
      </p>
    ) : undefined;
  return <HubListPage def={def} page={page} lead={lead} extra={extra} />;
}
