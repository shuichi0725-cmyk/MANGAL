import React from "react";
import { ArtBookCard } from "mangal";

const COVER =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 120'>" +
      "<rect width='80' height='120' fill='#e0892e'/>" +
      "<text x='40' y='64' font-size='9' fill='#fff' text-anchor='middle'>ART</text></svg>",
  );

/** The catalogue row: 画集 badge, artist, publisher and year. */
export function Standard() {
  const artBook = {
    slug: "berserk-gaiden",
    title: "ベルセルク画集",
    artist: "三浦建太郎",
    publisher: "白泉社",
    year: 2002,
    volumes: [{ cover_url: null }],
  };
  return (
    <div className="max-w-xl">
      <ArtBookCard artBook={artBook} />
    </div>
  );
}

/** With a cover image in the slot instead of the 🎨 placeholder. */
export function WithCover() {
  const artBook = {
    slug: "tezuka-osamu-genga",
    title: "手塚治虫 原画の秘密",
    artist: "手塚治虫",
    publisher: "小学館クリエイティブ",
    year: 2011,
    volumes: [{ cover_url: COVER }],
  };
  return (
    <div className="max-w-xl">
      <ArtBookCard artBook={artBook} />
    </div>
  );
}

/** Sparse metadata — publisher and year are both optional. */
export function MinimalMetadata() {
  const artBook = {
    slug: "ikeda-riyoko-illustrations",
    title: "池田理代子 イラスト集",
    artist: "池田理代子",
    publisher: null,
    year: null,
    volumes: [{ cover_url: null }],
  };
  return (
    <div className="max-w-xl">
      <ArtBookCard artBook={artBook} />
    </div>
  );
}

/** Several rows stacked, as the 画集 catalogue lists them. */
export function AsCatalogue() {
  const books = [
    { slug: "a", title: "ベルセルク画集", artist: "三浦建太郎", publisher: "白泉社", year: 2002, volumes: [{ cover_url: null }] },
    { slug: "b", title: "手塚治虫 原画の秘密", artist: "手塚治虫", publisher: "小学館クリエイティブ", year: 2011, volumes: [{ cover_url: COVER }] },
    { slug: "c", title: "ジョジョ展 図録", artist: "荒木飛呂彦", publisher: "集英社", year: 2018, volumes: [{ cover_url: null }] },
  ];
  return (
    <div className="max-w-xl space-y-2">
      {books.map((b) => (
        <ArtBookCard key={b.slug} artBook={b} />
      ))}
    </div>
  );
}
