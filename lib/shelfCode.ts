/**
 * 本棚の「文字列」= バックアップ(M2)と おすすめ(R2)の書き出し・読み込み(2026-11-17 ユーザ要件)。
 *
 * 要件(ユーザ):
 *   ① Mac / Windows / iOS / Android で文字化けしない   → 中身は英数字と - _ . だけ(base64url)
 *   ② バックアップに使える                               → 先頭に「MANGAL本棚 日付 N作」・検査文字・旧 v1. も永久に読む
 *   ③ 他人へおすすめを簡単に渡せる(選べる)              → R2 = 作品(と版)だけ。 持っている巻数・日付は入れない
 *   コピペ運用が基本(手で打つことは想定しない)。
 *
 * 形:  <種類><圧縮>.<本体>.<検査>
 *   種類 = "M2"(バックアップ = 棚まるごと)/ "R2"(おすすめ = 選んだ作品だけ)
 *   圧縮 = "z"(deflate-raw)/ "p"(圧縮なし = CompressionStream が無い古いブラウザ)
 *   本体 = 1作品1行・項目はタブ区切りの文字列を base64url にしたもの
 *          M2: slug \t 棚(o/c/w) \t 巻 \t 版 \t 版の既刊   (末尾の既定値は省く)
 *          R2: slug \t 版
 *   検査 = 本体(base64url の文字列そのもの)の CRC32 下位24bit を base64url 4文字。 欠け・書き換えを見つける。
 *   ★時刻は入れない(取り込んだ日付は受け取った側の端末で付ける = 文字列が短くなる)。
 *
 * 読み込みは寛容に(コピペで起きる崩れを全部吸う):
 *   全角→半角(NFKC)・途中の改行や空白・前後に付いた説明文や URL(#s= / ?s=)。
 *   見つからない = "none" / 見つかったが検査が合わない・解けない = "broken"(=「欠けています」)。
 */
import { type ShelfId, type ShelfItem, decodeShelf, normalizeItems } from "./myShelf";

export type ShelfCodeKind = "backup" | "recommend";
export type ReadResult =
  | { ok: true; kind: ShelfCodeKind | "v1"; items: ShelfItem[] }
  | { ok: false; reason: "none" | "broken" };

const SHELF_CODE: Record<ShelfId, string> = { own: "o", curious: "c", wish: "w" };
const CODE_SHELF: Record<string, ShelfId> = { o: "own", c: "curious", w: "wish" };
const KIND_PREFIX: Record<ShelfCodeKind, string> = { backup: "M2", recommend: "R2" };

// ─── base64url / CRC32 ─────────────────────────────────────────────

function bytesToB64url(bytes: Uint8Array): string {
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function b64urlToBytes(s: string): Uint8Array {
  const b64 = s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4);
  const bin = atob(b64);
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

let _crcTable: Uint32Array | null = null;
function crc32(s: string): number {
  if (!_crcTable) {
    _crcTable = new Uint32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      _crcTable[n] = c >>> 0;
    }
  }
  let c = 0xffffffff;
  for (let i = 0; i < s.length; i++) c = _crcTable[(c ^ s.charCodeAt(i)) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
/** 検査文字 = CRC32 の下位24bit を base64url 4文字 */
export function checkChars(body: string): string {
  const v = crc32(body) & 0xffffff;
  return bytesToB64url(new Uint8Array([(v >> 16) & 0xff, (v >> 8) & 0xff, v & 0xff]));
}

// ─── 圧縮(ブラウザ標準の CompressionStream。 無ければ圧縮なし) ─────────────

const canCompress = () => typeof CompressionStream !== "undefined" && typeof DecompressionStream !== "undefined";

async function pipe(bytes: Uint8Array, stream: CompressionStream | DecompressionStream): Promise<Uint8Array> {
  const out = new Response(new Blob([bytes as BlobPart]).stream().pipeThrough(stream));
  return new Uint8Array(await out.arrayBuffer());
}

// ─── 書き出し ─────────────────────────────────────────────

/** 1作品1行の本文(タブ区切り・末尾の既定値は省く)。 タブ・改行は版の名前に入らない前提で、念のため空白に替える。 */
export function payloadText(items: ShelfItem[], kind: ShelfCodeKind): string {
  const clean = (s: string) => s.replace(/[\t\r\n]+/g, " ");
  return items
    .map((x) => {
      const row =
        kind === "recommend"
          ? [x.slug, x.edition ?? ""]
          : [x.slug, SHELF_CODE[x.shelf], x.shelf === "own" ? String(x.owned ?? 0) : "", x.edition ?? "", x.edition && x.editionTotal ? String(x.editionTotal) : ""];
      while (row.length > 1 && row[row.length - 1] === "") row.pop();
      return row.map(clean).join("\t");
    })
    .join("\n");
}

/** 棚 → 文字列(M2 / R2)。 おすすめは同じ作品×版を1つに・持っている巻数や棚は入れない。 */
export async function encodeShelfCode(items: ShelfItem[], kind: ShelfCodeKind): Promise<string> {
  const raw = new TextEncoder().encode(payloadText(items, kind));
  let mode = "p";
  let bytes = raw;
  if (canCompress()) {
    try {
      const z = await pipe(raw, new CompressionStream("deflate-raw"));
      if (z.length < raw.length) {
        bytes = z;
        mode = "z";
      }
    } catch {
      /* 圧縮できない環境は圧縮なしで書く */
    }
  }
  const body = bytesToB64url(bytes);
  return `${KIND_PREFIX[kind]}${mode}.${body}.${checkChars(body)}`;
}

/** バックアップの先頭行(メモ帳に貼っても「いつの・何作の」棚か分かる)。 */
export function backupHeader(items: ShelfItem[], now = new Date()): string {
  const d = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  return `MANGAL本棚 ${d} ${items.length}作`;
}

/** 棚の頁の URL(# の後ろはサーバに送られない)。 */
export function shelfCodeUrl(origin: string, code: string): string {
  return `${origin}/shelf#s=${code}`;
}

// ─── 読み込み ─────────────────────────────────────────────

const CODE_RE = /([MR]2)([zp])\.([A-Za-z0-9_-]+)\.([A-Za-z0-9_-]{4})/;

/**
 * 貼られた文字列(バックアップの全文・URL・文字列だけ・おすすめの文章)→ 棚。
 * ★寛容に読む: NFKC(全角→半角)→ 空白・改行を全部取る → 文字列を探す。 旧 v1. も読む。
 */
export async function readShelfCode(input: string, now = Date.now()): Promise<ReadResult> {
  const flat = input.normalize("NFKC").replace(/\s+/g, "");
  const m = CODE_RE.exec(flat);
  if (!m) {
    // 旧形式(v1. / 棚のURL #s=v1.…)
    const v1 = /v1\.[A-Za-z0-9_-]+/.exec(flat);
    if (v1) {
      const items = decodeShelf(v1[0], now);
      return items ? { ok: true, kind: "v1", items } : { ok: false, reason: "broken" };
    }
    // 頭は在るのに続きが崩れている(検査文字まで届かない)= 欠け
    return /[MR]2[zp]\./.test(flat) ? { ok: false, reason: "broken" } : { ok: false, reason: "none" };
  }
  const [, prefix, mode, body, check] = m;
  if (checkChars(body) !== check) return { ok: false, reason: "broken" };
  try {
    let bytes = b64urlToBytes(body);
    if (mode === "z") {
      if (!canCompress()) return { ok: false, reason: "broken" };
      bytes = await pipe(bytes, new DecompressionStream("deflate-raw"));
    }
    const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    const kind: ShelfCodeKind = prefix === "R2" ? "recommend" : "backup";
    const rows = text.split("\n").filter(Boolean).map((l) => l.split("\t"));
    const raw =
      kind === "recommend"
        ? rows.map((r) => ({ slug: r[0], shelf: "curious", edition: r[1] ?? "", addedAt: now, updatedAt: now }))
        : rows.map((r) => ({
            slug: r[0],
            shelf: CODE_SHELF[r[1] ?? ""] ?? "curious",
            owned: r[2] ? Number(r[2]) : 0,
            edition: r[3] ?? "",
            editionTotal: r[4] ? Number(r[4]) : undefined,
            addedAt: now,
            updatedAt: now,
          }));
    const items = normalizeItems(raw, now);
    return items.length ? { ok: true, kind, items } : { ok: false, reason: "broken" };
  } catch {
    return { ok: false, reason: "broken" };
  }
}

// ─── 取り込みで増えた本の印(②-5a)・バックアップの取り忘れ ─────────────
//  ★本ごとの欄は増やさない: 増えた本は addedAt を「取り込んだ時刻」にし、端末には最後の取り込み1件だけ持つ。

export const IMPORT_MARK_KEY = "mangal:shelf:import:v1";
export const BACKUP_MARK_KEY = "mangal:shelf:backup:v1";

/** 最後の取り込み(at = 増えた本の addedAt と同じ値 / n = 増えた作品数 / ack = 「確認した」を押した) */
export type ImportMark = { at: number; n: number; ack: boolean };
/** 最後のバックアップ(at = 取った時刻 / sig = その時の文字列の検査文字+長さ) */
export type BackupMark = { at: number; sig: string };

export function parseMark<T>(raw: string | null, keys: string[]): T | null {
  try {
    const v = raw ? JSON.parse(raw) : null;
    return v && typeof v === "object" && keys.every((k) => k in v) ? (v as T) : null;
  } catch {
    return null;
  }
}

/** 文字列の同一性の印(中身そのものは端末に二重に持たない) */
export function codeSig(code: string): string {
  return `${checkChars(code)}:${code.length}`;
}

/**
 * 合流で取り込む: 手元に無かった作品×版だけ「増えた本」にする(addedAt = updatedAt = now)。
 * 手元に在る作品は合流の規則(myShelf mergeSameKey)に任せる = 増えた本にしない。
 * 戻り値 added = 増えた作品数(0 なら印は付けない)。
 */
export function mergeWithMark(
  current: ShelfItem[],
  incoming: ShelfItem[],
  merge: (a: ShelfItem[], b: ShelfItem[]) => ShelfItem[],
  keyOf: (x: ShelfItem) => string,
  now: number,
): { items: ShelfItem[]; added: number } {
  const have = new Set(current.map(keyOf));
  const fresh = new Set<string>();
  const marked = incoming.map((x) => {
    const k = keyOf(x);
    if (have.has(k)) return x;
    fresh.add(k);
    return { ...x, addedAt: now, updatedAt: now };
  });
  return { items: merge(current, marked), added: fresh.size };
}
