import React from "react";
import { EditionVolumes } from "mangal";

const COVER = (n: number) =>
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 120'>" +
      "<rect width='80' height='120' fill='#d23f3f'/>" +
      "<text x='40' y='64' font-size='11' fill='#fff' text-anchor='middle'>" + n + "</text></svg>",
  );

const vol = (n: number) => ({
  number: n,
  release_date: `19${89 + n}-11-24`,
  cover_url: COVER(n),
  isbn13: `97845921320${String(n).padStart(2, "0")}`,
});

const manga = { slug: "berserk", title: "ベルセルク", editions: [] };

/** One edition, no reprints — the plain volume shelf. */
export function SingleEdition() {
  const edition = {
    label: "通常版",
    publisher: "白泉社",
    imprint: "ヤングアニマルコミックス",
    volumes: [1, 2, 3, 4, 5, 6].map(vol),
  };
  return (
    <div className="max-w-xl">
      <EditionVolumes manga={manga} edition={edition} />
    </div>
  );
}

/** Two reprints — the oldest fully-in-stock one is selected by default. */
export function WithVersionTabs() {
  const edition = {
    label: "文庫版",
    publisher: "白泉社",
    imprint: "白泉社文庫",
    volumes: [1, 2, 3].map(vol),
    versions: [
      { label: "初版", volumes: [1, 2, 3].map(vol) },
      { label: "新装版", volumes: [1, 2, 3, 4].map(vol) },
    ],
  };
  return (
    <div className="max-w-xl">
      <EditionVolumes manga={manga} edition={edition} />
    </div>
  );
}

/** Collapsed by default — how secondary editions open on a work page. */
export function Collapsed() {
  const edition = {
    label: "愛蔵版",
    publisher: "白泉社",
    imprint: "ジェッツコミックス",
    volumes: [1, 2, 3].map(vol),
  };
  return (
    <div className="max-w-xl">
      <EditionVolumes manga={manga} edition={edition} defaultCollapsed />
    </div>
  );
}
