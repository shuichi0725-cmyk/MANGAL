"use client";

import { buildAmazonUrlForVolume, buildKindleUrlForVolume } from "@/lib/amazon";
import { primaryVolume, type Manga, type Volume } from "@/lib/schema";
import { usePurchaseMode } from "./PurchaseMode";

type Props = {
  manga: Manga;
  /** 指定が無ければ volumes[0] を使う */
  volume?: Volume;
  className?: string;
  /** aria-label の接頭辞 (例: "ONE PIECE 5巻")。 ストア名はモードで自動付与。 */
  labelPrefix?: string;
};

/**
 * 購入ボタン。 ★購入モード ([[PurchaseMode]]) に応じて 見た目もリンク先も切替:
 *  - print  → Amazon (紙) /dp/{asin} or 書籍検索
 *  - ebook  → Kindle (電子) /dp/{kindle_asin} or Kindleストア検索
 * ストアを増やす時はここに分岐を足すだけ (フォルダ不要)。
 */
export default function AffiliateLink({ manga, volume, className, labelPrefix }: Props) {
  const { mode } = usePurchaseMode();
  const tag = process.env.NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG ?? "";
  const locale = process.env.NEXT_PUBLIC_AMAZON_LOCALE ?? "jp";
  const target = volume ?? primaryVolume(manga);
  const ebook = mode === "ebook";

  const href = ebook
    ? buildKindleUrlForVolume(target, manga, { associateTag: tag, locale })
    : buildAmazonUrlForVolume(target, manga, { associateTag: tag, locale });
  const store = ebook ? "Kindle" : "アマゾン";
  const icon = ebook ? "📱" : "📖";

  return (
    <a
      href={href}
      target="_blank"
      rel="nofollow sponsored noopener"
      className={className}
      aria-label={`${labelPrefix ? `${labelPrefix} を ` : ""}${store} で見る`}
    >
      <span aria-hidden className="mr-1">
        {icon}
      </span>
      {store}
    </a>
  );
}
