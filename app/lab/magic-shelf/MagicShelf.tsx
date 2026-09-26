"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { ensureFullIndex, isFullIndexLoaded, useMangaIndex } from "@/lib/useMangaIndex";
import {
  type Book,
  type CastResult,
  type GenreDef,
  type Spell,
  GROUPS,
  SORTS,
  castSpell,
  compileSpell,
  describeSpell,
  makeSpellbook,
  setExclusive,
  toBooks,
  toggleClause,
} from "./spell";

/** 集めなし = 1回に呼ぶ冊数 / 集めあり = 棚ごとの冊数 / 深淵に残す冊数。
 *  ★描く本を絞るのは view transition が名前付き要素を1枚ずつ撮るため(スマホの負荷とメモリを抑える)。 */
const LIMIT_STEP = 60;
const GROUP_STEP = 12;
const SUNK_MAX = 24;
/** 打鍵中は待つ(1文字ごとに唱えると演出が重なって読めない)。Enter・チップは即時。 */
const TYPE_DEBOUNCE_MS = 280;

const YEAR_CHIPS = [
  { token: "1969年以前", label: "〜60s" },
  ...[1970, 1980, 1990, 2000, 2010, 2020].map((d) => ({ token: `${d}年代`, label: `${String(d).slice(2)}s` })),
];
const VOL_CHIPS = [
  { token: "1巻", label: "1巻" },
  { token: "2-5巻", label: "2〜5巻" },
  { token: "6-20巻", label: "6〜20巻" },
  { token: "21巻以上", label: "21巻〜" },
];
const STATUS_CHIPS = [
  { token: "完結", label: "完結" },
  { token: "連載中", label: "連載中" },
];

type TabId = "genre" | "year" | "vols" | "status" | "sort" | "group";
const TABS: { id: TabId; label: string }[] = [
  { id: "genre", label: "ジャンル" },
  { id: "year", label: "年代" },
  { id: "vols", label: "巻数" },
  { id: "status", label: "完結" },
  { id: "sort", label: "並び" },
  { id: "group", label: "集め" },
];

function countKind(spell: Spell, kind: "genre" | "year" | "vols" | "status"): string {
  const n = spell.clauses.filter((c) => !c.neg && c.kind === kind).length;
  return n ? String(n) : "";
}

type Applied = {
  text: string;
  spell: Spell;
  result: CastResult;
  /** 直前まで見えていて、今回の呪文に合わなくなった本(新しく沈んだ順) */
  sunk: Book[];
  ms: number;
  /** 今回はじめて現れた本(view transition が無いブラウザ用の登場演出) */
  fresh: Set<string>;
  caps: Record<string, number>;
  castId: number;
};

// ─── view transition(条件を変えた瞬間に本が飛んで並び替わる) ───────────────

type VTLike = { finished: Promise<void>; ready: Promise<void>; skipTransition: () => void };
let _vt: VTLike | null = null;

function canTransition(): boolean {
  return (
    typeof document !== "undefined" &&
    typeof (document as { startViewTransition?: unknown }).startViewTransition === "function" &&
    !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );
}

/** CSS の識別子として安全な view-transition-name(slug は数字始まりや記号を含み得る)。 */
function vtName(key: string): string {
  return "ms-" + key.replace(/[^a-zA-Z0-9-]/g, (c) => `_${c.codePointAt(0)!.toString(16)}_`);
}

/**
 * 書架の差し替えを view transition で包む。
 * ★overlays(共通ヘッダーと呪文コンソール)にも遷移中だけ名前を付ける: 名前付き要素は全部ページの写しより
 *   上に描かれるため、付けないとスクロール中に飛ぶ本が貼り付きバーの上を横切る。両者は z-index が本より上
 *   = 描画順で後ろに並ぶので、バーは本の上に残る。
 * ★名前を付けるのは「画面の近く(上下半画面)にある本」だけ = 撮影枚数を画面の本数に比例させる。
 *   遷移後は「さっき名前を付けた本」+「新しく画面の近くに来た本」に付け直す(= 同じ本は飛んで移動、
 *   消える本は沈み、現れる本は召喚される)。遠くの本は名前なしでルートのクロスフェードに溶ける。
 */
function transitionShelf(root: HTMLElement | null, overlays: (HTMLElement | null)[], update: () => void): void {
  if (!root || !canTransition()) {
    update();
    return;
  }
  _vt?.skipTransition(); // 連打 = 前の演出は打ち切って最新の呪文へ
  const html = document.documentElement;
  const margin = window.innerHeight * 0.5;
  const near = (el: HTMLElement) => {
    const r = el.getBoundingClientRect();
    return r.bottom > -margin && r.top < window.innerHeight + margin;
  };
  const cells = () => root.querySelectorAll<HTMLElement>("[data-vt]");
  const named = new Set<string>();
  cells().forEach((el) => {
    const on = near(el);
    el.style.viewTransitionName = on ? el.dataset.vt! : "";
    if (on) named.add(el.dataset.vt!);
  });
  const bars = overlays.filter((el): el is HTMLElement => !!el);
  bars.forEach((el, i) => (el.style.viewTransitionName = `ms-bar-${i}`));
  html.classList.add("ms-vt");
  const vt = (document as unknown as { startViewTransition: (cb: () => void) => VTLike }).startViewTransition(() => {
    flushSync(update);
    cells().forEach((el) => {
      const k = el.dataset.vt!;
      el.style.viewTransitionName = named.has(k) || near(el) ? k : "";
    });
  });
  _vt = vt;
  vt.ready.catch(() => {}); // 打ち切り(skip)は正常系 = 未処理エラーにしない
  vt.finished
    .catch(() => {})
    .finally(() => {
      if (_vt !== vt) return; // 次の詠唱が走っていれば後始末はそちらに任せる
      _vt = null;
      html.classList.remove("ms-vt");
      cells().forEach((el) => (el.style.viewTransitionName = ""));
      bars.forEach((el) => (el.style.viewTransitionName = ""));
    });
}

// ─── 書影は見えている分だけ(1つの IntersectionObserver を全書影で共有) ───────────

let _io: IntersectionObserver | null = null;
const _onSeen = new WeakMap<Element, () => void>();
function watchOnce(el: Element, fn: () => void): () => void {
  if (!_io)
    _io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (!e.isIntersecting) continue;
          _onSeen.get(e.target)?.();
          _onSeen.delete(e.target);
          _io!.unobserve(e.target);
        }
      },
      { rootMargin: "160px 0px" },
    );
  _onSeen.set(el, fn);
  _io.observe(el);
  return () => {
    _onSeen.delete(el);
    _io?.unobserve(el);
  };
}

function LazyCover({ src, title }: { src: string | null; title: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [seen, setSeen] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!src || seen || !ref.current) return;
    if (typeof IntersectionObserver === "undefined") {
      setSeen(true);
      return;
    }
    return watchOnce(ref.current, () => setSeen(true));
  }, [src, seen]);
  const blank = !src || failed;
  return (
    <span ref={ref} className="ms-cover">
      {!blank && seen && (
        // eslint-disable-next-line @next/next/no-img-element -- 外部CDN直リンク(images.unoptimized)。読み込み時機は上の観測で握る
        <img
          src={src}
          alt=""
          decoding="async"
          onLoad={(e) => (e.currentTarget.dataset.loaded = "1")}
          onError={() => setFailed(true)}
        />
      )}
      {blank && <span className="ms-spine">{title}</span>}
    </span>
  );
}

const STATUS_MARK: Record<string, string> = { completed: "完", ongoing: "連", hiatus: "休" };

function BookCell({
  b,
  genreName,
  sunk,
  fresh,
}: {
  b: Book;
  genreName: Map<string, string>;
  sunk?: boolean;
  fresh?: boolean;
}) {
  const genres = b.genres.map((g) => genreName.get(g) ?? g).join("・");
  return (
    <Link
      href={`/manga/${b.slug}`}
      prefetch={false} // 呪文ごとに見える本が入れ替わる = 先読みすると唱えるたびに通信が走る
      className="ms-book"
      data-vt={vtName(b.slug)}
      data-sunk={sunk ? "" : undefined}
      data-fresh={fresh ? "" : undefined}
      title={`${b.title}${genres ? ` — ${genres}` : ""}`}
    >
      <LazyCover src={b.cover} title={b.title} />
      <span className="ms-title">{b.title}</span>
      <span className="ms-meta">
        {b.year ?? "—"} · {b.vols > 0 ? `${b.vols}巻` : "—"} ·{" "}
        <span data-st={b.status}>{STATUS_MARK[b.status] ?? "?"}</span>
      </span>
      {genres && <span className="ms-genres">{genres}</span>}
    </Link>
  );
}

function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" className="ms-chip" aria-pressed={on} onClick={onClick}>
      {children}
    </button>
  );
}

/** 共有URLの鍵。★?q= は使わない = 全頁の左レール(FilterRail)が ?q= を自分の検索語として読むため、
 *  呪文がレールの検索窓に流れ込んで「一致する作品がありません」を出す(2026-09-26 PC幅で確認)。 */
const SPELL_PARAM = "spell";

function readQuery(): string {
  try {
    return new URLSearchParams(window.location.search).get(SPELL_PARAM) ?? "";
  } catch {
    return "";
  }
}

function writeQuery(q: string): void {
  try {
    const url = q ? `${window.location.pathname}?${SPELL_PARAM}=${encodeURIComponent(q)}` : window.location.pathname;
    window.history.replaceState(window.history.state, "", url);
  } catch {
    /* 共有URLは付加価値。失敗しても書架は動く */
  }
}

export default function MagicShelf({ genres }: { genres: GenreDef[] }) {
  const items = useMangaIndex();
  // ★この頁は「探す」が本文 = フル索引を手すき待ちにせず即要求(head 100件だけで篩う誤答窓を縮める)
  useEffect(() => ensureFullIndex(), []);
  const full = items !== null && isFullIndexLoaded();
  // head が取れず空配列が返る間(= フル索引待ち)は「まだ開いていない」扱い = 0冊で唱えない
  const books = useMemo(() => (items && (items.length > 0 || full) ? toBooks(items) : null), [items, full]);

  const spellbook = useMemo(() => makeSpellbook(genres), [genres]);
  const genreName = useMemo(() => new Map(genres.map((g) => [g.key, g.name])), [genres]);

  const [text, setText] = useState("");
  const [applied, setApplied] = useState<Applied | null>(null);
  const [help, setHelp] = useState(false);
  const [tab, setTab] = useState<TabId>("genre");
  const appliedRef = useRef<Applied | null>(null);
  appliedRef.current = applied;
  const castTextRef = useRef<string | null>(null); // 最後に唱えた(唱えかけの)呪文 = 打鍵待ちの二重詠唱よけ
  // ★state(ref ではなく): 変換確定で値が変わらなくても再描画→下の打鍵待ちが走り直す
  const [composing, setComposing] = useState(false);
  const shelfRef = useRef<HTMLDivElement>(null);
  const consoleRef = useRef<HTMLElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  const cast = useCallback(
    (nextText: string, opts?: { caps?: Record<string, number>; animate?: boolean }) => {
      if (!books) return;
      const prev = appliedRef.current;
      const animate = opts?.animate !== false && canTransition();
      const t0 = performance.now();
      const spell = spellbook.parse(nextText);
      const caps = opts?.caps ?? {};
      const step = spell.group === "none" ? LIMIT_STEP : GROUP_STEP;
      const result = castSpell(books, spell, (k) => caps[k] ?? step);
      const ms = performance.now() - t0;

      const shown = new Set<string>();
      for (const g of result.groups) for (const b of g.books) shown.add(b.slug);
      const pass = compileSpell(spell);
      const before = prev ? [...prev.result.groups.flatMap((g) => g.books), ...prev.sunk] : [];
      const sunk: Book[] = [];
      const seen = new Set<string>();
      for (const b of before) {
        if (sunk.length >= SUNK_MAX) break;
        if (shown.has(b.slug) || seen.has(b.slug) || pass(b)) continue;
        seen.add(b.slug);
        sunk.push(b);
      }
      const had = new Set(before.map((b) => b.slug));
      const fresh = new Set<string>();
      if (prev && !animate) for (const s of shown) if (!had.has(s)) fresh.add(s);

      const next: Applied = { text: nextText, spell, result, sunk, ms, fresh, caps, castId: (prev?.castId ?? 0) + 1 };
      castTextRef.current = nextText;
      writeQuery(nextText.trim());
      if (animate && prev)
        transitionShelf(
          shelfRef.current,
          [document.querySelector<HTMLElement>("body > header"), consoleRef.current],
          () => setApplied(next),
        );
      else setApplied(next);
    },
    [books, spellbook],
  );

  // 索引が届いた(head → full 差し替え含む)= 今の呪文で唱え直す。初回は URL の ?spell= から。
  useEffect(() => {
    if (!books) return;
    const cur = appliedRef.current;
    if (cur) {
      cast(castTextRef.current ?? cur.text, { caps: cur.caps, animate: false });
      return;
    }
    const q = readQuery();
    setText(q);
    cast(q, { animate: false });
  }, [books, cast]);

  // 打鍵 → 少し待って唱える(IME変換中は唱えない)
  useEffect(() => {
    if (!books || composing || text === castTextRef.current) return;
    const id = setTimeout(() => {
      if (text !== castTextRef.current) cast(text);
    }, TYPE_DEBOUNCE_MS);
    return () => clearTimeout(id);
  }, [text, books, cast, composing]);

  // コンソールを共通ヘッダー(sticky)の真下に貼る
  useEffect(() => {
    const header = document.querySelector("body > header");
    const root = rootRef.current;
    if (!header || !root) return;
    const set = () => root.style.setProperty("--ms-top", `${Math.round(header.getBoundingClientRect().height)}px`);
    set();
    const ro = new ResizeObserver(set);
    ro.observe(header);
    return () => ro.disconnect();
  }, []);

  const live = useMemo(() => spellbook.parse(text), [spellbook, text]);
  const hasKey = (token: string) => {
    const tok = spellbook.parseToken(token);
    return tok?.type === "clause" && live.clauses.some((c) => !c.neg && c.key === tok.clause.key);
  };
  const edit = (next: string) => {
    setText(next);
    cast(next);
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const t = text.trim();
    const tok = spellbook.parseToken(t);
    if (tok?.type === "cmd") {
      if (tok.cmd === "help") {
        setHelp(true);
        setText(applied?.text ?? "");
      } else edit("");
      return;
    }
    cast(text);
  };

  const randomSpell = () => {
    const g = genres[Math.floor(Math.random() * genres.length)];
    const extras = [...YEAR_CHIPS.map((c) => c.token), ...STATUS_CHIPS.map((c) => c.token), "", ""];
    const x = extras[Math.floor(Math.random() * extras.length)];
    edit([g?.name, x].filter(Boolean).join(" "));
  };

  const more = (key: string, shownCount: number) => {
    if (!applied) return;
    const step = applied.spell.group === "none" ? LIMIT_STEP : GROUP_STEP;
    cast(applied.text, { caps: { ...applied.caps, [key]: shownCount + step }, animate: false });
  };

  const total = books?.length ?? 0;
  const grouped = applied ? applied.spell.group !== "none" : false;

  // タブ見出しの目印 = そのタブで今効いている語の数(並び/集めは既定以外なら ●)
  const marks: Record<TabId, string> = {
    genre: countKind(live, "genre"),
    year: countKind(live, "year"),
    vols: countKind(live, "vols"),
    status: countKind(live, "status"),
    sort: live.sort !== "pop" ? "●" : "",
    group: live.group !== "none" ? "●" : "",
  };
  const clauseChips = (list: { token: string; label: string }[]) =>
    list.map((c) => (
      <Chip key={c.token} on={hasKey(c.token)} onClick={() => edit(toggleClause(text, c.token, spellbook))}>
        {c.label}
      </Chip>
    ));

  return (
    <div ref={rootRef} className="ms-shelf-app">
      {/* ★入力行・呪文チップ・結果行をまとめて貼り付ける = スマホでも本が動く様子を見ながら押せる */}
      <section ref={consoleRef} className="ms-console" aria-label="呪文コンソール">
        <form className="ms-prompt" onSubmit={onSubmit} role="search">
          <span className="ms-caret" aria-hidden>
            ✦&gt;
          </span>
          <input
            className="ms-input"
            type="text"
            inputMode="search"
            enterKeyHint="go"
            autoComplete="off"
            autoCapitalize="off"
            spellCheck={false}
            aria-label="呪文(条件)を入力"
            placeholder="例: ファンタジー 90年代 完結"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onCompositionStart={() => setComposing(true)}
            onCompositionEnd={(e) => {
              setComposing(false);
              setText(e.currentTarget.value);
            }}
          />
          {text && (
            <button type="button" className="ms-clear" aria-label="呪文を消す" onClick={() => edit("")}>
              ×
            </button>
          )}
          <button type="submit" className="ms-cast">
            詠唱
          </button>
        </form>

        <div className="ms-tabs" role="tablist" aria-label="呪文の種類">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              className="ms-tab"
              onClick={() => setTab(t.id)}
            >
              {t.label}
              {marks[t.id] && <i>{marks[t.id]}</i>}
            </button>
          ))}
          <span className="ms-tabs-tools">
            <button type="button" className="ms-tool" aria-label="おまかせ詠唱" title="おまかせ詠唱" onClick={randomSpell}>
              ⚄
            </button>
            <button
              type="button"
              className="ms-tool"
              aria-label="呪文帳"
              title="呪文帳"
              aria-expanded={help}
              onClick={() => setHelp((v) => !v)}
            >
              ?
            </button>
          </span>
        </div>
        <div key={tab} className="ms-row" role="tabpanel">
          {tab === "genre" && clauseChips(genres.map((g) => ({ token: g.name, label: g.name })))}
          {tab === "year" && clauseChips(YEAR_CHIPS)}
          {tab === "vols" && clauseChips(VOL_CHIPS)}
          {tab === "status" && clauseChips(STATUS_CHIPS)}
          {tab === "sort" &&
            SORTS.map((s) => (
              <Chip
                key={s.id}
                on={live.sort === s.id}
                onClick={() => edit(setExclusive(text, "sort", s.id === "pop" ? "" : s.token, spellbook))}
              >
                {s.label}
              </Chip>
            ))}
          {tab === "group" &&
            GROUPS.map((g) => (
              <Chip
                key={g.id}
                on={live.group === g.id}
                onClick={() => edit(setExclusive(text, "group", g.token, spellbook))}
              >
                {g.label}
              </Chip>
            ))}
        </div>

        <div className="ms-out" aria-live="polite">
          {!applied ? (
            <p>書架を開いています…</p>
          ) : (
            <>
              <p>
                <span className="ms-dim">✦</span> {describeSpell(applied.spell)}
              </p>
              <p>
                <span className="ms-dim">→</span> <b>{applied.result.matched.toLocaleString()}</b>冊が集まり、
                <b>{(total - applied.result.matched).toLocaleString()}</b>冊が沈んだ
                <span className="ms-dim">
                  {" "}
                  · {applied.ms < 1 ? applied.ms.toFixed(2) : applied.ms.toFixed(1)}ms · 全{total.toLocaleString()}冊
                  {!full && "(書架を展開中…)"}
                </span>
              </p>
            </>
          )}
        </div>

        {help && (
          <div className="ms-help">
            <button type="button" className="ms-help-close" aria-label="呪文帳を閉じる" onClick={() => setHelp(false)}>
              ×
            </button>
            <dl>
              <dt>ジャンル</dt>
              <dd>ファンタジー / #ホラー / sf ── 並べると「かつ」</dd>
              <dt>年</dt>
              <dd>1990年代 / 90年代 / 1995 / 1980〜1999 / 2010年以降 / 1979年以前</dd>
              <dt>巻数</dt>
              <dd>1巻 / 2-5巻 / 10巻以上 / 5巻以下</dd>
              <dt>状態</dt>
              <dd>完結 / 連載中 ── 年・巻数・状態は同じ種類どうし「または」</dd>
              <dt>除く</dt>
              <dd>-ホラー / !完結 / -1巻</dd>
              <dt>並び</dt>
              <dd>人気順(既定) 古い順 新しい順 巻数順 50音順</dd>
              <dt>集め</dt>
              <dd>年代別 状態別 巻数別</dd>
              <dt>その他</dt>
              <dd>題名に含む語として探す(ひらがなでも可) / 消去 = 全部消す / ? = この呪文帳</dd>
            </dl>
          </div>
        )}
      </section>

      <div ref={shelfRef} className="ms-shelf">
        {applied && <div key={applied.castId} className="ms-sweep" aria-hidden />}
        {!applied &&
          Array.from({ length: 12 }, (_, i) => (
            <span key={`sk${i}`} className="ms-book ms-book--ghost" aria-hidden>
              <span className="ms-cover" />
            </span>
          ))}
        {applied && applied.result.matched === 0 && (
          <p className="ms-empty" data-vt={vtName("empty")}>
            何も集まらなかった…… 呪文を1語減らすか、-(除く)を外してみて。
          </p>
        )}
        {applied?.result.groups.flatMap((g) => {
          const cells: React.ReactNode[] = [];
          if (grouped)
            cells.push(
              <h2 key={`h:${g.key}`} className="ms-head" data-vt={vtName(`h:${g.key}`)}>
                {g.label}
                <small>{g.total.toLocaleString()}冊</small>
              </h2>,
            );
          for (const b of g.books)
            cells.push(<BookCell key={b.slug} b={b} genreName={genreName} fresh={applied.fresh.has(b.slug)} />);
          if (g.total > g.books.length)
            cells.push(
              <button
                key={`m:${g.key}`}
                type="button"
                className="ms-more"
                data-vt={vtName(`m:${g.key}`)}
                onClick={() => more(g.key, g.books.length)}
              >
                <span>+{(g.total - g.books.length).toLocaleString()}冊</span>
                さらに呼ぶ
              </button>,
            );
          return cells;
        })}
        {applied && applied.sunk.length > 0 && (
          <h2 key="h:abyss" className="ms-head ms-head--abyss" data-vt={vtName("h:abyss")}>
            深淵 ── 沈んだ本
            <small>さっきまで見えていた {applied.sunk.length}冊</small>
          </h2>
        )}
        {applied?.sunk.map((b) => <BookCell key={b.slug} b={b} genreName={genreName} sunk />)}
      </div>
    </div>
  );
}
