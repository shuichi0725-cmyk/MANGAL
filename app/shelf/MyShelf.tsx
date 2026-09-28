"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { amazonSearchUrl } from "@/lib/amazon";
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
  moveItem,
  ownedNote,
  plaqueStats,
  removeItem,
  renameSlug,
  resolveMovedSlug,
  setOwned,
  shelfShareUrl,
  volumeTiles,
} from "@/lib/myShelf";
import type { MangaListItem } from "@/lib/schema";
import { ensureFullIndex, isFullIndexLoaded, useMangaIndex } from "@/lib/useMangaIndex";
import { useMyShelf } from "@/lib/useMyShelf";

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
};

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

/** 番号タイル(もってるの段だけ)。10巻で1行、41巻以上は所持の前半を帯に畳む(lib/myShelf volumeTiles)。 */
function Tiles({ owned, total }: { owned: number; total: number | null }) {
  const t = volumeTiles(owned, total);
  if (!t) return null;
  const missing = t.tiles.filter((x) => x.state === "missing").map((x) => x.n);
  const label =
    (owned > 0 ? `1〜${owned}巻 所持` : "1巻はまだ") +
    (missing.length ? `・${missing[0]}〜${missing[missing.length - 1]}巻 未所持` : "");
  return (
    // 読み上げは1文にまとめる(タイル1枚ずつ読ませない)
    <span className="shelf-c3-tiles" role="img" aria-label={label}>
      {t.band && (
        <span className="shelf-c3-band">
          {t.band.from}〜{t.band.to}巻 所持({t.band.count}冊)
        </span>
      )}
      {t.tiles.map((x) => (
        <span key={x.n} className={`shelf-c3-tile is-${x.state}`}>
          {x.n}
        </span>
      ))}
    </span>
  );
}

/** 棚の1段 = 1作品。左に1巻の書影、右に題名・所持状況・番号タイル(ほしい/気になるは巻数と状態+キャッチ)。 */
function Row({ d, onMenu, readOnly }: { d: CardData; onMenu: () => void; readOnly: boolean }) {
  const { item, m, lost, note } = d;
  const title = m?.title ?? (item.title || item.slug);
  const cover = m?.cover ?? item.cover;
  const press = useLongPress(onMenu);
  const alert = note && (note.kind === "behind" || note.kind === "complete-behind");
  const body = (
    <>
      <Cover src={cover} title={title} />
      <span className="shelf-c3-body">
        <span className="shelf-c3-title">{title}</span>
        {lost ? (
          <span className="shelf-c3-sub">この作品は見つからなくなりました</span>
        ) : note ? (
          <>
            <span className={`shelf-c3-note${alert ? " is-alert" : ""}`}>{note.text}</span>
            <Tiles owned={item.owned ?? 0} total={note.total} />
          </>
        ) : (
          m && (
            <>
              <span className="shelf-c3-sub">
                {m.max_edition_volumes ? `全${m.max_edition_volumes}巻・` : ""}
                {STATUS_LABEL[m.status] ?? ""}
              </span>
              {m.catch && <span className="shelf-c3-catch">{m.catch}</span>}
            </>
          )
        )}
      </span>
    </>
  );
  return (
    <li className="shelf-c3-row">
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
    </li>
  );
}

/** 真鍮の銘板 = 集計3つ(lib/myShelf plaqueStats)。 */
function Plaque({ stats }: { stats: PlaqueStats }) {
  return (
    <div className="shelf-c3-plaque" role="group" aria-label="集計">
      <div>
        <b>{stats.ownedVolumes.toLocaleString()}</b>
        <span>もってる冊数</span>
      </div>
      <div>
        <b>{stats.nextVolumes.toLocaleString()}</b>
        <span>出ている続きの巻</span>
      </div>
      <div>
        <b>{stats.completeWorks.toLocaleString()}</b>
        <span>全巻そろった作品</span>
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
  const tag = process.env.NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG ?? "";
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
                <a
                  href={amazonSearchUrl(`${title} ${nextVol}`, tag)}
                  target="_blank"
                  rel="noopener nofollow sponsored"
                  className="rounded-full border border-[var(--color-line)] px-3 py-1.5 text-xs text-ink/80"
                >
                  📖 {nextVol}巻をアマゾンで探す
                </a>
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
}: {
  id: ShelfId;
  cards: CardData[];
  readOnly: boolean;
  onMenu: (slug: string) => void;
}) {
  const def = SHELVES.find((s) => s.id === id)!;
  return (
    <div className="shelf-c3-case" role="tabpanel" aria-label={def.label}>
      <p className="shelf-c3-casenote">{def.note}</p>
      {cards.length === 0 ? (
        <p className="shelf-c3-empty">{readOnly ? "この棚は空です" : "作品頁の「しまう」から入れられます"}</p>
      ) : (
        <ul className="shelf-c3-rows">
          {cards.map((c) => (
            <Row key={c.item.slug} d={c} readOnly={readOnly} onMenu={() => onMenu(c.item.slug)} />
          ))}
        </ul>
      )}
    </div>
  );
}

export default function MyShelf({ genres }: { genres: GenreDef[] }) {
  const index = useMangaIndex({ withCatch: true });
  // ★この頁は索引が本文(書影・題名・巻数・状態)= 手すき待ちにせず全件を即要求
  useEffect(() => ensureFullIndex(), []);
  const full = index !== null && isFullIndexLoaded();
  const bySlug = useMemo(() => new Map((index ?? []).map((m) => [m.slug, m])), [index]);
  const genreName = useMemo(() => new Map(genres.map((g) => [g.key, g.name])), [genres]);

  const { items, ready, persisted, update } = useMyShelf();
  const [shared, setShared] = useState<ShelfItem[] | null>(null);
  const [menu, setMenu] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [confirmOverwrite, setConfirmOverwrite] = useState(false);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [paste, setPaste] = useState("");
  const [pasteError, setPasteError] = useState(false);
  // 転送を確かめ終えても見つからなかった slug(= 見つからなくなった作品)
  const [lost, setLost] = useState<Set<string>>(new Set());
  const tried = useRef(new Set<string>());
  const [tab, setTab] = useState<ShelfId>("own");

  // 選んだタブは端末に覚える(水和後に読む。保存できない環境は既定の「もってる」のまま)
  useEffect(() => {
    try {
      const v = window.localStorage.getItem(TAB_KEY);
      if (v === "own" || v === "wish" || v === "curious") setTab(v);
    } catch {
      /* 既定のまま */
    }
  }, []);
  const chooseTab = (id: ShelfId) => {
    setTab(id);
    try {
      window.localStorage.setItem(TAB_KEY, id);
    } catch {
      /* 覚えられなくても切り替えは効く */
    }
  };

  // 棚のURL(#s=…)で開かれたら、まず「見るだけ」で出す(取り込むかは本人が選ぶ)
  useEffect(() => {
    const got = decodeShelf(window.location.hash);
    if (got) setShared(got);
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
  const shown = viewing ? shared : items;
  const factsOf = (slug: string): IndexFacts | null => {
    const m = bySlug.get(slug);
    return m ? { max_edition_volumes: m.max_edition_volumes, status: m.status } : null;
  };
  const cardsOf = (id: ShelfId): CardData[] => {
    const cards = shown
      .filter((x) => x.shelf === id)
      .map((item) => {
        const m = bySlug.get(item.slug);
        return {
          item,
          m,
          lost: !m && (viewing ? full : lost.has(item.slug)),
          note: id === "own" ? ownedNote(item, factsOf(item.slug)) : null,
        };
      });
    const rank = (c: CardData) => (c.note && (c.note.kind === "behind" || c.note.kind === "complete-behind") ? 0 : 1);
    return cards.sort((a, b) => rank(a) - rank(b) || b.item.updatedAt - a.item.updatedAt);
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
  const doImport = (mode: ImportMode) => {
    if (!shared) return;
    if (mode === "overwrite" && items.length > 0 && !confirmOverwrite) {
      setConfirmOverwrite(true);
      return;
    }
    const n = shared.length;
    update((s) => importShelf(s, shared, mode));
    leaveShared(mode === "merge" ? `${n}作を自分の棚に合流しました` : `棚を持ってきた${n}作で置き換えました`);
  };

  const makeUrl = () => {
    setShareUrl(shelfShareUrl(window.location.origin, items));
    setCopied(false);
  };
  const copyUrl = async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };
  const shareNative = async () => {
    if (!shareUrl || typeof navigator.share !== "function") return;
    try {
      await navigator.share({ title: "マイ本棚", url: shareUrl });
    } catch {
      /* キャンセルは無視 */
    }
  };
  const readPaste = () => {
    const got = decodeShelf(paste);
    if (!got) {
      setPasteError(true);
      return;
    }
    setPasteError(false);
    setPaste("");
    setShared(got);
    window.scrollTo({ top: 0 });
  };

  const menuCard = menu ? cardsOf(shown.find((x) => x.slug === menu)?.shelf ?? "own").find((c) => c.item.slug === menu) : undefined;
  const counts = countByShelf(shown);

  if (!ready) return <p className="mt-8 text-center text-sm text-ink/55">本棚を開いています…</p>;

  return (
    <div>
      {viewing && (
        <div className="mt-4 border-2 border-[var(--color-accent)] p-3 text-[13px]" role="region" aria-label="共有された棚">
          <p className="font-bold">共有された棚を見ています(見るだけ・自分の棚はそのまま)</p>
          <p className="mt-0.5 text-[11.5px] text-ink/60">
            もってる {counts.own}・気になる {counts.curious}・ほしい {counts.wish}(計 {shared.length}作)
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
        </div>
      )}
      {message && (
        <p className="mt-4 text-[12px] font-semibold text-[var(--color-accent)]" role="status">
          {message}
        </p>
      )}
      {!persisted && (
        <p className="mt-4 text-[11.5px] text-ink/60">
          この端末(ブラウザ)では保存できないため、頁を閉じると棚は消えます。下の「棚のURL」で持ち出せます。
        </p>
      )}
      {!full && <p className="mt-3 text-[11px] text-ink/45">作品データを読み込み中… 巻数と続きの巻は揃い次第出ます</p>}

      <Plaque stats={plaqueStats(shown, factsOf)} />
      <div className="shelf-c3-tabs" role="tablist" aria-label="棚">
        {TAB_ORDER.map((id) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => chooseTab(id)} className="shelf-c3-tab">
            {SHELVES.find((s) => s.id === id)!.label}
            <span>{counts[id]}</span>
          </button>
        ))}
      </div>
      <Case id={tab} cards={cardsOf(tab)} readOnly={viewing} onMenu={setMenu} />


      {!viewing && (
        <section className="mt-10 border-t border-[var(--color-line)] pt-5 text-[12.5px]">
          <h2 className="text-[14px] font-bold">棚をURLで保存・復元する</h2>
          {/* ★日本語の文は1行に書く(JSX は改行を空白1つにする=「を メモ帳」のような空白が出る) */}
          <p className="mt-1 text-[11.5px] leading-relaxed text-ink/60">
            {"この本棚は、この端末(ブラウザ)の中だけにあります。「棚のURLを作る」で出るURL(文字列)をメモ帳・メールの下書き・自分宛てのLINEなどに"}
            <b>保存しておけば</b>
            {"、棚が消えても(Safari は7日開かないと消えることがあります)・機種変更しても、そのURLを開くか下の欄に貼るだけで"}
            <b>元の棚に戻せます</b>。
          </p>
          <p className="mt-1 text-[11.5px] leading-relaxed text-ink/60">
            {"人に見せる時もこのURLを送ってください(開いた側で「合流/上書き/見るだけ」を選べます)。URL の「#」より後ろはサーバーに送られません。"}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button type="button" onClick={makeUrl} disabled={!items.length} className="rounded-full border-2 border-[var(--color-accent)] px-3 py-1.5 text-xs font-bold text-[var(--color-accent)] disabled:opacity-40">
              棚のURLを作る
            </button>
            {shareUrl && (
              <>
                <button type="button" onClick={copyUrl} className="rounded-full border border-[var(--color-line)] px-3 py-1.5 text-xs">
                  {copied ? "コピーしました" : "コピー"}
                </button>
                {typeof navigator !== "undefined" && typeof navigator.share === "function" && (
                  <button type="button" onClick={shareNative} className="rounded-full border border-[var(--color-line)] px-3 py-1.5 text-xs">
                    共有
                  </button>
                )}
              </>
            )}
          </div>
          {shareUrl && (
            <input
              readOnly
              value={shareUrl}
              onFocus={(e) => e.currentTarget.select()}
              aria-label="棚のURL"
              className="mt-2 w-full rounded border border-[var(--color-line)] bg-[var(--color-surface)] px-2 py-1.5 font-mono text-[11px] text-ink/80"
            />
          )}
          {shareUrl && (
            <p className="mt-1 text-[11px] leading-relaxed text-ink/55">
              ↑ このURLを保存しておけば、いつでもこの棚に戻せます。作った時点の中身なので、棚を変えたら作り直して保存し直してください。
            </p>
          )}
          <h3 className="mt-5 text-[13px] font-bold">保存しておいたURL(文字列)から復元する</h3>
          <div className="mt-2 flex gap-2">
            <input
              value={paste}
              onChange={(e) => setPaste(e.target.value)}
              placeholder="https://…/shelf#s=v1.… または v1.…"
              aria-label="棚のURLを貼る"
              className="min-w-0 flex-1 rounded border border-[var(--color-line)] bg-[var(--color-surface)] shelf-paste px-2 py-1.5"
            />
            <button type="button" onClick={readPaste} disabled={!paste.trim()} className="shrink-0 rounded-full border border-[var(--color-line)] px-3 py-1.5 text-xs disabled:opacity-40">
              読む
            </button>
          </div>
          {pasteError && <p className="mt-1 text-[11px] text-ink/60">読めませんでした。棚のURLか「v1.」で始まる文字列を貼ってください。</p>}
        </section>
      )}

      {menuCard && !viewing && (
        <Sheet
          d={menuCard}
          genreName={genreName}
          onClose={() => setMenu(null)}
          onMove={(s) => update((x) => moveItem(x, menuCard.item.slug, s))}
          onOwned={(n) => update((x) => setOwned(x, menuCard.item.slug, n))}
          onRemove={() => {
            update((x) => removeItem(x, menuCard.item.slug));
            setMenu(null);
          }}
        />
      )}
    </div>
  );
}
