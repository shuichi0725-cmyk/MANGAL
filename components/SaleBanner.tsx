"use client";

import { useEffect, useState } from "react";

/**
 * Amazon のセールバナー(2026-11-24 ユーザ指示「先ほどの画像含めテスト環境に」)。
 * 画像 = アソシエイト・セントラル ヘルプ「コンテンツで使えるバナー画像を配布中」(GE5FP7BFAWDLYXVT)の配布物を
 *   そのまま表示(★商標ガイドラインで加工・編集は禁止=切り抜き/文字入れをしない)。 画像にリンクは入っていないので自分のタグで包む。
 * ★期限切れは自動で消す: 配信HTMLには出しておき(サーバー描画が空にならない=サニティ#32)、
 *   ブラウザで今日が UNTIL を過ぎていたら隠す。 次のセールは SALE を差し替える。
 */
const TAG = process.env.NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG || "mangal08-22";
const SALE = {
  name: "Amazon ブラックフライデー",
  // 先行 11/27 0:00〜・本セール 11/30〜12/7 23:59(2026-11-19 発表)
  until: "2026-12-07T23:59:59+09:00",
  href: `https://www.amazon.co.jp/blackfriday?tag=${TAG}`,
  img: "https://m.media-amazon.com/images/G/09/2026/x-site/BFW/P8sQnYf/03_ccm/BFW26_CCM_026_LUDO_Paid_yahoo_dtmb_640x360.jpg",
  w: 640,
  h: 360,
};

export function saleActiveAtBuild(): boolean {
  return Date.now() <= Date.parse(SALE.until);
}

export default function SaleBanner({ className = "" }: { className?: string }) {
  const [hidden, setHidden] = useState(false);
  useEffect(() => {
    if (Date.now() > Date.parse(SALE.until)) setHidden(true);
  }, []);
  if (hidden || !saleActiveAtBuild()) return null;
  return (
    <div className={className}>
      <p className="mb-1 text-[10.5px] text-ink/55">
        <span className="mr-1.5 bg-[#ff8a3d] px-1.5 py-px text-[10px] font-bold text-black">PR</span>
        {SALE.name}(12月7日まで)
      </p>
      <a href={SALE.href} target="_blank" rel="sponsored noopener" className="spring-press block">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={SALE.img}
          width={SALE.w}
          height={SALE.h}
          alt={`${SALE.name}のセール会場へ(Amazon)`}
          loading="lazy"
          className="h-auto w-full border border-[var(--color-line)]"
        />
      </a>
    </div>
  );
}
