import React from "react";
import { VolumeTile } from "mangal";

const COVER =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 120'>" +
      "<rect width='80' height='120' fill='#d23f3f'/>" +
      "<text x='40' y='64' font-size='9' fill='#fff' text-anchor='middle'>1</text></svg>",
  );

const manga = {
  slug: "berserk",
  title: "ベルセルク",
  editions: [{ label: "通常版", publisher: "白泉社", volumes: [] }],
};

const edition = { label: "通常版", publisher: "白泉社", imprint: "ヤングアニマルコミックス", volumes: [] };

/** A volume with a cover, a release date and a buy link. */
export function WithCover() {
  const volume = {
    number: 1,
    release_date: "1990-11-24",
    cover_url: COVER,
    isbn13: "9784592132011",
  };
  return (
    <div className="max-w-xl">
      <VolumeTile manga={manga} volume={volume} edition={edition} />
    </div>
  );
}

/** No cover yet — the slot keeps its shape and shows the volume number. */
export function WithoutCover() {
  const volume = { number: 7, release_date: "1995-03-29", cover_url: null, isbn13: "9784592132073" };
  return (
    <div className="max-w-xl">
      <VolumeTile manga={manga} volume={volume} edition={edition} />
    </div>
  );
}

/** Per-volume credits and a publisher that differs from the edition's. */
export function WithPerVolumeCredits() {
  const volume = {
    number: 76,
    release_date: "2007-06-30",
    cover_url: null,
    isbn13: "9784845833016",
    publisher: "リイド社",
    artists: ["さいとう・たかを"],
    supervisors: ["池波正太郎"],
  };
  return (
    <div className="max-w-xl">
      <VolumeTile
        manga={{ ...manga, title: "鬼平犯科帳" }}
        volume={volume}
        edition={{ ...edition, label: "文庫版", publisher: "文藝春秋" }}
      />
    </div>
  );
}

/** Carrying a per-volume description — the B2 blurb the volume seed supplies. */
export function WithDescription() {
  const volume = {
    number: 1,
    release_date: "2021-09-09",
    cover_url: COVER,
    isbn13: "9784049128840",
    description:
      "自身のスキル「影が薄い」を駆使し、歴代最悪と呼ばれた魔王を一人で暗殺したロラン。富も名誉も固辞した彼が唯一望んだものは、一人の人間としての普通の生活だった。",
  };
  return (
    <div className="max-w-xl">
      <VolumeTile
        manga={{ ...manga, title: "ハズレスキル《影が薄い》" }}
        volume={volume}
        edition={edition}
      />
    </div>
  );
}

/** A short run rendered as the volume list does. */
export function AsVolumeList() {
  const vols = [1, 2, 3].map((n) => ({
    number: n,
    release_date: `199${n}-0${n + 1}-24`,
    cover_url: COVER,
    isbn13: `978459213201${n}`,
  }));
  return (
    <div className="max-w-xl space-y-4">
      {vols.map((v) => (
        <VolumeTile key={v.number} manga={manga} volume={v} edition={edition} />
      ))}
    </div>
  );
}
