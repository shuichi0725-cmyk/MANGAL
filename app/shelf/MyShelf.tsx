"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  type FetchFinal,
  type ImportMode,
  type IndexFacts,
  type OwnedNote,
  type PlaqueStats,
  type ShelfId,
  type ShelfItem,
  SHELVES,
  countByShelf,
  decodeShelf,
  importShelf,
  itemKey,
  moveItem,
  ownedNote,
  plaqueStats,
  removeItem,
  renameSlug,
  resolveMovedSlug,
  setOwned,
  volumeTiles,
} from "@/lib/myShelf";
import {
  type BackupMark,
  type ImportMark,
  BACKUP_MARK_KEY,
  IMPORT_MARK_KEY,
  backupHeader,
  codeSig,
  encodeShelfCode,
  mergeWithMark,
  parseMark,
  readShelfCode,
  shelfCodeUrl,
} from "@/lib/shelfCode";
import { type DivideEntry, type DivideMode, DIVIDE_KEY, DIVIDE_MODES, divide, isDivideMode } from "@/lib/shelfDivide";
import { useRailMasters } from "@/lib/useRailMasters";
import type { MangaListItem } from "@/lib/schema";
import { ensureFullIndex, isFullIndexLoaded, useMangaIndex } from "@/lib/useMangaIndex";
import { useMyShelf } from "@/lib/useMyShelf";
import { loadEditionFacts } from "@/lib/volCovers";
import BuyLinks from "./BuyLinks";
import VolPeek from "./VolPeek";

type GenreDef = { key: string; name: string };

/** 旧 slug の作品頁を HEAD で取りに行き、301 を辿った先の URL を返す(同一オリジン=fetch が自動で辿る)。 */
const fetchFinal: FetchFinal = async (path) => {
  const r = await fetch(path, { method: "HEAD", cache: "no-store" });
  return { url: r.url, ok: r.ok };
};

const STATUS_LABEL: Record<string, string> = { completed: "完結", ongoing: "連載中", hiatus: "休載中" };

/**
 * 長押し(タッチ)・右クリックでメニュー。
 * ★長押しが成立した後、指を離した時の「クリック」を1回だけ飲み込む。飲まないと、開いたメニューの
 *   背景(= 押すと閉じる)にそのクリックが落ちて、開いた瞬間に閉じる/作品頁へ飛ぶ(2026-09-28 実測)。
 *   クリックの行き先は札とは限らない(メニューが被さる)ので、window の捕捉段階で止める。
 */
function useLongPress(onLong: () => void) {
  const timer = useRef<number | null>(null);
  const start = useRef<{ x: number; y: number } | null>(null);
  const clear = () => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = null;
  };
  const swallowNextClick = () => {
    const swallow = (e: MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
    };
    window.addEventListener("click", swallow, { capture: true, once: true });
    // 離した後にクリックが来なかった時(長押しの後に指を滑らせた等)は、次の本物のクリックを食べないよう外す
    const release = () => window.setTimeout(() => window.removeEventListener("click", swallow, { capture: true }), 400);
    window.addEventListener("pointerup", release, { once: true });
    window.addEventListener("pointercancel", release, { once: true });
  };
  return {
    onPointerDown: (e: React.PointerEvent) => {
      if (e.pointerType === "mouse") return; // マウスは右クリック(onContextMenu)で開く
      start.current = { x: e.clientX, y: e.clientY };
      clear();
      timer.current = window.setTimeout(() => {
        timer.current = null;
        swallowNextClick();
        onLong();
      }, 500);
    },
    onPointerMove: (e: React.PointerEvent) => {
      const s = start.current;
      if (s && Math.hypot(e.clientX - s.x, e.clientY - s.y) > 10) clear(); // 横スクロールは長押しにしない
    },
    onPointerUp: clear,
    onPointerCancel: clear,
    onPointerLeave: clear,
    // PC の右クリック・Android の長押し(こちらは離してもクリックが来ない)
    onContextMenu: (e: React.MouseEvent) => {
      e.preventDefault();
      clear();
      onLong();
    },
  };
}

type CardData = {
  item: ShelfItem;
  m: MangaListItem | undefined;
  lost: boolean;
  note: OwnedNote | null;
  /** 版ごとにしまった1冊: その版の今の巻数と1巻の書影(巻の書影データから引けた時) */
  live: EditionFacts | undefined;
  /** 段の上の日付「11/17 取り込み」「10/30 から棚に」(2026-11-17 見本②-5a) */
  dateLabel: string;
  /** 最後の取り込みで増えた本(「確認した」を押すまで = 赤茶の段・書影が光る・日付が赤い札) */
  isNew: boolean;
};
type EditionFacts = { total: number; cover: string | null };

/** 1巻の書影を正面向きで1枚(44×64)。無ければ背に題名。★同じ書影を背表紙として並べる表現は使わない(ユーザ裁定) */
function Cover({ src, title }: { src: string | null; title: string }) {
  const [failed, setFailed] = useState(false);
  return (
    <span className="shelf-c3-cover">
      {src && !failed ? (
        // eslint-disable-next-line @next/next/no-img-element -- 外部CDN直リンク(images.unoptimized)
        <img src={src} alt="" loading="lazy" decoding="async" onError={() => setFailed(true)} className="bg-white" />
      ) : (
        <span className="shelf-c3-spine">{title}</span>
      )}
    </span>
  );
}

/** 番号タイル(もってるの段だけ)。10巻で1行、41巻以上は所持の前半を帯に畳む・未所持は1行まで(lib/myShelf volumeTiles)。 */
function Tiles({
  owned,
  total,
  on,
  onPick,
}: {
  owned: number;
  total: number | null;
  on?: number | null;
  onPick?: (n: number) => void;
}) {
  const t = volumeTiles(owned, total);
  if (!t) return null;
  const missing = t.tiles.filter((x) => x.state === "missing").map((x) => x.n);
  const missTo = t.tail ? t.tail.to : missing[missing.length - 1];
  const label =
    (owned > 0 ? `1〜${owned}巻 所持` : "1巻はまだ") + (missing.length ? `・${missing[0]}〜${missTo}巻 未所持` : "");
  return (
    // 読み上げは1文にまとめる。 ★押す = その巻の書影を段の下に開く(2026-10-04)。 段は作品頁へのリンクなので遷移を止める。
    <span className="shelf-c3-tiles" role="group" aria-label={label}>
      {t.band && (
        <span className={`shelf-c3-band${onPick ? " is-pick" : ""}`} {...pickProps(t.band.from, onPick)}>
          {t.band.from}〜{t.band.to}巻 所持({t.band.count}冊)
        </span>
      )}
      {t.tiles.map((x) => (
        <span
          key={x.n}
          className={`shelf-c3-tile is-${x.state}${onPick ? " is-pick" : ""}${on === x.n ? " is-on" : ""}`}
          {...pickProps(x.n, onPick)}
        >
          {x.n}
        </span>
      ))}
      {t.tail && (
        <span className={`shelf-c3-band is-tail${onPick ? " is-pick" : ""}`} {...pickProps(t.tail.from, onPick)}>
          あと{t.tail.count}巻 未所持({t.tail.from}〜{t.tail.to}巻)
        </span>
      )}
    </span>
  );
}

/** 番号タイルを押せるようにする属性(段=作品頁へのリンクの中なので、遷移を止めてから開く)。 */
function pickProps(n: number, onPick?: (n: number) => void) {
  if (!onPick) return {};
  return {
    role: "button" as const,
    tabIndex: 0,
    "aria-label": `第${n}巻の書影を見る`,
    onClick: (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      onPick(n);
    },
    onKeyDown: (e: React.KeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        e.stopPropagation();
        onPick(n);
      }
    },
  };
}

/** 棚の1段 = 1作品(版ごとにしまった時は1つの版)。左に1巻の書影、右に題名・版・所持状況・番号タイル(ほしい/気になるは巻数と状態+キャッチ)。 */
function Row({
  d,
  onMenu,
  onOwned,
  onBought,
  readOnly,
  select,
}: {
  d: CardData;
  /** おすすめを選ぶ(見本④)の間 = 段を押すとチェックが付く(作品頁へは行かない・操作は出さない) */
  select?: { on: boolean; toggle: () => void } | null;
  onMenu: () => void;
  /** U1: 書影欄の「ここ(N巻)まで持ってる」 */
  onOwned: (n: number) => void;
  /** U2: ほしい・気になるの「1巻を買った」= もってる・1巻まで へ */
  onBought: () => void;
  readOnly: boolean;
}) {
  const { item, m, lost, note, live } = d;
  const title = m?.title ?? (item.title || item.slug);
  // 版ごとにしまった1冊はその版の1巻の書影(2026-10-31 本棚 A+1)
  const cover = live?.cover ?? m?.cover ?? item.cover;
  const author = m?.authors[0]?.name;
  const press = useLongPress(onMenu);
  const [vol, setVol] = useState<number | null>(null); // 書影を開いている巻(番号タイルを押した)
  const alert = note && (note.kind === "behind" || note.kind === "complete-behind");
  const body = (
    <>
      <Cover src={cover} title={title} />
      <span className="shelf-c3-body">
        {d.dateLabel && <span className="shelf-c3-date">{d.isNew ? `🆕 ${d.dateLabel}` : d.dateLabel}</span>}
        <span className="shelf-c3-title">{title}</span>
        {item.edition && <span className="shelf-c3-ed">{item.edition}</span>}
        {lost ? (
          <span className="shelf-c3-sub">この作品は見つからなくなりました</span>
        ) : note ? (
          <>
            <span className={`shelf-c3-note${alert ? " is-alert" : ""}`}>{note.text}</span>
            <Tiles
              owned={item.owned ?? 0}
              total={note.total}
              on={vol}
              onPick={select ? undefined : (n) => setVol((v) => (v === n ? null : n))}
            />
          </>
        ) : (
          m && (
            <>
              <span className="shelf-c3-sub">
                {(live?.total ?? (item.edition ? item.editionTotal : null) ?? m.max_edition_volumes)
                  ? `全${live?.total ?? (item.edition ? item.editionTotal : null) ?? m.max_edition_volumes}巻・`
                  : ""}
                {STATUS_LABEL[m.status] ?? ""}
              </span>
              {m.catch && <span className="shelf-c3-catch">{m.catch}</span>}
            </>
          )
        )}
      </span>
    </>
  );
  if (select)
    return (
      <li className={`shelf-c3-row is-select${select.on ? " is-on" : ""}${d.isNew ? " is-new" : ""}`}>
        <button type="button" className="shelf-c3-link shelf-c3-selrow" aria-pressed={select.on} onClick={select.toggle}>
          <span className="shelf-c3-check" aria-hidden="true">
            {select.on ? "✓" : ""}
          </span>
          {body}
        </button>
      </li>
    );
  return (
    <li className={`shelf-c3-row${d.isNew ? " is-new" : ""}`}>
      {lost ? (
        <div className="shelf-c3-link shelf-press" {...(readOnly ? {} : press)}>
          {body}
        </div>
      ) : (
        <Link href={`/manga/${item.slug}`} prefetch={false} className="shelf-c3-link shelf-press" {...(readOnly ? {} : press)}>
          {body}
        </Link>
      )}
      {!readOnly && (
        <button type="button" onClick={onMenu} aria-label={`${title} の棚の操作`} className="shelf-c3-menu">
          ⋯
        </button>
      )}
      {/* ★その場で Kindle・Amazon(2026-10-31 ユーザ要望): もってる=続きの最初の巻 / ほしい・気になる=作品名。 段(Link)の外に置く */}
      {!lost && (item.shelf === "own" ? !!note?.next.length : true) && (
        <div className="shelf-c3-buybar">
          {item.shelf === "own" ? (
            <BuyLinks title={title} author={author} n={note!.next[0]} label={`次は${note!.next[0]}巻`} />
          ) : (
            <>
              <BuyLinks title={title} author={author} />
              {/* U2(2026-10-31 ユーザ裁定 A+U1+U2+U4): 買ったら1手で「もってる・1巻まで」へ(取り消しは札) */}
              {!readOnly && (
                <button type="button" className="shelf-c3-bought" onClick={onBought}>
                  1巻を買った → もってるへ
                </button>
              )}
            </>
          )}
        </div>
      )}
      {vol !== null && !lost && (
        <VolPeek
          slug={item.slug}
          edition={item.edition}
          title={title}
          author={author}
          n={vol}
          owned={item.owned ?? 0}
          onOwned={readOnly ? undefined : onOwned}
          onN={setVol}
          onClose={() => setVol(null)}
        />
      )}
    </li>
  );
}

/** 真鍮の銘板 = 集計3つ(lib/myShelf plaqueStats)。 */
function Plaque({ stats }: { stats: PlaqueStats }) {
  return (
    <div className="shelf-c3-plaque" role="group" aria-label="集計">
      {/* 案A(2026-10-31): 1行に細く = 棚を上へ */}
      <div>
        <b>{stats.ownedVolumes.toLocaleString()}</b>
        <span>冊</span>
      </div>
      <div>
        <b>{stats.nextVolumes.toLocaleString()}</b>
        <span>続きの巻</span>
      </div>
      <div>
        <b>{stats.caughtUpWorks.toLocaleString()}</b>
        <span>そろった</span>
      </div>
    </div>
  );
}

function Sheet({
  d,
  genreName,
  onClose,
  onMove,
  onOwned,
  onRemove,
}: {
  d: CardData;
  genreName: Map<string, string>;
  onClose: () => void;
  onMove: (s: ShelfId) => void;
  onOwned: (n: number) => void;
  onRemove: () => void;
}) {
  const { item, m, lost, note } = d;
  const title = m?.title ?? (item.title || item.slug);
  const [confirm, setConfirm] = useState(false);
  const max = note?.total ?? 9999;
  const nextVol = note?.next[0];
  const pick = (on: boolean) =>
    `rounded-full border px-3 py-1.5 text-xs font-semibold ${
      on ? "border-[var(--color-accent)] text-[var(--color-accent)]" : "border-[var(--color-line)] text-ink/70"
    }`;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="shelf-backdrop fixed inset-0 z-40 flex items-end justify-center bg-black/60" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`${title} の棚の操作`}
        onClick={(e) => e.stopPropagation()}
        className="shelf-sheet w-full max-w-md overflow-y-auto border-t-2 border-[var(--color-accent)] bg-[var(--color-surface)] p-4 text-[13px]"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[15px] font-bold leading-snug">{title}</p>
            {item.edition && <p className="mt-0.5 text-[11.5px] font-semibold text-[var(--color-accent)]">{item.edition}</p>}
            {m && (
              <p className="mt-0.5 text-[11px] text-ink/55">
                {STATUS_LABEL[m.status]}
                {m.max_edition_volumes ? `・${m.max_edition_volumes}巻` : ""}
                {m.latest_date ? `・最新刊 ${m.latest_date.replace("-", "年")}月` : ""}
                {m.genres.length ? `・${m.genres.map((g) => genreName.get(g) ?? g).join("/")}` : ""}
              </p>
            )}
            {lost && <p className="mt-0.5 text-[11px] text-ink/55">この作品は見つからなくなりました(改名・統合の転送先もありません)</p>}
          </div>
          <button type="button" onClick={onClose} aria-label="閉じる" className="shrink-0 px-2 text-lg text-ink/60">
            ×
          </button>
        </div>
        {m?.catch && <p className="mt-2 text-[12px] leading-relaxed text-ink/75">{m.catch}</p>}

        {item.shelf === "own" && (
          <div className="mt-4">
            <p className="text-xs text-ink/70">何巻まで持ってる?(1巻から続けて持っている最後の巻)</p>
            <div className="mt-1.5 flex items-center gap-2">
              <button type="button" aria-label="1巻減らす" onClick={() => onOwned(Math.max(0, (item.owned ?? 0) - 1))} className={pick(false)}>
                −
              </button>
              <span className="w-12 text-center text-[16px] font-bold tabular-nums">{item.owned ?? 0}</span>
              <button
                type="button"
                aria-label="1巻増やす"
                onClick={() => onOwned(Math.min(max, (item.owned ?? 0) + 1))}
                className={pick(false)}
              >
                +
              </button>
              {note?.total != null && <span className="text-xs text-ink/55">/ 既刊 {note.total}巻</span>}
            </div>
            {note && <p className="mt-1.5 text-[12px] font-semibold text-[var(--color-accent)]">{note.text}</p>}
            {note?.fixedEdition && (
              <p className="mt-1 text-[11px] text-ink/50">
                {item.edition}で登録=登録した時の巻数({note.total}巻)で比べています。新刊が出ても自動では増えません。
              </p>
            )}
            {nextVol && !lost && (
              <p className="mt-2 flex flex-wrap gap-2">
                {/* ★価格は書かない(静的な価格表示禁止)。検索リンクだけ */}
                <BuyLinks title={title} author={m?.authors[0]?.name} n={nextVol} label={`${nextVol}巻`} />
                <Link href={`/manga/${item.slug}`} prefetch={false} className="rounded-full border border-[var(--color-line)] px-3 py-1.5 text-xs text-ink/80">
                  作品頁の巻一覧へ
                </Link>
              </p>
            )}
          </div>
        )}

        <p className="mt-4 text-xs text-ink/70">棚を移す</p>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {SHELVES.map((s) => (
            <button key={s.id} type="button" aria-pressed={item.shelf === s.id} onClick={() => onMove(s.id)} className={pick(item.shelf === s.id)}>
              {s.label}
            </button>
          ))}
        </div>

        <div className="mt-4 flex items-center gap-2 border-t border-[var(--color-line)] pt-3">
          {!lost && (
            <Link href={`/manga/${item.slug}`} prefetch={false} className="text-xs text-ink/70 underline decoration-dotted underline-offset-2">
              作品頁を開く
            </Link>
          )}
          <button
            type="button"
            onClick={() => (confirm ? onRemove() : setConfirm(true))}
            className="ml-auto rounded-full border border-[var(--color-line)] px-3 py-1.5 text-xs text-ink/70"
          >
            {confirm ? "もう一度押すと取り出します" : "本棚から取り出す"}
          </button>
        </div>
      </div>
    </div>
  );
}

/** タブの並び(依頼書 C3 = もってる/ほしい/気になる)。選んだ棚は端末に覚える(本人だけの便利機能)。 */
const TAB_ORDER: ShelfId[] = ["own", "wish", "curious"];
const TAB_KEY = "mangal:shelf:tab";

/** 黒い展示棚。選んだ棚の作品を1段ずつ、段の下に棚板。 */
function Case({
  id,
  cards,
  readOnly,
  onMenu,
  onOwned,
  onBought,
  mode,
  onMode,
  sections,
  importBar,
  select,
}: {
  id: ShelfId;
  cards: CardData[];
  readOnly: boolean;
  onMenu: (key: string) => void;
  onOwned: (key: string, n: number) => void;
  onBought: (key: string) => void;
  /** 自動の仕切り(見本①)。 共有された棚を見ている時も使える */
  mode: DivideMode;
  onMode: (m: DivideMode) => void;
  /** 仕切った段(先頭に「取り込みで増えた本」の段が来ることがある) */
  sections: { id: string; label: string; isNew?: boolean; cards: CardData[] }[];
  /** 「11/17 の取り込みで 3作 増えました [確認した]」(見本②-5a)。 無ければ null */
  importBar: { text: string; onAck: () => void } | null;
  select: { has: (key: string) => boolean; toggle: (key: string) => void } | null;
}) {
  const def = SHELVES.find((s) => s.id === id)!;
  const row = (c: CardData) => {
    const k = itemKey(c.item);
    return (
      <Row
        key={k}
        d={c}
        readOnly={readOnly}
        onMenu={() => onMenu(k)}
        onOwned={(n) => onOwned(k, n)}
        onBought={() => onBought(k)}
        select={select ? { on: select.has(k), toggle: () => select.toggle(k) } : null}
      />
    );
  };
  return (
    <div className="shelf-c3-case" role="tabpanel" aria-label={def.label}>
      <p className="shelf-c3-casenote">{def.note}</p>
      {importBar && (
        <div className="shelf-newbar" role="status">
          <b>{importBar.text}</b>
          <button type="button" onClick={importBar.onAck}>
            確認した
          </button>
        </div>
      )}
      {cards.length > 1 && (
        <div className="shelf-chips" role="group" aria-label="仕切り">
          <span>仕切り</span>
          {DIVIDE_MODES.map((d) => (
            <button key={d.id} type="button" aria-pressed={mode === d.id} onClick={() => onMode(d.id)}>
              {d.label}
            </button>
          ))}
        </div>
      )}
      {cards.length === 0 ? (
        <p className="shelf-c3-empty">{readOnly ? "この棚は空です" : "作品頁の「しまう」から入れられます"}</p>
      ) : (
        <>
          {sections.map((sec) =>
            sec.label ? (
              <section key={sec.id} aria-label={sec.label}>
                <h3 className={`shelf-sec${sec.isNew ? " is-new" : ""}`}>
                  {sec.label} <small>{sec.cards.length}作</small>
                </h3>
                <ul className="shelf-c3-rows">{sec.cards.map(row)}</ul>
              </section>
            ) : (
              <ul key={sec.id} className="shelf-c3-rows">
                {sec.cards.map(row)}
              </ul>
            ),
          )}
          <p className="shelf-c3-pr">[PR] 店舗リンクにはアフィリエイト広告を含みます</p>
        </>
      )}
    </div>
  );
}

/** 日付「11/17」(端末の暦) */
const md = (t: number) => {
  const d = new Date(t);
  return `${d.getMonth() + 1}/${d.getDate()}`;
};

/** 端末の小さな控え(取り込みの印・バックアップの印・仕切り)。 保存できない環境は黙って無し */
function readLocal(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}
function writeLocal(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    /* 覚えられなくても棚は動く */
  }
}

export default function MyShelf({ genres }: { genres: GenreDef[] }) {
  const index = useMangaIndex({ withCatch: true });
  // ★この頁は索引が本文(書影・題名・巻数・状態)= 手すき待ちにせず全件を即要求
  useEffect(() => ensureFullIndex(), []);
  const full = index !== null && isFullIndexLoaded();
  const bySlug = useMemo(() => new Map((index ?? []).map((m) => [m.slug, m])), [index]);
  const genreName = useMemo(() => new Map(genres.map((g) => [g.key, g.name])), [genres]);

  const { items, ready, persisted, update } = useMyShelf();
  // 共有された棚(URL の #s= で開いた・貼って読んだ)。 kind = バックアップ / 旧URL / おすすめ(おすすめは「気になる」に入れるだけ)
  const [shared, setShared] = useState<{ items: ShelfItem[]; kind: "backup" | "v1" | "recommend" } | null>(null);
  const [menu, setMenu] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [confirmOverwrite, setConfirmOverwrite] = useState(false);
  // 転送を確かめ終えても見つからなかった slug(= 見つからなくなった作品)
  const [lost, setLost] = useState<Set<string>>(new Set());
  const tried = useRef(new Set<string>());
  const [tab, setTab] = useState<ShelfId>("own");
  // U1/U2 の後に出す札(取り消しつき)。 undo = 変える前の棚まるごと
  const [toast, setToast] = useState<{ text: string; undo: ShelfItem[] } | null>(null);
  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 6000);
    return () => window.clearTimeout(t);
  }, [toast]);

  // ── 2026-11-17 見本 ①自動の仕切り / ②-5a 取り込みで増えた本 / ③バックアップ / ④おすすめを選ぶ ──
  const [mode, setMode] = useState<DivideMode>("none");
  const [importMark, setImportMark] = useState<ImportMark | null>(null);
  const [backupMark, setBackupMark] = useState<BackupMark | null>(null);
  const [panel, setPanel] = useState<"backup" | "select" | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [backupCode, setBackupCode] = useState<string | null>(null);
  const [recCode, setRecCode] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [paste, setPaste] = useState("");
  const [pasteError, setPasteError] = useState<string | null>(null);
  const [origin, setOrigin] = useState("");
  const [canShare, setCanShare] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  // 出版社の名前は仕切りを「出版社」にした時だけ取りに行く(レールと同じ静的JSON・1回だけ)
  const publishers = useRailMasters(mode === "publisher").publishers;
  const publisherName = useMemo(() => new Map(publishers.map((p) => [p.key, p.name])), [publishers]);

  // 選んだタブ・仕切り・印は端末に覚える(水和後に読む。保存できない環境は既定のまま)
  useEffect(() => {
    const v = readLocal(TAB_KEY);
    if (v === "own" || v === "wish" || v === "curious") setTab(v);
    const d = readLocal(DIVIDE_KEY);
    if (isDivideMode(d)) setMode(d);
    setImportMark(parseMark<ImportMark>(readLocal(IMPORT_MARK_KEY), ["at", "n", "ack"]));
    setBackupMark(parseMark<BackupMark>(readLocal(BACKUP_MARK_KEY), ["at", "sig"]));
    setOrigin(window.location.origin);
    setCanShare(typeof navigator.share === "function");
  }, []);
  const chooseTab = (id: ShelfId) => {
    setTab(id);
    writeLocal(TAB_KEY, id);
  };
  const chooseMode = (m: DivideMode) => {
    setMode(m);
    writeLocal(DIVIDE_KEY, m);
  };
  const saveImportMark = (m: ImportMark | null) => {
    setImportMark(m);
    writeLocal(IMPORT_MARK_KEY, m ? JSON.stringify(m) : null);
  };

  // 棚のURL(#s=…)で開かれたら、まず「見るだけ」で出す(取り込むかは本人が選ぶ)。 旧 v1. も読む
  useEffect(() => {
    if (!window.location.hash) return;
    readShelfCode(window.location.hash).then((r) => {
      if (r.ok) {
        setShared({ items: r.items, kind: r.kind });
        if (r.kind === "recommend") setTab("curious"); // おすすめは全部「気になる」に並ぶ(選んだタブの記憶は変えない)
      } else if (r.reason === "broken")
        setMessage("開いたURLの棚の文字列が欠けていて読めませんでした。送ってもらったURLを全部コピーし直してください。");
    });
  }, []);

  // ★slug の解決: 全件が揃ってから(先頭100件だけで「無い」と判断しない)。索引に無い slug だけ、
  //   作品頁の 301 転送先を1件ずつ確かめて保存値を書き換える。それでも無ければ「見つからなくなりました」。
  //   ★棚が変わっても確かめかけた分は打ち切らない(打ち切ると「確認済み・結果なし」で宙に浮く)。二重確認は tried で防ぐ。
  useEffect(() => {
    if (!full || !ready) return;
    const todo = items.filter((x) => !bySlug.has(x.slug) && !tried.current.has(x.slug));
    for (const x of todo) tried.current.add(x.slug);
    (async () => {
      for (const x of todo) {
        const to = await resolveMovedSlug(x.slug, fetchFinal);
        if (to) update((s) => renameSlug(s, x.slug, to));
        else setLost((prev) => new Set(prev).add(x.slug));
      }
    })();
  }, [full, ready, items, bySlug, update]);

  // 棚のURLで取り込んだ作品は題名・書影の控えを持たない = 索引から埋めておく(見つからなくなった時の表示用)
  useEffect(() => {
    if (!ready || !index) return;
    // ★索引側にも書影が無い作品は埋めようが無い = 「埋められる時だけ」書く(書き続けの輪を作らない)
    const fillable = (x: ShelfItem) => {
      const m = bySlug.get(x.slug);
      return !!m && ((!x.title && !!m.title) || (!x.cover && !!m.cover));
    };
    if (!items.some(fillable)) return;
    update((s) =>
      s.map((x) => {
        if (!fillable(x)) return x;
        const m = bySlug.get(x.slug)!;
        return { ...x, title: x.title || m.title, cover: x.cover ?? m.cover };
      }),
    );
  }, [ready, index, items, bySlug, update]);

  const viewing = shared !== null;
  const shown = viewing ? shared.items : items;

  // ★版ごとにしまった1冊(版ラベル付き)は、その版の今の巻数と1巻の書影を巻の書影データ(lib/volCovers)から引く
  //   (2026-10-31 本棚 A+1)。 引けるまでは登録時点の巻数・索引の書影で出す(引けない = 版の名前が変わった等もそのまま)。
  const [edFacts, setEdFacts] = useState<Map<string, EditionFacts>>(new Map());
  const edAsked = useRef(new Set<string>());
  useEffect(() => {
    const todo = shown.filter((x) => x.edition && !edAsked.current.has(itemKey(x)));
    if (!todo.length) return;
    for (const x of todo) edAsked.current.add(itemKey(x)); // 1冊につき1回(書影データは1本ずつ端末のメモリに残る)
    Promise.all(todo.map(async (x) => [itemKey(x), await loadEditionFacts(x.slug, x.edition!)] as const)).then((got) => {
      if (!got.some(([, f]) => f)) return;
      setEdFacts((prev) => {
        const next = new Map(prev);
        for (const [k, f] of got) if (f) next.set(k, f);
        return next;
      });
    });
  }, [shown]);
  const liveOf = (x: ShelfItem) => (x.edition ? edFacts.get(itemKey(x)) : undefined);

  // ★増えた本 = 最後の取り込みの時刻と addedAt が同じ本(本ごとの欄は増やさない)。 共有された棚を見ている間は付けない
  const importedAt = !viewing && importMark ? importMark.at : null;
  const isNewItem = (x: ShelfItem) => importedAt !== null && !importMark!.ack && x.addedAt === importedAt;

  const factsOf = (slug: string): IndexFacts | null => {
    const m = bySlug.get(slug);
    return m ? { max_edition_volumes: m.max_edition_volumes, status: m.status } : null;
  };
  const cardsOf = (id: ShelfId): CardData[] => {
    const cards = shown
      .filter((x) => x.shelf === id)
      .map((item) => {
        const m = bySlug.get(item.slug);
        const live = liveOf(item);
        return {
          item,
          m,
          lost: !m && (viewing ? full : lost.has(item.slug)),
          note: id === "own" ? ownedNote(item, factsOf(item.slug), live?.total) : null,
          live,
          // 日付は全部の本に(見本②-5a)。 共有された棚(見るだけ)には出さない = 受け取った時刻しか無いので
          dateLabel: viewing ? "" : item.addedAt === importedAt ? `${md(item.addedAt)} 取り込み` : `${md(item.addedAt)} から棚に`,
          isNew: isNewItem(item),
        };
      });
    const rank = (c: CardData) => (c.note && (c.note.kind === "behind" || c.note.kind === "complete-behind") ? 0 : 1);
    cards.sort((a, b) => rank(a) - rank(b) || b.item.updatedAt - a.item.updatedAt);
    // 同じ作品の別の版は隣どうしに(先に来た版の位置へ寄せる・版どうしの順は上の並びのまま)
    const groups = new Map<string, CardData[]>();
    for (const c of cards) {
      const g = groups.get(c.item.slug);
      if (g) g.push(c);
      else groups.set(c.item.slug, [c]);
    }
    return [...groups.values()].flat();
  };
  /** 仕切った段。 増えた本があれば「11/17 に取り込み」を先頭に、残りを仕切る(仕切りなし = 「前から棚にある本」) */
  const sectionsOf = (cards: CardData[]) => {
    const fresh = cards.filter((c) => c.isNew);
    const rest = fresh.length ? cards.filter((c) => !c.isNew) : cards;
    const entries: DivideEntry<CardData>[] = rest.map((c) => ({
      value: c,
      noteKind: c.note?.kind ?? null,
      facts: c.m
        ? {
            status: c.m.status,
            genres: c.m.genres,
            author: c.m.authors[0] ? { name: c.m.authors[0].name, kana: c.m.authors[0].kana } : null,
            publisher: c.m.publisher,
            titleKana: c.m.title_kana,
          }
        : null,
    }));
    const divided = divide(entries, mode, { genre: (k) => genreName.get(k), publisher: (k) => publisherName.get(k) })
      .map((sec) => ({
        id: sec.id,
        label: sec.label || (fresh.length ? "前から棚にある本" : ""),
        cards: sec.entries.map((e) => e.value),
      }))
      .filter((sec) => sec.cards.length);
    if (!fresh.length) return divided;
    return [{ id: "new", label: `${md(importedAt!)} に取り込み`, isNew: true, cards: fresh }, ...divided];
  };

  const titleOf = (slug: string) => bySlug.get(slug)?.title || items.find((x) => x.slug === slug)?.title || slug;
  const slugOfKey = (key: string) => items.find((x) => itemKey(x) === key)?.slug ?? key;
  // U1: 書影欄の「ここ(N巻)まで持ってる」。 key = itemKey(版ごとにしまった1冊を区別する)
  const ownTo = (key: string, n: number) => {
    const before = items;
    update((x) => setOwned(x, key, n));
    setToast({ text: `${titleOf(slugOfKey(key))} を ${n}巻まで持ってる にしました`, undo: before });
  };
  // U2: ほしい・気になる →「もってる・1巻まで」
  const boughtFirst = (key: string) => {
    const before = items;
    update((x) => setOwned(moveItem(x, key, "own"), key, 1));
    setToast({ text: `${titleOf(slugOfKey(key))} を もってる(1巻まで)へ移しました`, undo: before });
  };

  const leaveShared = (msg?: string) => {
    setShared(null);
    setConfirmOverwrite(false);
    try {
      window.history.replaceState(window.history.state, "", window.location.pathname);
    } catch {
      /* URL を戻せなくても棚は動く */
    }
    if (msg) setMessage(msg);
  };
  /** 取り込む。 合流 = 手元に無かった本だけ「増えた本」の印(見本②-5a)。 上書き = 印は付けない(全部が新しくなるので) */
  const takeIn = (incoming: ShelfItem[], how: ImportMode): number => {
    const now = Date.now();
    let added = 0;
    update((s) => {
      if (how === "overwrite") return importShelf(s, incoming, "overwrite");
      const r = mergeWithMark(s, incoming, (a, b) => importShelf(a, b, "merge"), itemKey, now);
      added = r.added;
      return r.items;
    });
    if (how === "merge" && added > 0) saveImportMark({ at: now, n: added, ack: false });
    return added;
  };
  const doImport = (how: ImportMode) => {
    if (!shared) return;
    if (how === "overwrite" && items.length > 0 && !confirmOverwrite) {
      setConfirmOverwrite(true);
      return;
    }
    const n = shared.items.length;
    // ★おすすめは「手元に無い本だけ」入れる(手元の本の棚・巻数を「気になる」で上書きしない)
    const have = new Set(items.map(itemKey));
    const added = takeIn(shared.kind === "recommend" ? shared.items.filter((x) => !have.has(itemKey(x))) : shared.items, how);
    leaveShared(
      how === "overwrite"
        ? `棚を持ってきた${n}作で置き換えました`
        : shared.kind === "recommend"
          ? `おすすめ${n}作のうち${added}作を「おすすめ！」に入れました`
          : `${n}作を自分の棚に合流しました(新しく増えたのは${added}作)`,
    );
  };

  // ── ③ バックアップ: 棚が変わるたびに今の文字列を作っておく(押した時に待たせない) ──
  useEffect(() => {
    if (!ready || viewing) return;
    if (!items.length) {
      setBackupCode(null);
      return;
    }
    let alive = true;
    encodeShelfCode(items, "backup").then((c) => {
      if (alive) setBackupCode(c);
    });
    return () => {
      alive = false;
    };
  }, [ready, viewing, items]);
  const backupText = backupCode ? `${backupHeader(items)}\n${backupCode}` : "";
  const backupStale = !!backupCode && (!backupMark || backupMark.sig !== codeSig(backupCode));
  const markBackedUp = () => {
    if (!backupCode) return;
    const m = { at: Date.now(), sig: codeSig(backupCode) };
    setBackupMark(m);
    writeLocal(BACKUP_MARK_KEY, JSON.stringify(m));
  };
  const copyText = async (text: string, tag: string, after?: () => void) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(tag);
      after?.();
    } catch {
      setCopied(null);
    }
  };
  const shareText = async (text: string, after?: () => void) => {
    if (typeof navigator.share !== "function") return;
    try {
      await navigator.share({ title: "本棚", text });
      after?.();
    } catch {
      /* キャンセルは無視 */
    }
  };
  const saveTxt = () => {
    if (!backupText) return;
    const d = new Date();
    const name = `mangal-shelf-${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}.txt`;
    const url = URL.createObjectURL(new Blob([backupText + "\n"], { type: "text/plain;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 2000);
    markBackedUp();
  };
  const readInput = async (text: string) => {
    const r = await readShelfCode(text);
    if (!r.ok) {
      setPasteError(
        r.reason === "broken"
          ? "文字列が欠けているか、途中で変わっています。保存した時の文字列を全部コピーし直してください。"
          : "読めませんでした。バックアップの文字列・棚のURL・おすすめのURLのどれかを貼ってください。",
      );
      return;
    }
    setPasteError(null);
    setPaste("");
    setPanel(null);
    setShared({ items: r.items, kind: r.kind });
    if (r.kind === "recommend") setTab("curious");
    window.scrollTo({ top: 0 });
  };
  const readFile = async (f: File | undefined) => {
    if (!f) return;
    try {
      await readInput(await f.text());
    } catch {
      setPasteError("ファイルを読めませんでした。");
    }
  };

  // ── ④ おすすめを選ぶ ──
  const togglePick = (key: string) =>
    setPicked((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  const pickedItems = useMemo(() => items.filter((x) => picked.has(itemKey(x))), [items, picked]);
  useEffect(() => {
    if (panel !== "select" || !pickedItems.length) {
      setRecCode(null);
      return;
    }
    let alive = true;
    encodeShelfCode(pickedItems, "recommend").then((c) => {
      if (alive) setRecCode(c);
    });
    return () => {
      alive = false;
    };
  }, [panel, pickedItems]);
  const recUrl = recCode ? shelfCodeUrl(origin, recCode) : "";
  // ★送り方はURLだけ(2026-11-23 ユーザ裁定: 題名を並べる「文章」方式は使い勝手が悪いので廃止)
  const recOut = recUrl;
  const togglePanel = (p: "backup" | "select") => {
    setPanel((cur) => (cur === p ? null : p));
    setCopied(null);
    if (p === "select") setPicked(new Set());
  };

  const menuCard = menu ? cardsOf(shown.find((x) => itemKey(x) === menu)?.shelf ?? "own").find((c) => itemKey(c.item) === menu) : undefined;
  const counts = countByShelf(shown);
  const tabCards = cardsOf(tab);
  const newItems = !viewing && importMark && !importMark.ack ? items.filter(isNewItem) : [];
  const newCount = newItems.length;
  const newWhere = TAB_ORDER.map((id) => [id, newItems.filter((x) => x.shelf === id).length] as const)
    .filter(([, n]) => n > 0)
    .map(([id, n]) => `${SHELVES.find((s) => s.id === id)!.label} ${n}`)
    .join("・");
  const selecting = panel === "select" && !viewing;
  const backupOpen = !viewing && (panel === "backup" || !persisted);

  if (!ready) return <p className="mt-8 text-center text-sm text-ink/55">本棚を開いています…</p>;

  return (
    <div>
      {viewing && (
        <div className="mt-4 border-2 border-[var(--color-accent)] p-3 text-[13px]" role="region" aria-label="共有された棚">
          {shared.kind === "recommend" ? (
            <>
              <p className="font-bold">おすすめの漫画が届きました({shared.items.length}作・見るだけ)</p>
              <p className="mt-0.5 text-[11.5px] text-ink/60">「おすすめ！に入れる」を押すと、自分の棚の「おすすめ！」に新しく増えた本として印が付きます。</p>
              <div className="mt-2 flex flex-wrap gap-2">
                <button type="button" onClick={() => doImport("merge")} className="rounded-full border-2 border-[var(--color-accent)] px-3 py-1.5 text-xs font-bold text-[var(--color-accent)]">
                  おすすめ！に入れる
                </button>
                <button type="button" onClick={() => leaveShared()} className="rounded-full border border-[var(--color-line)] px-3 py-1.5 text-xs text-ink/70">
                  自分の棚に戻る
                </button>
              </div>
            </>
          ) : (
            <>
              <p className="font-bold">共有された棚を見ています(見るだけ・自分の棚はそのまま)</p>
              <p className="mt-0.5 text-[11.5px] text-ink/60">
                もってる {counts.own}・おすすめ！ {counts.curious}・ほしい {counts.wish}(計 {shared.items.length}作)
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <button type="button" onClick={() => doImport("merge")} className="rounded-full border-2 border-[var(--color-accent)] px-3 py-1.5 text-xs font-bold text-[var(--color-accent)]">
                  自分の棚に合流
                </button>
                <button type="button" onClick={() => doImport("overwrite")} className="rounded-full border border-[var(--color-line)] px-3 py-1.5 text-xs text-ink/80">
                  {confirmOverwrite ? `今の棚(${items.length}作)を消して置き換える=もう一度` : "上書きして取り込む"}
                </button>
                <button type="button" onClick={() => leaveShared()} className="rounded-full border border-[var(--color-line)] px-3 py-1.5 text-xs text-ink/70">
                  自分の棚に戻る
                </button>
              </div>
            </>
          )}
        </div>
      )}
      {message && (
        <p className="mt-4 text-[12px] font-semibold text-[var(--color-accent)]" role="status">
          {message}
        </p>
      )}
      {!persisted && (
        <p className="mt-4 text-[11.5px] text-ink/60">
          この端末(ブラウザ)では保存できないため、頁を閉じると棚は消えます。下の「💾 棚のバックアップ」で持ち出せます。
        </p>
      )}
      {!full && <p className="mt-3 text-[11px] text-ink/45">作品データを読み込み中… 巻数と続きの巻は揃い次第出ます</p>}

      <Plaque stats={plaqueStats(shown, factsOf, (x) => liveOf(x)?.total)} />
      {!viewing && (
        <div className="shelf-tools">
          <button type="button" aria-pressed={selecting} onClick={() => togglePanel("select")} disabled={!items.length}>
            ⭐ おすすめを選ぶ
          </button>
          <button type="button" aria-pressed={backupOpen} onClick={() => togglePanel("backup")}>
            💾 バックアップ
            {backupStale && <i aria-label="取り直しをおすすめ" />}
          </button>
        </div>
      )}

      {backupOpen && (
        <section className="shelf-backup" aria-label="棚のバックアップ">
          <h2>💾 棚のバックアップ</h2>
          {backupStale && (
            <p className="shelf-backup-warn">
              {backupMark
                ? `前回のバックアップ(${md(backupMark.at)})のあと、棚が変わりました。取り直しておくと安心です。`
                : "まだバックアップを取っていません。下の文字列を保存しておくと、棚が消えても戻せます。"}
            </p>
          )}
          {backupCode ? (
            <>
              <pre className="shelf-code" aria-label="バックアップの文字列">
                <b>{backupHeader(items)}</b>
                {"\n"}
                {backupCode}
              </pre>
              <div className="shelf-btns">
                <button type="button" className="is-solid" onClick={() => copyText(backupText, "backup", markBackedUp)}>
                  {copied === "backup" ? "コピーしました" : "コピー"}
                </button>
                <button type="button" onClick={saveTxt}>
                  .txt で保存
                </button>
                {canShare && (
                  <button type="button" onClick={() => shareText(backupText, markBackedUp)}>
                    共有…
                  </button>
                )}
                <button type="button" onClick={() => copyText(shelfCodeUrl(origin, backupCode), "backup-url", markBackedUp)}>
                  {copied === "backup-url" ? "コピーしました" : "URLでコピー"}
                </button>
              </div>
              <p className="shelf-backup-note">
                {"メモ帳・自分宛てのメール/LINE、または .txt ファイルで残してください(iPhone は「ファイル」、Android と PC は「ダウンロード」に入ります)。文字は英数字だけなので、どの端末でも化けません。"}
                <b>持っている巻数も入っています</b>
                {"(人に送る時は「⭐ おすすめを選ぶ」を使ってください)。"}
              </p>
            </>
          ) : (
            <p className="shelf-backup-note">棚が空です。作品頁の「しまう」で入れると、ここでバックアップを取れます。</p>
          )}
          <h3>バックアップから戻す</h3>
          <div className="shelf-restore">
            <textarea
              value={paste}
              onChange={(e) => setPaste(e.target.value)}
              placeholder="ここに貼る(文字列・URL・.txt の中身どれでも)"
              aria-label="バックアップの文字列を貼る"
              rows={3}
              className="shelf-paste"
            />
            <button type="button" onClick={() => readInput(paste)} disabled={!paste.trim()}>
              読む
            </button>
          </div>
          <div className="shelf-btns">
            <button type="button" onClick={() => fileRef.current?.click()}>
              .txt ファイルを選ぶ
            </button>
            <input ref={fileRef} type="file" accept=".txt,text/plain" hidden onChange={(e) => readFile(e.target.files?.[0])} />
          </div>
          {pasteError && <p className="shelf-backup-warn">{pasteError}</p>}
          <p className="shelf-backup-note">{"読むとまず「見るだけ」で並び、「合流(今の棚に足す)/上書き」を選べます。前の形式(v1. や棚のURL)もそのまま読めます。"}</p>
        </section>
      )}

      {selecting && (
        <div className="shelf-selbar" role="status">
          <span>
            ⭐ おすすめを選ぶ <b>{picked.size}作</b> 選択中
          </span>
          <button type="button" onClick={() => setPicked(new Set(items.map(itemKey)))}>
            全部
          </button>
          <button type="button" onClick={() => togglePanel("select")}>
            やめる
          </button>
        </div>
      )}

      <div className="shelf-c3-tabs" role="tablist" aria-label="棚">
        {TAB_ORDER.map((id) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => chooseTab(id)} className="shelf-c3-tab">
            {SHELVES.find((s) => s.id === id)!.label}
            <span>{counts[id]}</span>
          </button>
        ))}
      </div>
      <Case
        id={tab}
        cards={tabCards}
        readOnly={viewing}
        onMenu={setMenu}
        onOwned={ownTo}
        onBought={boughtFirst}
        mode={mode}
        onMode={chooseMode}
        sections={sectionsOf(tabCards)}
        importBar={
          newCount > 0
            ? {
                text: `${md(importMark!.at)} の取り込みで ${newCount}作 増えました(${newWhere})`,
                onAck: () => saveImportMark({ ...importMark!, ack: true }),
              }
            : null
        }
        select={selecting ? { has: (k) => picked.has(k), toggle: togglePick } : null}
      />
      {toast && (
        <div className="shelf-toast" role="status">
          <span>{toast.text}</span>
          <button
            type="button"
            onClick={() => {
              const undo = toast.undo;
              update(() => undo);
              setToast(null);
            }}
          >
            取り消す
          </button>
        </div>
      )}

      {/* 下から出る送り方の画面で最後の段が隠れないように */}
      {selecting && picked.size > 0 && <div aria-hidden="true" style={{ height: 340 }} />}
      {selecting && picked.size > 0 && (
        <div className="shelf-send" role="dialog" aria-label="おすすめを送る">
          <p className="shelf-send-h">{picked.size}作を送る(持っている巻数・日付は送りません)</p>
          <pre className="shelf-code is-text">{recOut || "作っています…"}</pre>
          <div className="shelf-btns">
            <button type="button" className="is-solid" disabled={!recOut} onClick={() => copyText(recOut, "rec")}>
              {copied === "rec" ? "コピーしました" : "コピー"}
            </button>
            {canShare && (
              <button type="button" disabled={!recOut} onClick={() => shareText(recOut)}>
                共有…(LINE など)
              </button>
            )}
          </div>
          <p className="shelf-backup-note">
            {"相手は開くと「見るだけ」で並び、「おすすめ！に入れる」で自分の棚の「おすすめ！」に入れられます。"}
          </p>
        </div>
      )}

      {menuCard && !viewing && !selecting && (
        <Sheet
          d={menuCard}
          genreName={genreName}
          onClose={() => setMenu(null)}
          onMove={(s) => update((x) => moveItem(x, itemKey(menuCard.item), s))}
          onOwned={(n) => update((x) => setOwned(x, itemKey(menuCard.item), n))}
          onRemove={() => {
            update((x) => removeItem(x, itemKey(menuCard.item)));
            setMenu(null);
          }}
        />
      )}
    </div>
  );
}
