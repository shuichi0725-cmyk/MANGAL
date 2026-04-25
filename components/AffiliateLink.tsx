import { buildAmazonUrl } from "@/lib/amazon";
import type { Manga } from "@/lib/schema";

type Props = {
  manga: Manga;
  className?: string;
  children?: React.ReactNode;
};

export default function AffiliateLink({ manga, className, children }: Props) {
  const tag = process.env.NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG ?? "";
  const locale = process.env.NEXT_PUBLIC_AMAZON_LOCALE ?? "jp";
  const href = buildAmazonUrl(manga, { associateTag: tag, locale });

  return (
    <a
      href={href}
      target="_blank"
      rel="nofollow sponsored noopener"
      className={className}
    >
      {children ?? "Amazonで購入"}
    </a>
  );
}
