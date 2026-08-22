import React from "react";
import { ChipButton } from "mangal";

const GENRES = ["アクション", "ファンタジー", "恋愛", "スポーツ", "ミステリー", "ギャグ"];

/** A live filter row — click to toggle. Active chips take the accent fill. */
export function FilterRow() {
  const [on, setOn] = React.useState<string[]>(["アクション", "ファンタジー"]);
  const toggle = (g: string) =>
    setOn((prev) => (prev.includes(g) ? prev.filter((x) => x !== g) : [...prev, g]));
  return (
    <div className="flex max-w-md flex-wrap gap-2">
      {GENRES.map((g) => (
        <ChipButton key={g} active={on.includes(g)} onClick={() => toggle(g)}>
          {g}
        </ChipButton>
      ))}
    </div>
  );
}

/** The two states side by side. */
export function States() {
  return (
    <div className="flex flex-wrap gap-2">
      <ChipButton active={false} onClick={() => {}}>未選択</ChipButton>
      <ChipButton active onClick={() => {}}>選択中</ChipButton>
    </div>
  );
}
