import React from "react";
import { MangaGrid } from "mangal";

const publishers = [
  { key: "shueisha", name: "集英社" },
  { key: "hakusensha", name: "白泉社" },
  { key: "kodansha", name: "講談社" },
];

const base = {
  title_kana: "", cover: null, subtitle: null, original_authors: [],
  genres: [], demographic: "shonen", publishers: [],
  total_volumes: 0, max_edition_volumes: 0,
};

const items = [
  {
    ...base, slug: "berserk", title: "ベルセルク", year_started: 1989, year_ended: null,
    status: "ongoing", authors: [{ name: "三浦建太郎" }], publisher: "hakusensha",
    catch: "黒い剣士ガッツが、鷹の団との日々の果てに背負った烙印とともに、化物を狩る旅を続ける。",
    total_volumes: 42, max_edition_volumes: 42,
  },
  {
    ...base, slug: "hunter-x-hunter", title: "ハンター×ハンター", year_started: 1998,
    year_ended: null, status: "ongoing", authors: [{ name: "冨樫義博" }], publisher: "shueisha",
    catch: "父を探して旅に出た少年ゴンが、念能力を身につけながら仲間と出会い、世界の裏側へ踏み込んでいく。",
    total_volumes: 37, max_edition_volumes: 37,
  },
  {
    ...base, slug: "versailles-no-bara", title: "ベルサイユのばら", year_started: 1972,
    year_ended: 1973, status: "completed", authors: [{ name: "池田理代子" }], publisher: "shueisha",
    total_volumes: 10, max_edition_volumes: 10,
  },
  {
    ...base, slug: "kyojin-no-hoshi", title: "巨人の星", year_started: 1966, year_ended: 1971,
    status: "completed", authors: [{ name: "川崎のぼる" }],
    original_authors: [{ name: "梶原一騎" }], publisher: "kodansha",
    total_volumes: 19, max_edition_volumes: 19,
  },
];

/** The list view as visitors see it. */
export function ResultList() {
  return (
    <div className="max-w-xl">
      <MangaGrid items={items} publishers={publishers} genres={[]} demographics={[]} />
    </div>
  );
}

/** A single hit — the grid keeps the same rhythm. */
export function SingleResult() {
  return (
    <div className="max-w-xl">
      <MangaGrid items={items.slice(0, 1)} publishers={publishers} genres={[]} demographics={[]} />
    </div>
  );
}

/** Nothing matched — the built-in empty state, not a blank area. */
export function EmptyState() {
  return (
    <div className="max-w-xl">
      <MangaGrid items={[]} publishers={publishers} genres={[]} demographics={[]} />
    </div>
  );
}
