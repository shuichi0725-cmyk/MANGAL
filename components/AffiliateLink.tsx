import { buildAmazonUrlForVolume } from "@/lib/amazon";
import { primaryVolume, type Manga, type Volume } from "@/lib/schema";

type Props = {
  manga: Manga;
  /** 指定が無ければ volumes[0] を使う */
  volume?: Volume;
  className?: string;
  children?: React.ReactNode;
  ariaLabel?: string;
};

export default function AffiliateLink({
  manga,
  volume,
  className,
  children,
  ariaLabel,
}: Props) {
  const tag = process.env.NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG ?? "";
  const locale = process.env.NEXT_PUBLIC_AMAZON_LOCALE ?? "jp";
  const target = volume ?? primaryVolume(manga);
  const href = buildAmazonUrlForVolume(target, manga, { associateTag: tag, locale });

  return (
    <a
      href={href}
      target="_blank"
      rel="nofollow sponsored noopener"
      className={className}
      aria-label={ariaLabel}
    >
      {children ?? "Amazonで購入"}
    </a>
  );
}
