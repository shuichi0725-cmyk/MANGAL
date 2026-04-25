"use client";

import Image from "next/image";
import { useState } from "react";

type Props = {
  src: string | null;
  alt: string;
  sizes?: string;
  /** 画面幅小さめ枠か大きめ枠か。プレースホルダのフォントサイズだけ変える */
  size?: "card" | "detail";
};

/**
 * 表紙画像。src が null か、読み込みに失敗したら "表紙なし" を表示する。
 * next/image を使うが onError で自前のプレースホルダにフォールバックする。
 */
export default function CoverImage({ src, alt, sizes, size = "card" }: Props) {
  const [errored, setErrored] = useState(false);

  const showPlaceholder = !src || errored;

  return (
    <div className="absolute inset-0">
      {showPlaceholder ? (
        <div
          className={
            "absolute inset-0 grid place-items-center text-black/40 " +
            (size === "detail" ? "text-sm" : "text-xs")
          }
        >
          表紙なし
        </div>
      ) : (
        <Image
          src={src}
          alt={alt}
          fill
          sizes={sizes}
          className="object-cover"
          unoptimized
          onError={() => setErrored(true)}
        />
      )}
    </div>
  );
}
