/**
 * マイ本棚(もってる/気になる/ほしい)の中身と操作 = 純関数だけ(React/DOM 無し・テストで押さえる)。
 * 依頼書 = docs/cloud-briefs/my-shelf.md(2026-09-28 ユーザ裁定)。
 *
 * ★単位は「作品×版」(2026-10-31 ユーザ裁定 A+1: 同じ作品の別の版を別々にしまえる)。 識別 = itemKey(slug+版ラベル)。
 *   版が1つしかない作品・版を選ばずにしまった分は版ラベル無し(= slug だけが識別)。
 *   「もってる」だけ「1巻から連続で持っている最後の巻」を整数1つで持つ(1〜6, 8, 9巻所持 → 6。8・9巻は記録しない割り切り)。
 * ★保存先 = 端末(localStorage)+ 棚のURL。ログイン・サーバ保存は無い(個人情報ゼロ方針)。
 * ★表示の材料(書影・題名・巻数・状態)は一覧索引(useMangaIndex)から引く。ここに保存する題名/書影は
 *   「作品が見つからなくなった時」に出すための控え。
 */

export type ShelfId = "own" | "curious" | "wish";

export const SHELVES: { id: ShelfId; label: string; note: string }[] = [
  { id: "own", label: "もってる", note: "何巻まで持っているかを覚えて、続きの巻を知らせます" },
  { id: "curious", label: "気になる", note: "読むか迷っている作品" },
  { id: "wish", label: "ほしい", note: "買い物リスト" },
];

export type ShelfItem = {
  slug: string;
  title: string;
  /** 保存時点の書影URL(控え) */
  cover: string | null;
  shelf: ShelfId;
  /** もってるの時だけ: 1巻から連続で持っている最後の巻(0 = まだ1巻が無い) */
  owned?: number;
  /** 版を選んで登録した時だけ: 版ラベル(作品頁の表示ブロックの名前 = components/VolumeRow.tsx displayBlocks)。識別の一部 */
  edition?: string;
  /** 版を選んで登録した時だけ: 登録時点のその版の既刊。 本棚は巻の書影データ(lib/volCovers)からその版の今の巻数を引けたらそちらで比べる */
  editionTotal?: number;
  addedAt: number;
  updatedAt: number;
};

// ★v2(2026-10-31): 同じ作品を版ごとに別々に持つ形。 旧 v1 は「同じ slug は1つ」に畳む = 古いJSの頁が v1 を読んで
//   書き戻すと版ごとの棚が潰れるので、名前を変えて分ける(v2 が無い時だけ v1 を読んで引き継ぐ)。
export const STORAGE_KEY = "mangal:shelf:v2";
export const LEGACY_STORAGE_KEY = "mangal:shelf:v1";
/** 巻数の上限(入力の暴走よけ。最長のこち亀でも200巻台) */
const MAX_VOL = 9999;

type ReadStore = { getItem(key: string): string | null };
type WriteStore = { setItem(key: string, value: string): void };

const isShelfId = (v: unknown): v is ShelfId => v === "own" || v === "curious" || v === "wish";
const toInt = (v: unknown): number | undefined => {
  const n = typeof v === "number" ? v : typeof v === "string" && v.trim() !== "" ? Number(v) : NaN;
  return Number.isFinite(n) ? Math.min(MAX_VOL, Math.max(0, Math.floor(n))) : undefined;
};

// 時刻(ms)。toInt は巻数用に MAX_VOL で頭打ちにするので別に整える
function cleanTime(v: unknown, fallback: number): number {
  return typeof v === "number" && Number.isFinite(v) && v > 0 ? Math.floor(v) : fallback;
}

/** 1件を正しい形に整える(壊れた値は捨てる=null)。もってる以外は owned を持たない。 */
function cleanItem(raw: unknown, now: number): ShelfItem | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const slug = typeof r.slug === "string" ? r.slug.trim() : "";
  if (!slug || !isShelfId(r.shelf)) return null;
  const item: ShelfItem = {
    slug,
    title: typeof r.title === "string" ? r.title : "",
    cover: typeof r.cover === "string" && r.cover ? r.cover : null,
    shelf: r.shelf,
    addedAt: cleanTime(r.addedAt, now),
    updatedAt: 0,
  };
  item.updatedAt = cleanTime(r.updatedAt, item.addedAt);
  if (item.shelf === "own") item.owned = toInt(r.owned) ?? 0;
  const edition = typeof r.edition === "string" ? r.edition.trim() : "";
  const editionTotal = toInt(r.editionTotal);
  if (edition) {
    item.edition = edition;
    if (editionTotal) item.editionTotal = editionTotal;
  }
  return item;
}

/** 棚の1冊の識別 = slug + 版ラベル(版ラベルが無ければ slug そのもの)。 */
export function itemKey(x: { slug: string; edition?: string | null }): string {
  return x.edition ? `${x.slug}\u0000${x.edition}` : x.slug;
}

/** 読み込んだ値(JSON)→ 棚。形の崩れた行は捨て、同じ作品×版は1つにまとめる。 */
export function normalizeItems(raw: unknown, now = Date.now()): ShelfItem[] {
  const arr = Array.isArray(raw) ? raw : raw && typeof raw === "object" ? (raw as { items?: unknown }).items : null;
  if (!Array.isArray(arr)) return [];
  const out: ShelfItem[] = [];
  for (const r of arr) {
    const it = cleanItem(r, now);
    if (it) out.push(it);
  }
  return mergeSameKey(out);
}

/** 端末から読む。保存できない環境(プライベートモード・容量超過・無効化)は黙って空の棚。 v2 が無ければ v1 を引き継ぐ。 */
export function loadShelf(store: ReadStore | null | undefined): ShelfItem[] {
  try {
    const s = store?.getItem(STORAGE_KEY) ?? store?.getItem(LEGACY_STORAGE_KEY);
    return s ? normalizeItems(JSON.parse(s)) : [];
  } catch {
    return [];
  }
}

/** 端末へ書く。失敗したら false(棚は画面の上でだけ生きる)。 */
export function saveShelf(store: WriteStore | null | undefined, items: ShelfItem[]): boolean {
  try {
    if (!store) return false;
    store.setItem(STORAGE_KEY, JSON.stringify({ v: 2, items }));
    return true;
  } catch {
    return false;
  }
}

/**
 * 同じ作品×版をまとめる(= 改名・重複頁の統合で2つが同じ slug になった時・棚の合流)。 版が違えば別の1冊のまま。
 * ★どれかが「もってる」なら結果も「もってる」、owned は大きい方(持っている事実を失わない)。
 *   それ以外は後から更新した方の棚。題名・書影・版の既刊は後から更新した方。登録日は古い方、更新日は新しい方。
 */
export function mergeSameKey(items: ShelfItem[]): ShelfItem[] {
  const order: string[] = [];
  const groups = new Map<string, ShelfItem[]>();
  for (const it of items) {
    const k = itemKey(it);
    let g = groups.get(k);
    if (!g) {
      groups.set(k, (g = []));
      order.push(k);
    }
    g.push(it);
  }
  return order.map((k) => {
    const g = groups.get(k)!;
    if (g.length === 1) return g[0];
    const latest = g.reduce((a, b) => (b.updatedAt > a.updatedAt ? b : a));
    const owns = g.filter((x) => x.shelf === "own");
    const merged: ShelfItem = {
      ...latest,
      addedAt: Math.min(...g.map((x) => x.addedAt)),
      updatedAt: Math.max(...g.map((x) => x.updatedAt)),
    };
    if (owns.length) {
      merged.shelf = "own";
      merged.owned = Math.max(...owns.map((x) => x.owned ?? 0));
    }
    if (!merged.title) merged.title = g.find((x) => x.title)?.title ?? "";
    if (!merged.cover) merged.cover = g.find((x) => x.cover)?.cover ?? null;
    return merged;
  });
}

/** 旧名(同じ slug を1つにまとめていた頃)。 今は作品×版でまとめる。 */
export const mergeSameSlug = mergeSameKey;

export type PutInput = {
  slug: string;
  title: string;
  cover: string | null;
  shelf: ShelfId;
  owned?: number;
  /** 版を選んだ時だけ(label と登録時点の既刊)。 無し(null/省略) = 版ラベル無しの1冊 */
  edition?: { label: string; total: number } | null;
};

/** しまう/棚を移す/巻数を変える(= 同じ作品×版があれば上書き・登録日は保つ)。新規は先頭に置く。 */
export function putItem(items: ShelfItem[], input: PutInput, now = Date.now()): ShelfItem[] {
  const key = itemKey({ slug: input.slug, edition: input.edition?.label });
  const prev = items.find((x) => itemKey(x) === key);
  const next: ShelfItem = {
    slug: input.slug,
    title: input.title || prev?.title || "",
    cover: input.cover ?? prev?.cover ?? null,
    shelf: input.shelf,
    addedAt: prev?.addedAt ?? now,
    updatedAt: now,
  };
  if (input.shelf === "own") next.owned = toInt(input.owned) ?? prev?.owned ?? 0;
  const ed = input.edition;
  if (ed && ed.label) {
    next.edition = ed.label;
    const t = toInt(ed.total);
    if (t) next.editionTotal = t;
    else if (prev?.editionTotal) next.editionTotal = prev.editionTotal;
  }
  return prev ? items.map((x) => (itemKey(x) === key ? next : x)) : [next, ...items];
}

const editionOf = (x: ShelfItem) => (x.edition ? { label: x.edition, total: x.editionTotal ?? 0 } : null);

/** 棚だけ移す(もってるへ移したら owned は前の値 or 0)。 key = itemKey(版ラベルの無い1冊は slug そのもの)。 */
export function moveItem(items: ShelfItem[], key: string, shelf: ShelfId, now = Date.now()): ShelfItem[] {
  const prev = items.find((x) => itemKey(x) === key);
  if (!prev) return items;
  return putItem(items, { ...prev, shelf, owned: prev.owned, edition: editionOf(prev) }, now);
}

export function setOwned(items: ShelfItem[], key: string, owned: number, now = Date.now()): ShelfItem[] {
  const prev = items.find((x) => itemKey(x) === key);
  if (!prev || prev.shelf !== "own") return items;
  return putItem(items, { ...prev, owned, edition: editionOf(prev) }, now);
}

/** 取り出す(= 消すのは本人だけ。自動では消さない)。 key = itemKey。 */
export function removeItem(items: ShelfItem[], key: string): ShelfItem[] {
  return items.filter((x) => itemKey(x) !== key);
}

// ─── slug の解決(改名・統合で変わる) ─────────────────────────────

/** "/manga/<slug>"(URL・パス・.html 付き・末尾スラッシュ付き)から slug を取り出す。 */
export function parseMangaSlug(urlOrPath: string): string | null {
  let path = urlOrPath;
  try {
    path = new URL(urlOrPath, "https://x.invalid").pathname;
  } catch {
    /* パスのまま */
  }
  const m = path.match(/^\/manga\/([^/?#]+?)(?:\.html)?\/?$/);
  if (!m) return null;
  try {
    return decodeURIComponent(m[1]);
  } catch {
    return m[1];
  }
}

/** 旧 slug の作品頁を取りに行った結果(転送を辿った後の URL と、頁が在ったか)。 */
export type FetchFinal = (path: string) => Promise<{ url: string; ok: boolean } | null>;

/**
 * 索引に無い slug を、作品頁の 301 転送で新しい slug に解く(本番= KV で全件 / テスト環境= _redirects の一部)。
 * 転送されて別の作品頁に着いた時だけ新 slug を返す。転送なし・404・通信失敗は null(= 見つからない)。
 */
export async function resolveMovedSlug(slug: string, fetchFinal: FetchFinal): Promise<string | null> {
  try {
    const r = await fetchFinal(`/manga/${encodeURIComponent(slug)}`);
    if (!r || !r.ok) return null;
    const to = parseMangaSlug(r.url);
    return to && to !== slug ? to : null;
  } catch {
    return null;
  }
}

/** slug を付け替える(全部の版ごと。同じ作品×版が既にあれば1つにまとめる)。 */
export function renameSlug(items: ShelfItem[], from: string, to: string): ShelfItem[] {
  if (from === to) return items;
  return mergeSameKey(items.map((x) => (x.slug === from ? { ...x, slug: to } : x)));
}

// ─── もってるの札 ─────────────────────────────────────────────

export type IndexFacts = {
  /** 最大単一版の巻数(= 一覧表の「巻」。★total_volumes は全版の合計なので使わない) */
  max_edition_volumes: number;
  status: "ongoing" | "completed" | "hiatus";
};

export type OwnedNote = {
  kind: "behind" | "caught-up" | "complete" | "complete-behind" | "unknown";
  text: string;
  /** 続きの巻(owned+1 〜 既刊) */
  next: number[];
  /** 比べた既刊(不明は null) */
  total: number | null;
  /** 版を選んで登録した = 登録時点の既刊で比べた */
  fixedEdition: boolean;
};

function volRange(from: number, to: number): string {
  if (from === to) return `${from}巻`;
  if (to === from + 1) return `${from}・${to}巻`;
  return `${from}〜${to}巻`;
}

/**
 * 「もってる」の札の1行。既刊 = liveTotal(版の今の巻数 = 巻の書影データから引けた時)→ 版を選んだ作品は登録時点の値 →
 * それ以外は索引の最大単一版の巻数。 fixedEdition = 登録時点の値で比べた(新刊が出ても増えない)時だけ true。
 *   未達&連載中 → 「10巻まで所持 → 11・12巻が出ています」
 *   揃い&連載中 → 「最新刊まで揃っています」 / 揃い&完結 → 「全巻揃っています」
 *   未達&完結 → 「完結済み・あと2冊で全巻」
 */
export function ownedNote(
  item: Pick<ShelfItem, "owned" | "editionTotal">,
  facts: IndexFacts | null,
  liveTotal?: number | null,
): OwnedNote {
  const owned = item.owned ?? 0;
  const live = liveTotal && liveTotal > 0 ? liveTotal : null;
  const fixedEdition = !live && !!item.editionTotal;
  const total = live ?? item.editionTotal ?? (facts && facts.max_edition_volumes > 0 ? facts.max_edition_volumes : null);
  const had = owned > 0 ? `${owned}巻まで所持` : "1巻はまだ";
  if (total === null) return { kind: "unknown", text: owned > 0 ? had : "巻数の記録なし", next: [], total, fixedEdition };
  const completed = facts?.status === "completed";
  if (owned >= total)
    return completed
      ? { kind: "complete", text: "全巻揃っています", next: [], total, fixedEdition }
      : { kind: "caught-up", text: "最新刊まで揃っています", next: [], total, fixedEdition };
  const next = Array.from({ length: total - owned }, (_, i) => owned + 1 + i);
  if (completed)
    return { kind: "complete-behind", text: `完結済み・あと${total - owned}冊で全巻`, next, total, fixedEdition };
  return { kind: "behind", text: `${had} → ${volRange(owned + 1, total)}が出ています`, next, total, fixedEdition };
}

// ─── 番号タイル・銘板(見た目 C3 = docs/cloud-briefs/my-shelf-look-c3.md) ─────────────

export type VolumeTile = {
  n: number;
  /** owned = 所持 / missing = 出ているが未所持。★1巻も他の巻と同じ扱い(2026-09-29 ユーザ指摘: 1巻だけ細枠は未所持に見える) */
  state: "owned" | "missing";
};
export type VolumeRun = { from: number; to: number; count: number };
export type VolumeTiles = {
  /** 畳んだ所持の前半「1〜to巻 所持(count冊)」。畳まない時は null */
  band: VolumeRun | null;
  /** 個別タイル。先頭は必ず 1/11/21… の10巻区切りの頭(= 10列の格子で 11・21・31巻が左端にそろう) */
  tiles: VolumeTile[];
  /** 未所持の続きのうちタイルに出さなかった分「あと count巻 未所持(from〜to)」。無ければ null */
  tail: VolumeRun | null;
};
/** これを超える巻数の作品は所持の前半を帯に畳む */
export const FOLD_OVER = 40;
/** 未所持タイルは1行(10枚)まで。残りは帯1本(= 長い作品を少しだけ持っている時に1作品で画面が埋まらない) */
export const MISSING_SHOWN = 10;

/**
 * 「もってる」の段の番号タイル。既刊が分からない作品は null(= タイルを出さず所持状況の1行だけ)。
 * 40巻を超える作品は、最後に持っている巻を含む10巻区切りの頭より前を帯1本に畳む
 * (160巻中140巻所持 → 帯「1〜130巻」+ 131〜150 のタイル + 帯「あと10巻 未所持」)。
 * ★既刊より多く持っている(索引が古い・版違い)時も、持っている分までは出す。
 */
export function volumeTiles(owned: number, total: number | null): VolumeTiles | null {
  if (!total || total <= 0) return null;
  const own = Math.max(0, Math.floor(owned));
  const last = Math.max(total, own);
  let start = 1;
  let band: VolumeTiles["band"] = null;
  if (last > FOLD_OVER && own > 10) {
    start = Math.floor((own - 1) / 10) * 10 + 1;
    band = { from: 1, to: start - 1, count: start - 1 };
  }
  const shownTo = Math.min(last, own + MISSING_SHOWN);
  const tiles: VolumeTile[] = [];
  for (let n = start; n <= shownTo; n++) tiles.push({ n, state: n <= own ? "owned" : "missing" });
  const tail = shownTo < last ? { from: shownTo + 1, to: last, count: last - shownTo } : null;
  return { band, tiles, tail };
}

export type PlaqueStats = {
  /** もってる棚の owned の合計 */
  ownedVolumes: number;
  /** 出ている続きの巻(owned < 既刊 の差の合計) */
  nextVolumes: number;
  /** そろっている作品 = 完結でも連載中でも、出ている最後の巻まで持っている(札の「揃っています」と同じ集合) */
  caughtUpWorks: number;
};

/** 真鍮の銘板の3つの数字。既刊は札と同じ規則(ownedNote)で数える = 札の文言と数字が食い違わない。 */
export function plaqueStats(
  items: ShelfItem[],
  factsOf: (slug: string) => IndexFacts | null,
  liveTotalOf?: (x: ShelfItem) => number | null | undefined,
): PlaqueStats {
  const s: PlaqueStats = { ownedVolumes: 0, nextVolumes: 0, caughtUpWorks: 0 };
  for (const x of items) {
    if (x.shelf !== "own") continue;
    s.ownedVolumes += x.owned ?? 0;
    const note = ownedNote(x, factsOf(x.slug), liveTotalOf?.(x));
    s.nextVolumes += note.next.length;
    if (note.kind === "complete" || note.kind === "caught-up") s.caughtUpWorks++;
  }
  return s;
}

// ─── 棚のURL(引っ越し・Safari の7日消去の保険・人に見せる) ─────────────

const SHELF_CODE: Record<ShelfId, string> = { own: "o", curious: "c", wish: "w" };
const CODE_SHELF: Record<string, ShelfId> = { o: "own", c: "curious", w: "wish" };
export const SHARE_PARAM = "s";
const TOKEN_PREFIX = "v1.";

function b64urlEncode(s: string): string {
  const bytes = new TextEncoder().encode(s);
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function b64urlDecode(s: string): string {
  const b64 = s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4);
  const bin = atob(b64);
  const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

/**
 * 棚 → 貼り付け用の文字列(URL の #s= に載せる)。
 * ★題名・書影は載せない(= 索引から引ける。URL を短く保つ)。1行 = [slug, 棚, 巻, 版, 版の既刊, 更新(秒)]、末尾の既定値は省く。
 * ★# の後ろ(フラグメント)に載せる = サーバにも Cloudflare のログにも棚の中身が届かない。
 */
export function encodeShelf(items: ShelfItem[]): string {
  const rows = items.map((x) => {
    const row: (string | number)[] = [
      x.slug,
      SHELF_CODE[x.shelf],
      x.shelf === "own" ? x.owned ?? 0 : 0,
      x.edition ?? "",
      x.editionTotal ?? 0,
      Math.floor(x.updatedAt / 1000),
    ];
    return row;
  });
  return TOKEN_PREFIX + b64urlEncode(JSON.stringify(rows));
}

/** 文字列 or URL(#s= / ?s=)→ 棚。読めなければ null。題名・書影は空(表示時に索引から埋める)。 */
export function decodeShelf(input: string, now = Date.now()): ShelfItem[] | null {
  let token = input.trim();
  const m = token.match(/[#?&]s=([^&#\s]+)/);
  if (m) token = m[1];
  if (!token.startsWith(TOKEN_PREFIX)) return null;
  try {
    const rows = JSON.parse(b64urlDecode(token.slice(TOKEN_PREFIX.length)));
    if (!Array.isArray(rows)) return null;
    const items = rows
      .filter((r): r is unknown[] => Array.isArray(r))
      .map((r) => {
        const sec = typeof r[5] === "number" ? r[5] * 1000 : now;
        return {
          slug: r[0],
          title: "",
          cover: null,
          shelf: CODE_SHELF[String(r[1])],
          owned: r[2],
          edition: r[3],
          editionTotal: r[4],
          addedAt: sec,
          updatedAt: sec,
        };
      });
    return normalizeItems(items, now);
  } catch {
    return null;
  }
}

/** 棚のURL(= この頁の # に載せる)。 */
export function shelfShareUrl(origin: string, items: ShelfItem[]): string {
  return `${origin}/shelf#${SHARE_PARAM}=${encodeShelf(items)}`;
}

export type ImportMode = "overwrite" | "merge";

/**
 * 取り込み。上書き = 持ってきた棚だけにする / 合流 = 両方を合わせる。
 * 合流で同じ作品が両方にあれば mergeSameSlug の規則(もってる優先・巻は大きい方・他は新しい方)。
 * 持ってきた側に題名・書影が無い(URL には載せない)ので、手元に控えがあれば残す。
 */
export function importShelf(current: ShelfItem[], incoming: ShelfItem[], mode: ImportMode): ShelfItem[] {
  if (mode === "overwrite") {
    const keep = new Map(current.map((x) => [x.slug, x]));
    return mergeSameKey(
      incoming.map((x) => ({
        ...x,
        title: x.title || keep.get(x.slug)?.title || "",
        cover: x.cover ?? keep.get(x.slug)?.cover ?? null,
      })),
    );
  }
  return mergeSameKey([...current, ...incoming]);
}

/** 棚ごとの冊数(取り込み確認の表示用)。 */
export function countByShelf(items: ShelfItem[]): Record<ShelfId, number> {
  const c: Record<ShelfId, number> = { own: 0, curious: 0, wish: 0 };
  for (const x of items) c[x.shelf]++;
  return c;
}
