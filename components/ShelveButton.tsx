"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";
import { SHELVES, type ShelfId, putItem, removeItem } from "@/lib/myShelf";
import { useMyShelf } from "@/lib/useMyShelf";
// ★見た目の追加は専用CSSへ(Tailwind の新しいクラスを書くと、頁にならないファイルからも拾われて
//   本番の共通CSSが変わる=全頁のHTMLが変わる。この import は本番では require ごと刈り取られる)
import "./shelve-button.css";

/** 版の選択肢(作品頁の巻一覧と同じ並び=先頭が既定)。total = その版の巻数(小数の番外編は数えない)。 */
export type ShelveEdition = { label: string; total: number };

type Props = {
  slug: string;
  editions: ShelveEdition[];
  /** 最大単一版の巻数(= 一覧索引の max_edition_volumes と同じ数え方) */
  maxTotal: number;
};

/**
 * 作品頁の「しまう」ボタン(マイ本棚・プレビュー専用)。依頼書 = docs/cloud-briefs/my-shelf.md。
 * ★本番には出ない: next.config.ts が NEXT_PUBLIC_PREVIEW_FEATURES を定数で埋め、作品頁側の
 *   `=== "1" ? require(...) : null` で require ごと刈り取られる。ここの return null は二重の門。
 * ★索引(useMangaIndex)は読まない = 作品頁は全6.6万頁。材料は頁が既に持っている版だけ。
 * ★題名・書影は受け取らない(2026-09-29 ユーザ裁定「折衷案」): client 部品の props は全項目が
 *   HTML 内の埋め込みと .txt の2か所に書かれる = 7万頁×約0.5KB。控えの題名・書影は本棚の頁が
 *   索引から埋める(app/shelf/MyShelf.tsx の「控えを索引から埋める」効果)。
 *   残る弱点 = しまってから本棚を一度も開かないうちに作品が掲載から外れると、控えが slug だけになる。
 */
export default function ShelveButton(props: Props) {
  if (process.env.NEXT_PUBLIC_PREVIEW_FEATURES !== "1") return null;
  return <ShelvePanel {...props} />;
}

function ShelvePanel({ slug, editions, maxTotal }: Props) {
  const { items, ready, persisted, update } = useMyShelf();
  const mine = ready ? items.find((x) => x.slug === slug) : undefined;
  const panelId = useId();
  const [open, setOpen] = useState(false);
  const [choice, setChoice] = useState<ShelfId>("own");
  const [edIdx, setEdIdx] = useState(0);
  const [owned, setOwned] = useState(0);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [done, setDone] = useState<string | null>(null);

  const total = editions[edIdx]?.total ?? maxTotal;
  // ★既定の版(=頁の先頭)が最大の版と巻数が違う時は、索引の巻数と比べると「続き」を誤って出す
  //   (文庫8巻を持っていて通常版30巻と比べる等)= 先頭の版でも「版を選んだ」扱いで登録時点の巻数を持つ。
  const fixEdition = edIdx !== 0 || (editions[0] && editions[0].total !== maxTotal);

  // 開いた時は、しまってある中身(無ければ「もってる・既刊まで」)から始める
  useEffect(() => {
    if (!open) return;
    const i = mine?.edition ? Math.max(0, editions.findIndex((e) => e.label === mine.edition)) : 0;
    setChoice(mine?.shelf ?? "own");
    setEdIdx(i);
    setOwned(mine?.owned ?? editions[i]?.total ?? maxTotal);
    setConfirmRemove(false);
    setDone(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const save = () => {
    const n = Math.min(Math.max(0, Math.floor(owned) || 0), Math.max(total, 0));
    update((s) =>
      putItem(s, {
        slug,
        title: "", // 控えは本棚の頁が索引から埋める(putItem は既存の控えを消さない)
        cover: null,
        shelf: choice,
        owned: choice === "own" ? n : undefined,
        edition: fixEdition && editions[edIdx] ? { label: editions[edIdx].label, total } : null,
      }),
    );
    setDone(`「${SHELVES.find((x) => x.id === choice)!.label}」にしまいました`);
  };

  const remove = () => {
    if (!confirmRemove) {
      setConfirmRemove(true);
      return;
    }
    update((s) => removeItem(s, slug));
    setConfirmRemove(false);
    setDone("本棚から取り出しました");
  };

  const shelfLabel = mine ? SHELVES.find((x) => x.id === mine.shelf)!.label : null;
  const btn =
    "inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-xs font-medium " +
    "shadow-[var(--shadow-soft)] active:scale-95 transition";
  const pick = (on: boolean) =>
    `rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
      on
        ? "border-[var(--color-accent)] text-[var(--color-accent)] shadow-[var(--shadow-soft)]"
        : "border-[var(--color-line)] text-ink/70"
    }`;

  return (
    <div className="mt-3">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className={`${btn} ${
          mine
            ? "border-[var(--color-accent)] bg-[var(--color-surface)] text-[var(--color-accent)]"
            : "border-[var(--color-line)] bg-[var(--color-surface)] text-ink/75 hover:text-[var(--color-accent)]"
        }`}
      >
        {/* ヘッダーの「本棚」と同じアイコン(2026-09-30 ユーザ裁定) */}
        <svg
          viewBox="0 0 24 24"
          aria-hidden="true"
          width={14}
          height={14}
          style={{ stroke: "currentColor", fill: "none", strokeWidth: 1.9, flex: "none" }}
        >
          <path d="M4 4h4v16H4zM9 7h4v13H9zM14.2 6.3l3.8-1 3.3 12.6-3.8 1zM3 20h18" />
        </svg>
        {/* ★サーバ描画・水和直後は必ず「しまう」(端末の中身は水和後に読む) */}
        {mine ? `${shelfLabel}${mine.shelf === "own" ? `・${mine.owned ?? 0}巻まで` : ""}` : "しまう"}
      </button>

      {open && (
        <div
          id={panelId}
          className="shelve-panel mt-2 max-w-sm border border-[var(--color-line)] bg-[var(--color-surface)] p-3 text-[13px]"
        >
          <p className="text-xs font-semibold text-ink/70">どの棚にしまう?</p>
          <div className="mt-2 flex flex-wrap gap-1.5" role="radiogroup" aria-label="棚">
            {SHELVES.map((s) => (
              <button
                key={s.id}
                type="button"
                role="radio"
                aria-checked={choice === s.id}
                onClick={() => setChoice(s.id)}
                className={pick(choice === s.id)}
              >
                {s.label}
              </button>
            ))}
          </div>
          <p className="mt-1.5 text-[11px] text-ink/50">{SHELVES.find((s) => s.id === choice)!.note}</p>

          {editions.length > 1 && (
            <label className="mt-3 block text-xs text-ink/70">
              版
              <select
                value={edIdx}
                onChange={(e) => {
                  const i = Number(e.target.value);
                  setEdIdx(i);
                  setOwned((v) => Math.min(v, editions[i].total));
                }}
                className="shelve-select ml-2 rounded border border-[var(--color-line)] bg-[var(--color-surface)] px-2 py-1 text-ink"
              >
                {editions.map((e, i) => (
                  <option key={`${e.label}-${i}`} value={i}>
                    {e.label}({e.total}巻)
                  </option>
                ))}
              </select>
            </label>
          )}

          {choice === "own" && (
            <div className="mt-3">
              <p className="text-xs text-ink/70">何巻まで持ってる?(1巻から続けて持っている最後の巻)</p>
              <div className="mt-1.5 flex items-center gap-2">
                <button
                  type="button"
                  aria-label="1巻減らす"
                  onClick={() => setOwned((v) => Math.max(0, v - 1))}
                  className={pick(false)}
                >
                  −
                </button>
                <input
                  type="number"
                  inputMode="numeric"
                  min={0}
                  max={total}
                  value={owned}
                  onChange={(e) => setOwned(Number(e.target.value))}
                  aria-label="持っている最後の巻"
                  // 16px = iOS が入力時に拡大しない大きさ
                  className="w-20 rounded border border-[var(--color-line)] bg-[var(--color-surface)] px-2 py-1 text-center text-[16px] tabular-nums text-ink"
                />
                <button
                  type="button"
                  aria-label="1巻増やす"
                  onClick={() => setOwned((v) => Math.min(total, v + 1))}
                  className={pick(false)}
                >
                  +
                </button>
                <span className="text-xs text-ink/55">/ 既刊 {total}巻</span>
              </div>
              {fixEdition && (
                <p className="mt-1 text-[11px] text-ink/50">
                  この版の今の巻数({total}巻)で「続き」を数えます(新刊が出ても自動では増えません)。
                </p>
              )}
            </div>
          )}

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={save}
              className="rounded-full border-2 border-[var(--color-accent)] px-4 py-1.5 text-xs font-bold text-[var(--color-accent)] active:scale-95 transition"
            >
              {mine ? "変更する" : "しまう"}
            </button>
            {mine && (
              <button type="button" onClick={remove} className={pick(false)}>
                {confirmRemove ? "もう一度押すと取り出します" : "取り出す"}
              </button>
            )}
            <Link
              href="/shelf"
              prefetch={false}
              className="ml-auto text-xs text-ink/60 underline decoration-dotted underline-offset-2 hover:text-[var(--color-accent)]"
            >
              本棚を見る →
            </Link>
          </div>
          {done && (
            <p className="mt-2 text-[11px] text-[var(--color-accent)]" role="status">
              {done}
            </p>
          )}
          {!persisted && (
            <p className="mt-2 text-[11px] text-ink/55">
              この端末(ブラウザ)では保存できないため、頁を閉じると消えます。本棚の頁の「棚のURL」で持ち出せます。
            </p>
          )}
        </div>
      )}
    </div>
  );
}
