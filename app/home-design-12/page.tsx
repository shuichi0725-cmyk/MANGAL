import Link from "next/link";
import FeaturedDaily from "@/components/FeaturedDaily";
import AnniversaryDaily from "@/components/AnniversaryDaily";
import DeluxeWeekly from "@/components/DeluxeWeekly";
import TimeMachine from "@/components/TimeMachine";
import DestinyPickMock from "@/components/DestinyPickMock";
import MonthReleasesClient from "@/components/MonthReleasesClient";
import CalendarView from "@/components/CalendarView";
import HomeSidebar from "@/components/HomeSidebar";
import { bundle, seeded, volCount, thisMonthReleases, releaseDayLabel } from "@/lib/homeDesign";
import WeekendFeature from "@/components/WeekendFeature";
import { coverUrl } from "@/lib/schema";
import { loadAiReviews } from "@/lib/loadData";
import AiLeagueTeaser from "@/components/AiLeagueTeaser";
import AnimeSeasonCorner from "@/components/AnimeSeasonCorner";
import ZenshuuCorner from "@/components/ZenshuuCorner";
import ColorCorner from "@/components/ColorCorner";
import DailyFeatureCorner from "@/components/DailyFeatureCorner";
import { KotobaDaily, TriviaDaily, GenreRouletteDaily } from "@/components/DailyBits";
import HeroD3 from "./HeroD3";
import StatusDate from "./StatusDate";

export const metadata = { robots: { index: false, follow: false } };  // 実験頁=非索引

/** 案12(2026-08-11): D3「ダークブルータル」 — 案11の中身・データ・コーナー構成は完全同一、
 *  ガワだけ黒×アシッドライム×角丸ゼロへ(.theme-d3 トークン差し替え)。
 *  追加はD3外殻のみ: マーキー帯 / ランダムコピーのヒーロー+検索 / カテゴリ8枚(SVG線画アイコン)。
 *  ヘッダーは現行DesignNavと同一6リンクのSVG版(2026-09-02: 一覧→新作に差し替え・検索を先頭へ。DesignNavと同順)。
 *  フッターは共通SiteFooter(layout側)のまま。 */

const NavIcon = ({ d, circle }: { d: string; circle?: [number, number, number] }) => (
  <svg viewBox="0 0 24 24" className="h-[19px] w-[19px]" style={{ stroke: "var(--color-accent)", fill: "none", strokeWidth: 1.9 }}>
    {circle && <circle cx={circle[0]} cy={circle[1]} r={circle[2]} />}
    <path d={d} />
  </svg>
);

function D3Nav() {
  const cell = "spring-press flex flex-col items-center gap-0.5 active:scale-90";
  const right: Array<[React.ReactNode, string, string]> = [
    [<NavIcon key="s" d="M15 15l6 6" circle={[10.5, 10.5, 6]} />, "検索", "/browse"],
    // 新作=今月の新刊一覧。≡メニューの box アイコンと同じ絵柄
    [<NavIcon key="n" d="M21 8l-9-5-9 5v8l9 5 9-5zM3 8l9 5 9-5M12 13v8" />, "新作", "/shinkan"],
    [<NavIcon key="p" d="M4 20l2-6L16 4l4 4L10 18l-6 2zM14 6l4 4" />, "AI書評", "/column-ai-league"],
    [<NavIcon key="c" d="M12 7v5l3.5 2" circle={[12, 12, 8.5]} />, "過去ログ", "/sansedai-archive"],
    [<NavIcon key="g" d="M12 5c-2-1.6-5-1.6-8-.6V19c3-1 6-1 8 .6 2-1.6 5-1.6 8-.6V4.4c-3-1-6-1-8 .6zM12 5v14" />, "使い方", "/about"],
  ];
  return (
    <div className="flex items-center border-b-[3px] border-[var(--color-accent)] bg-[var(--color-paper)] px-3 py-1.5">
      {/* ★ロゴは共通ヘッダー(layout)に一本化(2026-08-11 ユーザ指摘「ヘッダーが二つ」)。DesignNavと同配置=ホーム左固定 */}
      <Link href="/" aria-label="ホーム" className={cell}>
        <NavIcon d="M3 11L12 3l9 8M6 10v11h12V10" />
        <span className="text-[9px] text-ink/55">ホーム</span>
      </Link>
      <div className="ml-auto flex items-center gap-3.5">
        {right.map(([icon, label, href]) => (
          <Link key={label} href={href} aria-label={label} className={cell}>
            {icon}
            <span className="text-[9px] text-ink/55">{label}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}

const CatIcon = ({ children }: { children: React.ReactNode }) => (
  <svg viewBox="0 0 24 24" className="mx-auto h-5 w-5" style={{ stroke: "var(--color-ink)", fill: "none", strokeWidth: 1.8 }}>
    {children}
  </svg>
);

export default function Design12() {
  const { data, manga, byNew } = bundle();
  const genreList = data.genres.map((g: { key: string; name: string }) => ({ key: g.key, name: g.name }));
  const aiSections = loadAiReviews().map((x) => ({ setsu: x.setsu, title: x.title, models: x.reviews.map((r) => r.model) }));
  const withSyn = manga.filter((m) => m.synopsis && m.synopsis.length > 40);
  const kotobaPool = seeded(withSyn, (m) => m.slug, 31, 7).map((m) => ({
    slug: m.slug,
    title: m.title,
    line: (m.synopsis as string).split("。")[0],
  }));
  const longest = [...manga].sort((a, b) => volCount(b) - volCount(a))[0];
  const totalBooks = manga.reduce((s, m) => s + m.editions.reduce((x, e) => x + e.volumes.length, 0), 0);
  const oldest = [...manga].filter((m) => m.year_started).sort((a, b) => a.year_started - b.year_started)[0];
  const trivia = [
    longest && `収録最長は『${longest.title}』の 全${volCount(longest)}巻。1日1冊でも読破に${Math.ceil(volCount(longest) / 30)}ヶ月。`,
    `登録は ${manga.length.toLocaleString()} 作品、漫画本は合計 ${totalBooks.toLocaleString()} 冊。`,
    oldest && `最も古い収録作は『${oldest.title}』(${oldest.year_started}年〜)。`,
  ].filter(Boolean) as string[];

  // カテゴリ8枚(browseと同構成・件数はビルド時集計)
  const nAnime = manga.filter((m) => m.anime_adapted).length;
  const nDone = manga.filter((m) => m.status === "completed").length;
  const nOn = manga.filter((m) => m.status === "ongoing").length;
  const demo = (k: string) => manga.filter((m) => m.demographic === k).length;
  const cats: Array<[React.ReactNode, string, number, string]> = [
    [<CatIcon key="a"><rect x="3" y="5" width="18" height="14" /><path d="M7 5v14M17 5v14M3 9h4M3 15h4M17 9h4M17 15h4" /></CatIcon>, "アニメ化", nAnime, "/browse?anime=true"],
    [<CatIcon key="b"><rect x="4" y="4" width="16" height="16" /><path d="M8 12l3 3 5-6" /></CatIcon>, "完結", nDone, "/browse?status=completed"],
    [<CatIcon key="c"><path d="M12 6c-2-1.6-5-1.6-8-.6V19c3-1 6-1 8 .6 2-1.6 5-1.6 8-.6V5.4c-3-1-6-1-8 .6zM12 6v14" /></CatIcon>, "連載中", nOn, "/browse?status=ongoing"],
    [<CatIcon key="d"><circle cx="12" cy="9" r="3.4" /><path d="M6.5 20c.6-4 3-6 5.5-6s4.9 2 5.5 6M9 5.5C10 4.5 11 4 12 4s2 .5 3 1.5" /></CatIcon>, "児童", demo("kodomo"), "/browse?demographic=kodomo"],
    [<CatIcon key="e"><circle cx="12" cy="8" r="3.6" /><path d="M5.5 20c.8-4.5 3.4-7 6.5-7s5.7 2.5 6.5 7" /></CatIcon>, "少年", demo("shounen"), "/browse?demographic=shounen"],
    [<CatIcon key="f"><circle cx="12" cy="8" r="3.6" /><path d="M5.5 20c.8-4.5 3.4-7 6.5-7s5.7 2.5 6.5 7M9 20v-3M15 20v-3" /></CatIcon>, "青年", demo("seinen"), "/browse?demographic=seinen"],
    [<CatIcon key="g"><circle cx="12" cy="8" r="3.6" /><path d="M5.5 20c.8-4.5 3.4-7 6.5-7s5.7 2.5 6.5 7M8 6.5C7.4 9 6.8 10.5 6 12M16 6.5c.6 2.5 1.2 4 2 5.5" /></CatIcon>, "少女", demo("shoujo"), "/browse?demographic=shoujo"],
    [<CatIcon key="h"><circle cx="12" cy="8" r="3.6" /><path d="M5.5 20c.8-4.5 3.4-7 6.5-7s5.7 2.5 6.5 7M8.5 6C7.5 9.5 7 12 6.5 14M15.5 6c1 3.5 1.5 6 2 8" /></CatIcon>, "女性", demo("josei"), "/browse?demographic=josei"],
  ];

  const Tile = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
    <div className={`rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] shadow-sm ${className}`}>{children}</div>
  );

  const banner = "日本の漫画 " + manga.length.toLocaleString() + "作品を収録 ✺ 全巻一覧・発売日・出版社がすぐわかる ✺ 今週も新刊入荷中 ✺ ";

  return (
    <div className="theme-d3 min-h-screen bg-[var(--color-bg)] pb-12">
      {/* E型ステータスバーは撤去(2026-08-17 ユーザ裁定=案D: ヘッダーは旧共通ヘッダーに統一。
          日付は下のマーキー帯先頭に出す=StatusDate)。 */}
      <D3Nav />
      {/* SEO用の固定見出し(視覚上は小さく。巨大タイポはHeroD3内の装飾p=ランダム可) */}
      <h1 className="sr-only">MANGAL — 漫画を探す・全巻一覧がわかる日本の漫画データベース</h1>
      <div className="overflow-hidden whitespace-nowrap border-b-[3px] border-[#0d0d0d] bg-[var(--color-accent)] py-1 text-[11px] font-black tracking-[0.14em] text-[#0d0d0d]">
        {/* ★日付はマーキー先頭(案D)。ループ2周とも先頭に付けて継ぎ目を揃える */}
        <span className="d3-marquee"><StatusDate />{banner}<StatusDate />{banner}</span>
      </div>
      <div className="mx-auto flex w-full max-w-[960px] justify-center gap-6 lg:px-4">
      <HomeSidebar genres={genreList} />
      <div className="w-full max-w-[640px] min-w-0">

      <HeroD3 total={manga.length} books={totalBooks} />

      {/* カテゴリ8枚(SVG線画・/browseのカテゴリカードと同じ行き先) */}
      <section className="mt-5 px-4">
        <div className="flex items-baseline gap-2.5">
          <h2 className="dot-heading text-[18px] font-black">カテゴリ</h2>
          <span className="text-[9px] font-extrabold tracking-[0.26em] text-ink/45">BROWSE BY</span>
        </div>
        <div className="mt-2.5 grid grid-cols-4 border-[3px] border-[var(--color-ink)] bg-[var(--color-surface)]">
          {cats.map(([icon, label, n, href], i) => (
            <Link
              key={label}
              href={href}
              className={`spring-press block px-1 py-3 text-center ${i % 4 !== 3 ? "border-r-2 border-[#333]" : ""} ${i < 4 ? "border-b-2 border-[#333]" : ""}`}
            >
              {icon}
              <div className="mt-1 text-[11px] font-black">{label}</div>
              <div className="mt-0.5 text-[9.5px] font-bold text-[var(--color-accent)] tabular-nums">{n.toLocaleString()}</div>
            </Link>
          ))}
        </div>
      </section>

      {/* ここから下は案11と完全同一(コーナー順・データ・リンク不変) */}
      {(() => {
        const books = totalBooks;
        // ★上のカテゴリタイルと同じ数を使う(2026-09-05 ユーザ報告「連載中の数に相違がある」)。
        //   旧: ここだけ status !== "completed" で数えており、休載(hiatus=7作。ガラスの仮面/
        //   HUNTER×HUNTER/NANA 等)を連載中に含めていた。結果、タイル 7,431 に対しこの帯が 7,438、
        //   しかも両方のリンク先 /browse?status=ongoing は厳密一致で 7,431 を出す = 数がリンク先と
        //   食い違っていた。定義を2か所に持たず nOn/nDone を共有する。
        const ongoing = nOn;
        const done = nDone;
        const S = ({ href, label, n }: { href: string; label: string; n: number }) => (
          <Link href={href} className="spring-press whitespace-nowrap">
            <span className="text-ink/50">{label}</span>{" "}
            <b className="tabular-nums text-ink/85">{n.toLocaleString()}</b>
          </Link>
        );
        return (
          <div className="flex items-center gap-x-3 overflow-x-auto px-4 py-2.5 text-[11px] leading-none">
            <S href="/browse" label="作品" n={manga.length} />
            <span className="text-ink/25">|</span>
            <S href="/browse" label="漫画本" n={books} />
            <span className="text-ink/25">|</span>
            <S href="/browse?status=ongoing" label="連載中" n={ongoing} />
            <span className="text-ink/25">|</span>
            <S href="/browse?status=completed" label="完結" n={done} />
            <span className="ml-auto shrink-0 text-[10px] text-ink/40">タップで絞り込み</span>
          </div>
        );
      })()}

      <AnimeSeasonCorner />
      <DailyFeatureCorner />

      <section className="mt-4 px-4">
        <Tile className="p-3.5">
          <div className="flex items-baseline justify-between">
            <h2 className="dot-heading text-[14px] font-bold">📦 今月の新刊</h2>
            <Link href="/shinkan?go=today" className="spring-press text-[11px] font-bold text-[var(--color-accent)]">全部見る →</Link>
          </div>
          <MonthReleasesClient
            pool={thisMonthReleases(manga, byNew, 60).map((r) => ({
              slug: r.m.slug,
              title: r.m.title,
              authors: (r.m.authors ?? []).map((a) => a.name).join("・"),
              number: r.number,
              sub: `${r.number ? `${r.number}巻` : "新刊"}${releaseDayLabel(r.date) ? `・${releaseDayLabel(r.date)}` : ""}`,
              cover: r.cover,
            }))}
          />
        </Tile>
      </section>

      <section className="mt-4 px-4">
        <Tile className="p-3.5">
          <div className="mb-1 flex items-baseline justify-between">
            <h2 className="dot-heading text-[14px] font-extrabold">📅 カレンダー</h2>
            <span className="text-[10px] text-ink/45">今月〜3ヶ月先+未定</span>
          </div>
          <CalendarView />
        </Tile>
      </section>

      <FeaturedDaily slot={0} />
      <KotobaDaily pool={kotobaPool} />
      <AnniversaryDaily />
      <TimeMachine />
      <DeluxeWeekly />

      {trivia.length > 0 && (
        <section className="mt-4 px-4">
          <div className="flex items-center gap-3 rounded-xl border border-dashed border-[var(--color-line)] bg-[var(--color-surface-2)]/60 px-4 py-3">
            <span className="text-2xl">🔢</span>
            <p className="text-[12px] leading-relaxed text-ink/75">
              <b>きょうの数字:</b> <TriviaDaily items={trivia} />
            </p>
          </div>
        </section>
      )}

      <FeaturedDaily slot={1} />

      <section className="mt-4 px-4">
        <GenreRouletteDaily genres={genreList} />
      </section>

      <FeaturedDaily slot={2} />

      <section className="mt-4 px-4">
        <Tile className="p-3.5">
          <h2 className="dot-heading border-l-4 border-[var(--color-accent)] pl-2.5 text-[14px] font-extrabold">
            特集: 週末で読み切る、全5巻以内の完結作
            <span className="ml-1.5 text-[10px] font-semibold text-ink/45">週替わり</span>
          </h2>
          <WeekendFeature
            pool={seeded(
              manga.filter((m) => m.status === "completed" && volCount(m) >= 3 && volCount(m) <= 5 && coverUrl(m)),
              (m) => m.slug,
              120,
              42,
            ).map((m) => ({
              slug: m.slug,
              title: m.title,
              authors: (m.authors ?? []).map((a) => a.name).join("・"),
              cover: coverUrl(m)!,
            }))}
          />
        </Tile>
      </section>

      <section className="mt-4 px-4">
        <Link href="/column-ai-league" className="spring-press block">
          <Tile className="overflow-hidden">
            <AiLeagueTeaser sections={aiSections} />
          </Tile>
        </Link>
      </section>

      <section className="mt-4 px-4">
        <Tile>
          <DestinyPickMock
            items={seeded(manga, (m) => m.slug, 60, 3).map((m) => ({
              slug: m.slug,
              title: m.title,
              authors: (m.authors ?? []).map((a) => a.name).join("・"),
              vols: volCount(m),
              cover: coverUrl(m),
            }))}
            initialIndex={0}
            total={manga.length}
          />
        </Tile>
      </section>

      {/* カラー版コーナー(2026-08-12 ユーザ指定=全集コーナーの直上) */}
      <ColorCorner />
      <ZenshuuCorner />
      <section className="mt-5 px-4">
        <div className="grid grid-cols-2 gap-2.5">
          {([
            ["📋 一覧表で探す", "全作品をソート・絞り込み", "/list"],
            ["🏷️ ジャンルから", "グリッド検索へ", "/browse"],
            ["あ 50音さくいん", "著者名から作品へ", "/authors"],
            ["📚 あなたの本棚", "所持巻を記録(準備中)", null],
          ] as const).map(([t, d, href]) =>
            href ? (
              <Link key={t} href={href} className="spring-press block">
                <Tile className="p-3"><p className="text-[13px] font-bold text-ink/85">{t}</p><p className="mt-0.5 text-[10.5px] text-ink/50">{d}</p></Tile>
              </Link>
            ) : (
              <Tile key={t} className="p-3 opacity-70"><p className="text-[13px] font-bold text-ink/85">{t}</p><p className="mt-0.5 text-[10.5px] text-ink/50">{d}</p></Tile>
            ),
          )}
        </div>
      </section>
      </div>
      </div>
    </div>
  );
}
