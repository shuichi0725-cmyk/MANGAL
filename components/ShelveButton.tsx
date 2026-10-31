"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";
import { SHELVES, type ShelfId, type ShelfItem, itemKey, putItem, removeItem } from "@/lib/myShelf";
import { useMyShelf } from "@/lib/useMyShelf";
import { loadEditionCovers } from "@/lib/volCovers";
// ★見た目の追加は専用CSSへ(Tailwind の新しいクラスを書くと、頁にならないファイルからも拾われて
//   本番の共通CSSが変わる=全頁のHTMLが変わる)
import "./shelve-button.css";

/** 版の選択肢(作品頁の巻一覧と同じ並び=先頭が既定)。total = その版の巻数(小数の番外編は数えない)。 */
export type ShelveEdition = { label: string; total: number };

type Props = {
  slug: string;
  editions: ShelveEdition[];
  /** 最大単一版の巻数(= 一覧索引の max_edition_volumes と同じ数え方) */
  maxTotal: number;
};

const shelfName = (id: ShelfId) => SHELVES.find((s) => s.id === id)!.label;
const stateText = (x: ShelfItem) => `${shelfName(x.shelf)}${x.shelf === "own" ? `・${x.owned ?? 0}巻まで` : ""}`;

const pick = (on: boolean) =>
  `rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
    on
      ? "border-[var(--color-accent)] text-[var(--color-accent)] shadow-[var(--shadow-soft)]"
      : "border-[var(--color-line)] text-ink/70"
  }`;

/**
 * 作品頁の「しまう」ボタン(マイ本棚)。依頼書 = docs/cloud-briefs/my-shelf.md。
 * 2026-10-31 本番にも出す(旧 = プレビュー専用で、作品頁側の require ごと刈り取り+ここで return null の二重の門)。
 * ★同じ作品の別の版を別々にしまえる(2026-10-31 ユーザ裁定 A+1)。 版が2つ以上ある作品は、開くと
 *   「この作品の本棚」= しまってある版が1行ずつ並び、行ごとに変える/取り出す。「＋ほかの版もしまう」で足す。
 *   版が1つの作品は従来どおり(棚・巻数・しまう)。
 * ★索引(useMangaIndex)は読まない = 作品頁は全6.6万頁。材料は頁が既に持っている版だけ。
 *   一覧の小さな書影だけは、開いた時に巻の書影データ(lib/volCovers の1本)を読む。
 * ★題名・書影は受け取らない(2026-09-29 ユーザ裁定「折衷案」): client 部品の props は全項目が
 *   HTML 内の埋め込みと .txt の2か所に書かれる = 7万頁×約0.5KB。控えの題名・書影は本棚の頁が
 *   索引から埋める(app/shelf/MyShelf.tsx の「控えを索引から埋める」効果)。
 *   残る弱点 = しまってから本棚を一度も開かないうちに作品が掲載から外れると、控えが slug だけになる。
 */
export default function ShelveButton(props: Props) {
  return <ShelvePanel {...props} />;
}

/**
 * 棚・巻数を選んでしまう/変える小さな書式。 choices を渡すと版の選択も出す(版をまだ選んでいない1冊・新しく足す版)。
 */
function ShelveForm({
  initialShelf,
  initialOwned,
  choices,
  total: fixedTotal,
  saveLabel,
  onSave,
  onRemove,
}: {
  initialShelf: ShelfId;
  initialOwned: number | null;
  choices?: ShelveEdition[];
  total: number;
  saveLabel: string;
  onSave: (shelf: ShelfId, owned: number, choice: ShelveEdition | null) => void;
  onRemove?: () => void;
}) {
  const [shelf, setShelf] = useState<ShelfId>(initialShelf);
  const [edIdx, setEdIdx] = useState(0);
  const total = choices?.length ? choices[edIdx].total : fixedTotal;
  const [owned, setOwned] = useState(initialOwned ?? total);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const save = () => {
    const n = Math.min(Math.max(0, Math.floor(owned) || 0), Math.max(total, 0));
    onSave(shelf, n, choices?.length ? choices[edIdx] : null);
  };
  return (
    <div className="shelve-form">
      {choices && choices.length > 0 && (
        <label className="block text-xs text-ink/70">
          版
          <select
            value={edIdx}
            onChange={(e) => {
              const i = Number(e.target.value);
              setEdIdx(i);
              setOwned(choices[i].total);
            }}
            className="shelve-select ml-2 rounded border border-[var(--color-line)] bg-[var(--color-surface)] px-2 py-1 text-ink"
          >
            {choices.map((e, i) => (
              <option key={`${e.label}-${i}`} value={i}>
                {e.label}({e.total}巻)
              </option>
            ))}
          </select>
        </label>
      )}
      <div className={`${choices?.length ? "mt-2 " : ""}flex flex-wrap gap-1.5`} role="radiogroup" aria-label="棚">
        {SHELVES.map((s) => (
          <button key={s.id} type="button" role="radio" aria-checked={shelf === s.id} onClick={() => setShelf(s.id)} className={pick(shelf === s.id)}>
            {s.label}
          </button>
        ))}
      </div>
      <p className="mt-1.5 text-[11px] text-ink/50">{SHELVES.find((s) => s.id === shelf)!.note}</p>

      {shelf === "own" && (
        <div className="mt-3">
          <p className="text-xs text-ink/70">何巻まで持ってる?(1巻から続けて持っている最後の巻)</p>
          <div className="mt-1.5 flex items-center gap-2">
            <button type="button" aria-label="1巻減らす" onClick={() => setOwned((v) => Math.max(0, v - 1))} className={pick(false)}>
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
            <button type="button" aria-label="1巻増やす" onClick={() => setOwned((v) => Math.min(total, v + 1))} className={pick(false)}>
              +
            </button>
            <span className="text-xs text-ink/55">/ 既刊 {total}巻</span>
          </div>
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={save}
          className="rounded-full border-2 border-[var(--color-accent)] px-4 py-1.5 text-xs font-bold text-[var(--color-accent)] active:scale-95 transition"
        >
          {saveLabel}
        </button>
        {onRemove && (
          <button
            type="button"
            onClick={() => (confirmRemove ? onRemove() : setConfirmRemove(true))}
            className={pick(false)}
          >
            {confirmRemove ? "もう一度押すと取り出します" : "取り出す"}
          </button>
        )}
      </div>
    </div>
  );
}

function ShelvePanel({ slug, editions, maxTotal }: Props) {
  const { items, ready, persisted, update } = useMyShelf();
  // しまってある版(この作品の分)。 新しく触った順
  const mine = ready ? items.filter((x) => x.slug === slug).sort((a, b) => b.updatedAt - a.updatedAt) : [];
  const multi = editions.length > 1;
  const panelId = useId();
  const [open, setOpen] = useState(false);
  // 変えている1冊の key / "add" = 版を足す書式を開いている
  const [edit, setEdit] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [covers, setCovers] = useState<Map<string, string | null>>(new Map());

  useEffect(() => {
    if (!open) return;
    setEdit(null);
    setDone(null);
    // 一覧の小さな書影 = その版の1巻(版が2つ以上の作品だけ・開いた時に1回)
    if (multi) loadEditionCovers(slug).then(setCovers);
  }, [open, multi, slug]);

  const totalOf = (x: ShelfItem) =>
    editions.find((e) => e.label === x.edition)?.total ?? x.editionTotal ?? editions[0]?.total ?? maxTotal;

  /** 1冊をしまう/変える。 replaceKey = 置き換える前の1冊(版をまだ選んでいなかった1冊に版を付けた時) */
  const put = (shelf: ShelfId, owned: number, edition: ShelveEdition | null, replaceKey?: string) => {
    update((s) =>
      putItem(replaceKey ? removeItem(s, replaceKey) : s, {
        slug,
        title: "", // 控えは本棚の頁が索引から埋める(putItem は既存の控えを消さない)
        cover: null,
        shelf,
        owned: shelf === "own" ? owned : undefined,
        edition: edition ? { label: edition.label, total: edition.total } : null,
      }),
    );
    setEdit(null);
    setDone(`${edition && multi ? `${edition.label}を` : ""}「${shelfName(shelf)}」にしまいました`);
  };
  const remove = (x: ShelfItem) => {
    update((s) => removeItem(s, itemKey(x)));
    setEdit(null);
    setDone(`${x.edition && multi ? `${x.edition}を` : ""}本棚から取り出しました`);
  };

  const head = mine[0];
  const btn =
    "inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-xs font-medium " +
    "shadow-[var(--shadow-soft)] active:scale-95 transition";
  // まだしまっていない版(版を足す書式の選択肢)
  const rest = editions.filter((e) => !mine.some((x) => x.edition === e.label));

  return (
    <div className="mt-3">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className={`${btn} ${
          head
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
        {head ? `${stateText(head)}${mine.length > 1 ? ` ＋${mine.length - 1}版` : ""}` : "しまう"}
      </button>

      {open && (
        <div
          id={panelId}
          className="shelve-panel mt-2 max-w-sm border border-[var(--color-line)] bg-[var(--color-surface)] p-3 text-[13px]"
        >
          {!multi ? (
            // ── 版が1つの作品 = 従来どおり ──
            <>
              <p className="mb-2 text-xs font-semibold text-ink/70">どの棚にしまう?</p>
              <ShelveForm
                key={head ? itemKey(head) : "new"}
                initialShelf={head?.shelf ?? "own"}
                initialOwned={head?.owned ?? null}
                total={editions[0]?.total ?? maxTotal}
                saveLabel={head ? "変更する" : "しまう"}
                onSave={(shelf, n) =>
                  put(
                    shelf,
                    n,
                    // 版ラベル付きでしまってあった1冊はその版のまま(版が1つになった作品)
                    head?.edition ? { label: head.edition, total: totalOf(head) } : null,
                  )
                }
                onRemove={head ? () => remove(head) : undefined}
              />
            </>
          ) : (
            // ── 版が2つ以上 = この作品の本棚(しまった版の一覧)+ ほかの版を足す ──
            <>
              {mine.length > 0 && (
                <>
                  <p className="text-xs font-semibold text-ink/70">この作品の本棚</p>
                  <ul className="shelve-list">
                    {mine.map((x) => {
                      const k = itemKey(x);
                      const cover = x.edition ? covers.get(x.edition) : null;
                      return (
                        <li key={k} className="shelve-item">
                          <div className="shelve-line">
                            {cover ? (
                              // eslint-disable-next-line @next/next/no-img-element -- 外部CDN直リンク(images.unoptimized)
                              <img src={cover} alt="" loading="lazy" decoding="async" className="shelve-thumb bg-white" />
                            ) : (
                              <span className="shelve-thumb is-empty" aria-hidden="true" />
                            )}
                            <span className="shelve-line-body">
                              <span className="shelve-line-t">{x.edition ?? "(版の指定なし)"}</span>
                              <span className="shelve-line-s">
                                <b>{shelfName(x.shelf)}</b>
                                {x.shelf === "own" ? `・${x.owned ?? 0}巻まで` : ""}(全{totalOf(x)}巻)
                              </span>
                            </span>
                            <button type="button" onClick={() => setEdit((v) => (v === k ? null : k))} className="shelve-mini" aria-expanded={edit === k}>
                              {edit === k ? "閉じる" : "変える"}
                            </button>
                          </div>
                          {edit === k && (
                            <ShelveForm
                              key={k}
                              initialShelf={x.shelf}
                              initialOwned={x.owned ?? null}
                              // 版をまだ選んでいない1冊(本棚が版ごとになる前にしまった分・羅針盤から入れた分)は版も選ぶ
                              choices={x.edition ? undefined : rest}
                              total={totalOf(x)}
                              saveLabel="変更する"
                              onSave={(shelf, n, choice) =>
                                x.edition
                                  ? put(shelf, n, { label: x.edition, total: totalOf(x) })
                                  : put(shelf, n, choice, choice ? k : undefined)
                              }
                              onRemove={() => remove(x)}
                            />
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </>
              )}
              {rest.length > 0 &&
                (mine.length === 0 ? (
                  <>
                    <p className="mb-2 text-xs font-semibold text-ink/70">どの版を、どの棚にしまう?</p>
                    <ShelveForm key="first" initialShelf="own" initialOwned={null} choices={rest} total={rest[0].total} saveLabel="しまう" onSave={(shelf, n, c) => put(shelf, n, c)} />
                  </>
                ) : (
                  <>
                    <button type="button" onClick={() => setEdit((v) => (v === "add" ? null : "add"))} className="shelve-add" aria-expanded={edit === "add"}>
                      {edit === "add" ? "－ 閉じる" : "＋ ほかの版もしまう"}
                    </button>
                    {edit === "add" && (
                      <ShelveForm key="add" initialShelf="own" initialOwned={null} choices={rest} total={rest[0].total} saveLabel="しまう" onSave={(shelf, n, c) => put(shelf, n, c)} />
                    )}
                  </>
                ))}
            </>
          )}

          <div className="mt-3 flex items-center">
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
