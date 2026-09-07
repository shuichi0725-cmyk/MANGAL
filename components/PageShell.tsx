"use client";

import { usePathname } from "next/navigation";

/**
 * PC左レール付きの共通シェル(★2026-09-07 ユーザ要望「左の検索は全ページで表示」)。
 *
 * ★lg(1024px)未満では rail が `hidden lg:block` で消えるので、モバイルの見た目は完全に不変。
 * ★ホーム(`/`)だけは対象外 = 全幅のマーキー帯 + 自前レールの専用レイアウトを持っており、
 *   ここで器に入れると帯が途中で切れる。ホームは従来どおり自分でレールを描く。
 * ★器の幅: 1440 - px-4×2 - レール260 - gap24 ≒ 本文1124px。
 *   これで **器を1つも持っていなかった /list・過去ログ**(全幅に伸びていた)も自動で収まる。
 */
export default function PageShell({
  rail,
  children,
}: {
  rail: React.ReactNode;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  if (pathname === "/") return <>{children}</>;
  return (
    <div className="mx-auto flex w-full max-w-[1440px] gap-6 lg:px-4">
      {rail}
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
