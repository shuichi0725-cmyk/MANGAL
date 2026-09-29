"use client";

import { useState } from "react";
import type { MangaListItem } from "@/lib/schema";
import { SHELVES, type ShelfId, putItem, removeItem } from "@/lib/myShelf";
import { useMyShelf } from "@/lib/useMyShelf";

/** 書庫のアイコン(ヘッダーの「書庫」と同じ絵柄 = components/GlobalNav.tsx の NAV_SVG.書庫)。 */
export function ShelfIcon({ size = 14 }: { size?: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      width={size}
      height={size}
      style={{ stroke: "currentColor", fill: "none", strokeWidth: 1.9, flex: "none" }}
    >
      <path d="M4 4h4v16H4zM9 7h4v13H9zM14.2 6.3l3.8-1 3.3 12.6-3.8 1zM3 20h18" />
    </svg>
  );
}

/**
 * 羅針盤のシートの「しまう」(2026-09-30 ユーザ裁定: 言葉=案A「しまう」・アイコン=ヘッダーの書庫)。
 * 押すとシートの中に 3つの棚(もってる/気になる/ほしい)が並び、選ぶと閉じる。
 * しまった後はボタンが「✓ 気になる」のように棚の名前へ変わり、もう一度押すと棚の変更と取り出し。
 * ★もってるは「既刊まで」で入れる(巻数は書庫で直せる)。 題名・書影の控えは羅針盤が持つ索引の値をそのまま使う。
 */
export function CompassShelveButton({ open, onToggle, slug }: { open: boolean; onToggle: () => void; slug: string }) {
  const { items, ready } = useMyShelf();
  const mine = ready ? items.find((x) => x.slug === slug) : undefined;
  const label = mine ? SHELVES.find((s) => s.id === mine.shelf)!.label : null;
  return (
    <button
      type="button"
      className={`cp-shelve${mine ? " is-in" : ""}`}
      aria-expanded={open}
      onClick={onToggle}
      aria-label={mine ? `書庫の「${label}」に入っています(変更・取り出し)` : "書庫にしまう"}
    >
      <ShelfIcon />
      {mine ? (
        <span>
          ✓ {label}
          {mine.shelf === "own" ? `・${mine.owned ?? 0}巻まで` : ""}
        </span>
      ) : (
        <span>しまう</span>
      )}
    </button>
  );
}

export function CompassShelvePanel({ item, onDone }: { item: MangaListItem; onDone: (msg: string) => void }) {
  const { items, ready, update } = useMyShelf();
  const mine = ready ? items.find((x) => x.slug === item.slug) : undefined;
  const [confirm, setConfirm] = useState(false);
  const put = (shelf: ShelfId) => {
    const total = item.max_edition_volumes || 0;
    update((s) =>
      putItem(s, {
        slug: item.slug,
        title: item.title,
        cover: item.cover ?? null,
        shelf,
        // もってるは既刊まで(既に「もってる」なら今の巻数を保つ)
        owned: shelf === "own" ? (mine?.shelf === "own" ? mine.owned : total) : undefined,
      }),
    );
    const name = SHELVES.find((s) => s.id === shelf)!.label;
    onDone(shelf === "own" && mine?.shelf !== "own" ? `「${name}」に既刊まで(${total}巻)で入れました・巻数は書庫で直せます` : `「${name}」にしまいました`);
  };
  const remove = () => {
    if (!confirm) {
      setConfirm(true);
      return;
    }
    update((s) => removeItem(s, item.slug));
    onDone("書庫から取り出しました");
  };
  return (
    <div className="cp-shelve-panel" role="group" aria-label="どの棚にしまう?">
      {SHELVES.map((s) => (
        <button
          key={s.id}
          type="button"
          className={`cp-shelve-chip${mine?.shelf === s.id ? " on" : ""}`}
          aria-pressed={mine?.shelf === s.id}
          onClick={() => put(s.id)}
        >
          {s.label}
        </button>
      ))}
      {mine && (
        <button type="button" className={`cp-shelve-chip out${confirm ? " confirm" : ""}`} onClick={remove}>
          {confirm ? "本当に取り出す" : "取り出す"}
        </button>
      )}
    </div>
  );
}
