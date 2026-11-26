import Link from "next/link";
import FeaturedDaily from "@/components/FeaturedDaily";
import AnniversaryDaily from "@/components/AnniversaryDaily";
import { AizoubanCorner, TokusoubanCorner } from "@/components/EditionCorners";
import DestinyPickMock from "@/components/DestinyPickMock";
import MonthReleasesClient from "@/components/MonthReleasesClient";
import FilterRail from "@/components/FilterRail";
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
import { DOT_HEADING } from "@/lib/fonts";
import { loadAizoubanStock, loadColorEditions, loadTokusoubanStock } from "@/lib/cornerData";
import { jstDayIndex } from "@/lib/sansedai";
import SaleBanner from "@/components/SaleBanner";

export const metadata = { robots: { index: false, follow: false } };  // 実験頁=非索引

/** 案12(2026-08-11): D3「ダークブルータル」 — 案11の中身・データ・コーナー構成は完全同一、
 *  ガワだけ黒×アシッドライム×角丸ゼロへ(.theme-d3 トークン差し替え)。
 *  追加はD3外殻のみ: マーキー帯 / ランダムコピーのヒーロー+検索 / カテゴリ8枚(SVG線画アイコン)。
 *  ヘッダーは現行DesignNavと同一6リンクのSVG版(2026-09-02: 一覧→新作に差し替え・検索を先頭へ。DesignNavと同順)。
 *  ★2026-09-14: その「新作」はラベルを **「新刊」** に改称(行き先 /shinkan は不変)。正本= components/GlobalNav.tsx。
 *  フッターは共通SiteFooter(layout側)のまま。 */

// ★NavIcon / D3Nav は components/GlobalNav.tsx へ移設(2026-09-07 ナビを layout に一本化)。
//   ホームだけ太線+paper地という差はパス判定で GlobalNav 側が出し分ける。

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
  // ★「登録は N 作品、漫画本は合計 M 冊」は外した(2026-11-04): ヒーロー直下と同じ数字が
  //   ホームに3回出ていた(ヒーロー・カテゴリ下の帯・この欄)。数字はヒーローの1回に寄せる。
  const trivia = [
    longest && `収録最長は『${longest.title}』の 全${volCount(longest)}巻。1日1冊でも読破に${Math.ceil(volCount(longest) / 30)}ヶ月。`,
    oldest && `最も古い収録作は『${oldest.title}』(${oldest.year_started}年〜)。`,
  ].filter(Boolean) as string[];

  const Tile = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
    <div className={`rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] shadow-sm ${className}`}>{children}</div>
  );

  // ★2026-09-24: JS描画のコーナーにSSR初期値を渡す(配信HTMLに枠と一覧頁へのリンクを出し、
  //   読み込み後に下がずれるのを防ぐ)。選び方=slugハッシュで決定的(ビルドごとに安定)。
  //   マウント後は各コーナーが従来どおりランダム抽選に差し替える。
  const aizStock = loadAizoubanStock();
  const tksStock = loadTokusoubanStock();
  const colorAll = Object.entries(loadColorEditions());
  const aizInitial = { picks: seeded(aizStock, (p) => `${p.s}-${p.e}-${p.v}`, 6, 11), total: aizStock.length };
  const tksInitial = { picks: seeded(tksStock, (p) => `${p.s}-${p.v}-${p.l}`, 6, 13), total: tksStock.length };
  // 14 = ColorCorner の SHOW と同じ枚数(★"use client" の export は server から値として import できない=定数も不可)
  const colorInitial = seeded(colorAll.filter(([, e]) => e.c), ([slug]) => slug, 14, 17);

  const banner = "日本の漫画 " + manga.length.toLocaleString() + "作品を収録 ✺ 全巻一覧・発売日・出版社がすぐわかる ✺ 今週も新刊入荷中 ✺ ";

  return (
    <div className="theme-d3 min-h-screen bg-[var(--color-bg)] pb-12">
      {/* E型ステータスバーは撤去(2026-08-17 ユーザ裁定=案D: ヘッダーは旧共通ヘッダーに統一。
          日付は下のマーキー帯先頭に出す=StatusDate)。 */}
      {/* SEO用の固定見出し(視覚上は小さく。巨大タイポはHeroD3内の装飾p=ランダム可) */}
      <h1 className="sr-only">MANGAL — 漫画を探す・全巻一覧がわかる日本の漫画データベース</h1>
      <div className="overflow-hidden whitespace-nowrap border-b-[3px] border-[#0d0d0d] bg-[var(--color-accent)] py-1 text-[11px] font-black tracking-[0.14em] text-[#0d0d0d]">
        {/* ★日付はマーキー先頭(案D)。ループ2周とも先頭に付けて継ぎ目を揃える */}
        <span className="d3-marquee"><StatusDate />{banner}<StatusDate />{banner}</span>
      </div>
      {/* ★2026-09-07: 他頁(PageShell)と同じ器 max-w-6xl に統一。ホームだけ 960px だと
          レールの左端位置が頁を移るたびに横に飛んでいた。本文は残り幅を埋める。 */}
      <div className="mx-auto flex w-full max-w-6xl gap-6 lg:px-4">
      <FilterRail masters={{ genres: data.genres, demographics: data.demographics }} />
      <div className="w-full min-w-0 flex-1">

      <HeroD3 total={manga.length} books={totalBooks} />

      {/* ★カテゴリ8枚(アニメ化/完結/連載中/児童/少年/青年/少女/女性)は撤去(2026-11-26 ユーザ相談→テストで試す)。
          行き先の /browse に同じ並び(CategoryHub)があり、PCは左のFilterRailでも絞れる。スマホで画面の約半分を使っていた。
          戻す時は git log で本コミットを引く。 */}

      {/* ★カテゴリ直下の数字の帯(作品|漫画本|連載中|完結|タップで絞り込み)は撤去(2026-11-04)。
          作品数・冊数はヒーロー、連載中・完結の数と行き先は上のタイルと同じで、スマホでは帯の右端
          (「タップで絞り込み」)が切れていた。タイルの数は nOn/nDone のまま(2026-09-05 の数の食い違い是正は不変)。 */}

      {/* ここから下は案11と完全同一(コーナー順・データ・リンク不変) */}
      {/* ★Amazon セールバナー(2026-11-24・期限で自動消滅・SaleBanner の SALE を差し替えて使い回す) */}
      <SaleBanner className="mt-4" />
      <AnimeSeasonCorner />
      <DailyFeatureCorner />

      <section className="mt-4 px-4">
        <Tile className="p-3.5">
          <div className="flex items-baseline justify-between">
            <h2 className={`${DOT_HEADING} text-[14px] font-bold`}>📦 今月の新刊</h2>
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

      {/* ★2026-09-14 ユーザ指示: カレンダー(CalendarView)と タイムマシン(TimeMachine)を
          PC/スマホとも完全撤去。ホームは1つのレスポンシブ実装なので両方から消える。
          両コンポーネントと未使用の ReleaseCalendarMock は削除済み(= サイト上に
          `/calendar/*.json` を読む所は無くなった)。
          ★ただし `data/calendar` の生成(_build-calendar.py)は**残す**: /shinkan(新刊)の
            データ生成 _gen-shinkan-data.py の入力になっている。配信はしない内部中間物。 */}

      <FeaturedDaily slot={0} />
      <KotobaDaily pool={kotobaPool} />
      <AnniversaryDaily />
      <AizoubanCorner initial={aizInitial} />

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
          <h2 className={`${DOT_HEADING} border-l-4 border-[var(--color-accent)] pl-2.5 text-[14px] font-extrabold`}>
            特集: 週末で読み切る、全5巻以内の完結作
            <span className="ml-1.5 text-[10px] font-semibold text-ink/45">週替わり</span>
          </h2>
          <WeekendFeature
            initialWeek={Math.floor(jstDayIndex() / 7)}
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
      {/* 8.1【中】特装版・限定版コーナー(2026-09-06 新設。愛蔵版と同型=毎回ランダム4点+全部見る) */}
      <TokusoubanCorner initial={tksInitial} />
      <ColorCorner initial={colorInitial} initialTotal={colorAll.length} />
      <ZenshuuCorner />
      <section className="mt-5 px-4">
        <div className="grid grid-cols-2 gap-2.5">
          {([
            ["📋 一覧表で探す", "全作品をソート・絞り込み", "/list"],
            ["🏷️ ジャンルから", "ジャンル別の作品一覧へ", "/genre"],  // ★2026-09-24 旧=/browse(ジャンル面への入口が無かった)
            ["あ 50音さくいん", "著者名から作品へ", "/authors"],
            // ★マイ本棚(/shelf)。 2026-10-31 本番にも出す(旧 = テスト環境だけ繋ぎ、本番は「準備中」で押せなかった)
            ["📚 本棚", "所持巻を記録・続刊を通知", "/shelf"],
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
