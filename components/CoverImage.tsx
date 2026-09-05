"use client";

import Image from "next/image";
import { useState } from "react";

type Props = {
  src: string | null;
  alt: string;
  /** ★next/image の標準prop = 「どの解像度をダウンロードするか」のヒント(表示サイズではない)。
   *  いまは images.unoptimized=true(静的書き出し+外部ホスト直リンク)で srcset を作らないため
   *  出力されないが、最適化を有効にすれば効き始める = ★消さない(2026-09-06 確認)。
   *  実際に落ちてくる解像度は URL の ?_ex=300x300(lib/coverSlim.ts)が決めている。
   *  ★300 は高DPI端末で64〜120px枠を潰さないための意図的な値。下げない(ユーザ裁定)。
   *  拡大表示(CoverLightbox)だけが ?_ex= を外してマスター原寸を読む。 */
  sizes?: string;
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
      // 透明PNG(楽天の .gif 由来)がダーク背景を透かして斑点に見えるのを防ぐ = 書影は必ず白地の上に置く
      className="bg-white object-cover"
      unoptimized
      onError={() => setErrored(true)}
    />
  );
}
