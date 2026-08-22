import React from "react";
import { ChipLink } from "mangal";

/** Category navigation — same skin as ChipButton, but it navigates. */
export function Categories() {
  return (
    <div className="flex max-w-md flex-wrap gap-2">
      <ChipLink href="/genre/action">アクション</ChipLink>
      <ChipLink href="/genre/fantasy">ファンタジー</ChipLink>
      <ChipLink href="/genre/romance">恋愛</ChipLink>
      <ChipLink href="/genre/sports">スポーツ</ChipLink>
    </div>
  );
}

/** The current facet is marked `active`. */
export function WithActive() {
  return (
    <div className="flex max-w-md flex-wrap gap-2">
      <ChipLink href="/demographic/shonen" active>少年</ChipLink>
      <ChipLink href="/demographic/seinen">青年</ChipLink>
      <ChipLink href="/demographic/shoujo">少女</ChipLink>
      <ChipLink href="/demographic/josei">女性</ChipLink>
    </div>
  );
}
