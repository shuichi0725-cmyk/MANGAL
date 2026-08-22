import React from "react";
import { MangaCard } from "mangal";

const publishers = [
  { key: "shueisha", name: "集英社" },
  { key: "kodansha", name: "講談社" },
  { key: "shogakukan", name: "小学館" },
];

const base = {
  title_kana: "",
  cover: null,
  subtitle: null,
  original_authors: [],
  genres: [],
  demographic: "shonen",
  publishers: [],
  total_volumes: 0,
  max_edition_volumes: 0,
};

/** The everyday row: ongoing series with a catch copy. */
export function Ongoing() {
  const manga = {
    ...base,
    slug: "hunter-x-hunter",
    title: "ハンター×ハンター",
    year_started: 1998,
    year_ended: null,
    status: "ongoing",
    catch: "父を探して旅に出た少年ゴンが、念能力を身につけながら仲間と出会い、世界の裏側へ踏み込んでいく。",
    authors: [{ name: "冨樫義博" }],
    publisher: "shueisha",
    total_volumes: 37,
    max_edition_volumes: 37,
  };
  return (
    <div className="max-w-xl">
      <MangaCard manga={manga} publishers={publishers} genres={[]} demographics={[]} />
    </div>
  );
}

/** Completed, no catch copy — the publisher name takes the last line instead. */
export function CompletedNoCatch() {
  const manga = {
    ...base,
    slug: "yoroshiku-mechadoc",
    title: "よろしくメカドック",
    year_started: 1982,
    year_ended: 1985,
    status: "completed",
    authors: [{ name: "次原隆二" }],
    publisher: "shueisha",
    total_volumes: 12,
    max_edition_volumes: 12,
  };
  return (
    <div className="max-w-xl">
      <MangaCard manga={manga} publishers={publishers} genres={[]} demographics={[]} />
    </div>
  );
}

/** Original author credited separately, plus a subtitle line. */
export function WithOriginalAuthor() {
  const manga = {
    ...base,
    slug: "kyojin-no-hoshi",
    title: "巨人の星",
    subtitle: "少年マガジン連載版",
    year_started: 1966,
    year_ended: 1971,
    status: "completed",
    catch: "父の果たせなかった夢を背負い、星飛雄馬が大リーグボールを武器に巨人軍のマウンドを目指す。",
    authors: [{ name: "川崎のぼる" }],
    original_authors: [{ name: "梶原一騎" }],
    publisher: "kodansha",
    total_volumes: 19,
    max_edition_volumes: 19,
  };
  return (
    <div className="max-w-xl">
      <MangaCard manga={manga} publishers={publishers} genres={[]} demographics={[]} />
    </div>
  );
}

/** A long title that has to marquee, and a four-line catch at full clamp. */
export function LongTitle() {
  const manga = {
    ...base,
    slug: "hazure-skill-kage-ga-usui",
    title: "ハズレスキル《影が薄い》を持つギルド職員が、実は伝説の暗殺者",
    year_started: 2021,
    year_ended: null,
    status: "ongoing",
    catch: "歴代最悪と呼ばれた魔王を一人で暗殺したロラン。富も名誉も固辞した彼が唯一望んだのは、一人の人間としての普通の生活だった。冒険者ギルドに就職するも、暗殺者の常識は世間の非常識で、何かとお騒がせしてしまう。",
    authors: [{ name: "白石新" }],
    publisher: "kadokawa",
    total_volumes: 9,
    max_edition_volumes: 9,
  };
  return (
    <div className="max-w-xl">
      <MangaCard manga={manga} publishers={publishers} genres={[]} demographics={[]} />
    </div>
  );
}
