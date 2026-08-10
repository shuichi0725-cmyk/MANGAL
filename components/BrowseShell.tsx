import Card from "@/components/ui/Card";
import type { IndexSummary } from "@/lib/schema";

/**
 * /browse の★サーバ描画シェル★(2026-08-01)。
 *
 * ★なぜ要るか
 *   /browse は HomeClient / CategoryHub が `useSearchParams()` を使うため、静的書き出しでは
 *   Suspense 必須。そのフォールバックが `null` だったので、**ビルド時に本文が丸ごと消えていた**。
 *   実測: /browse の可視テキストは 357字(= ヘッダとフッタだけ)。ホーム5,014字・
 *   ジャンル面16,814字と比べて明らかに異常で、JS が動くまで白紙だった。
 *   /browse はヘッダ・フッタ・メニュー・ショートカットの4箇所から張られた**検索の入口**なので、
 *   ここが白紙なのは体感でもSEOでも損が大きい。
 *
 * ★方針
 *   データに依存しない部分(見出し・検索窓・カテゴリ)は**HTMLに焼く**。件数はビルド時集計の
 *   IndexSummary を使うので、頁を開いた瞬間から正しい数字が出る。
 *   hydrate 後は HomeClient の本物(絞り込み・並べ替え・逐次検索つき)に差し替わる。
 *   見た目が飛ばないよう、クラス名は HomeClient / CategoryHub と揃えてある。
 *
 * ★JS が来る前でも使える: 検索窓は素の GET フォームで /browse?q=… に飛ぶ。
 *   カテゴリも素の <a href="/browse?…">。着地後に HomeClient が URL を読んで復元する。
 */

type Cat = { href: string; label: string; count: number; icon: string };

export default function BrowseShell({ summary }: { summary: IndexSummary }) {
  const s = summary;
  // ★8枚構成(2026-08-10 ユーザ裁定・案A): ソート系カード(人気順/新旧/巻数/五十音)は
  //   「カテゴリではない」ため撤去=フィルターの並び順に一本化。受賞もフィルターへ委譲。
  //   1行目=アニメ化/完結/連載中/児童(右上)、2行目=分野4はそのまま。
  const cats: Cat[] = [
    { href: "/browse?anime=true", label: "アニメ化作品", count: s.anime, icon: "🎞️" },
    { href: "/browse?status=completed", label: "完結作品", count: s.completed, icon: "✅" },
    { href: "/browse?status=ongoing", label: "連載中", count: s.ongoing, icon: "📖" },
    { href: "/browse?demographic=kodomo", label: "児童", count: s.kodomo, icon: "🧒" },
    { href: "/browse?demographic=shounen", label: "少年", count: s.shounen, icon: "👦" },
    { href: "/browse?demographic=seinen", label: "青年", count: s.seinen, icon: "👨" },
    { href: "/browse?demographic=shoujo", label: "少女", count: s.shoujo, icon: "👧" },
    { href: "/browse?demographic=josei", label: "女性", count: s.josei, icon: "👩" },
  ].filter((c) => c.count > 0);

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <section className="mb-6 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">日本の漫画から探す</h1>
          <p className="text-sm text-ink/60 mt-1">
            年・著者・出版社・分野・ジャンルで絞り込めます。 全{" "}
            <span className="font-semibold text-ink/80 tabular-nums">{s.total.toLocaleString()}</span> 件
            <span className="text-ink/45">（読み込み中…）</span>。
          </p>
        </div>
      </section>

      {/* 素の GET フォーム = JS が来る前でも検索に飛べる */}
      <form action="/browse" method="get" className="relative mb-6 flex items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <span
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink/35"
            aria-hidden="true"
          >
            🔍
          </span>
          <input
            type="search"
            name="q"
            placeholder="タイトル・よみがな・ローマ字で検索"
            aria-label="作品を検索"
            className="w-full rounded-card border border-[var(--color-line)] bg-[var(--color-surface)] shadow-[var(--shadow-soft)] pl-9 pr-10 py-2.5 text-sm transition focus:outline-none focus:border-[var(--color-accent)] focus:shadow-[var(--shadow-lift)]"
          />
        </div>
        <button
          type="submit"
          className="shrink-0 rounded-card bg-[var(--color-accent)] px-4 py-2.5 text-sm font-semibold text-white"
        >
          検索
        </button>
      </form>

      {cats.length > 0 && (
        <section className="mb-7">
          <h2 className="text-[11px] font-semibold tracking-[0.18em] uppercase text-ink/50 mb-3">
            カテゴリで探す
          </h2>
          <ul className="grid grid-cols-4 sm:grid-cols-5 lg:grid-cols-6 gap-2">
            {cats.map((c) => (
              <li key={c.label}>
                <Card href={c.href} className="h-full px-1 py-2.5 text-center">
                  <span className="flex flex-col items-center justify-center gap-1">
                    <span className="text-base leading-none" aria-hidden="true">
                      {c.icon}
                    </span>
                    <span className="text-[11px] font-semibold leading-tight">{c.label}</span>
                    <span className="text-[10px] font-medium leading-none tabular-nums text-ink/40">
                      {c.count.toLocaleString()}
                    </span>
                  </span>
                </Card>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
