import Link from "next/link";

/** 全頁共通フッター(2026-07-03): コーナー一覧 + データ出典 + 広告開示 + 規約類。 */
export default function SiteFooter() {
  const corners: Array<[string, string]> = [
    ["ホーム", "/"],
    ["一覧", "/list"],
    ["検索", "/browse"],
    ["三世代 過去ログ", "/sansedai-archive"],
    ["AI書評家リーグ", "/column-ai-league"],
    ["画集", "/art-books"],
    ["使い方", "/about"],
  ];
  return (
    <footer className="mt-10 border-t border-[var(--color-line)] bg-[var(--color-surface)] px-5 py-6 text-[11px] text-ink/55">
      <p className="text-[13px] font-extrabold text-ink/80">
        MANGAL<span className="text-[var(--color-accent)]">.</span>
        <span className="ml-2 text-[10px] font-semibold text-ink/45">日本の漫画データベース</span>
      </p>
      <nav className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
        {corners.map(([label, href]) => (
          <Link key={href + label} href={href} className="hover:text-ink">
            {label}
          </Link>
        ))}
      </nav>
      <p className="mt-4 leading-relaxed">
        出典: メディア芸術データベース(文化庁) / 国立国会図書館サーチ / 楽天ブックス / AniList / Wikidata。
        書影は楽天ブックスの商品情報を利用しています。
      </p>
      <p className="mt-1.5 leading-relaxed">[PR] 店舗リンクにはアフィリエイト広告を含みます。</p>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1">
        <Link href="/terms" className="hover:text-ink">利用規約</Link>
        <Link href="/privacy" className="hover:text-ink">プライバシー</Link>
        <span className="ml-auto">© 2026 MANGAL</span>
      </div>
    </footer>
  );
}
