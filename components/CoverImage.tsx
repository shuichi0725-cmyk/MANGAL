"use client";

import Image from "next/image";
import { useState } from "react";

type Props = {
  src: string | null;
  alt: string;
  sizes?: string;
  /** 画面幅小さめ枠か大きめ枠か。 (現状は描画ロジックに影響しないが API 互換のため残す) */
  size?: "card" | "detail";
};

/**
 * 表紙画像。 src が null か読み込み失敗 (onError) なら **何も描画しない** (null を返す)。
 *
 * 親側で `{cover && <div className="relative aspect-[2/3] bg-black/5 ...">...</div>}`
 * の形で wrapper を conditional 化することで、 cover が無いシリーズは灰色枠ごと
 * 完全に消える。 将来 Amazon PA-API 等で cover_url が入った時、 自然に表示される。
 */
export default function CoverImage({ src, alt, sizes }: Props) {
  const [errored, setErrored] = useState(false);

  if (!src || errored) return null;

  return (
    <Image
      src={src}
      alt={alt}
      fill
      sizes={sizes}
      className="object-cover"
      unoptimized
      onError={() => setErrored(true)}
    />
  );
}
