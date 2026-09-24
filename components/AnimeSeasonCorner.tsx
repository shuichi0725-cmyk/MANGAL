import view from "@/data/anime-seasons-view.json";
import AnimeSeasonCornerClient, { type SeasonBlock } from "./AnimeSeasonCornerClient";
import { animeNavSeasons, seasonLabel, type AnimeSeasonsView } from "@/lib/animeSeason";

const V = view as unknown as AnimeSeasonsView;

/** 📺 今季アニメの原作コーナー(トップ用・server側)。季刊入替=view JSON再生成のみ。
 *  表示部はclient(AnimeSeasonCornerClient)=★再読込ごとにシャッフル表示(2026-07-12)。
 *  季全体をpropsで渡す(50件×小fields=数KB。シャッフル母集団になる)。
 *  ★2026-09-24: 季はビルド時に決まるため、ビルドが季の境目をまたぐと次のビルドまで前の季を
 *  「今季」として出していた(ナビは 09-08 に同じ穴を塞いだが、このコーナーは未対応だった)。
 *  ナビと同じ animeNavSeasons で「今季+次の季」を渡し、JSTの今日が次の季に達していれば
 *  クライアントで次の季へ切り替える。次の季はviewに実在する季だけ(=存在しない頁へ飛ばさない)。 */
export default function AnimeSeasonCorner() {
  const { now, next } = animeNavSeasons(V.order);
  const block = (key: string): SeasonBlock | null => {
    const entries = V.seasons[key] ?? [];
    return entries.length ? { key, label: seasonLabel(key), entries } : null;
  };
  const current = block(now);
  if (!current) return null;

  return <AnimeSeasonCornerClient current={current} upcoming={next ? block(next) : null} />;
}
