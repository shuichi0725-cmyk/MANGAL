import view from "@/data/anime-seasons-view.json";
import AnimeSeasonCornerClient from "./AnimeSeasonCornerClient";
import { currentSeasonKey, seasonLabel, type AnimeSeasonsView } from "@/lib/animeSeason";

const V = view as unknown as AnimeSeasonsView;

/** 📺 今季アニメの原作コーナー(トップ用・server側)。季刊入替=view JSON再生成のみ。
 *  表示部はclient(AnimeSeasonCornerClient)=★再読込ごとにシャッフル表示(2026-07-12)。
 *  季全体をpropsで渡す(50件×小fields=数KB。シャッフル母集団になる)。 */
export default function AnimeSeasonCorner() {
  const key = currentSeasonKey(V.order);
  const entries = V.seasons[key] ?? [];
  if (entries.length === 0) return null;

  return (
    <AnimeSeasonCornerClient
      seasonKey={key}
      label={seasonLabel(key)}
      total={entries.length}
      entries={entries}
    />
  );
}
