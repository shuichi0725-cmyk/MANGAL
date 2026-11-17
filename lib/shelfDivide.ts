/**
 * 本棚の「自動の仕切り」(2026-11-17 見本①)= 棚の中を作品データで区切って並べる。 入力ゼロ・保存データも増えない。
 * 仕切り = 続き・状態 / ジャンル / 著者 / 出版社 / 50音(どれにするかは端末に覚える)。
 * ★1作品は1か所にだけ出す(ジャンルのように複数持つ物は、この棚でいちばん多い仕切りへ寄せる)。
 */

export type DivideMode = "none" | "state" | "genre" | "author" | "publisher" | "kana";

export const DIVIDE_MODES: { id: DivideMode; label: string }[] = [
  { id: "none", label: "なし" },
  { id: "state", label: "続き・状態" },
  { id: "genre", label: "ジャンル" },
  { id: "author", label: "著者" },
  { id: "publisher", label: "出版社" },
  { id: "kana", label: "50音" },
];
export const DIVIDE_KEY = "mangal:shelf:divide";
export const isDivideMode = (v: unknown): v is DivideMode => DIVIDE_MODES.some((d) => d.id === v);

/** 仕切りに使う作品の事実(索引から引けない作品 = m なし) */
export type DivideFacts = {
  status?: string;
  genres?: string[];
  author?: { name: string; kana?: string } | null;
  publisher?: string;
  titleKana?: string;
};
export type DivideEntry<T> = {
  value: T;
  facts: DivideFacts | null;
  /** もってるの札の種類(lib/myShelf ownedNote の kind)。 もってる以外は null */
  noteKind: string | null;
};
export type DivideSection<T> = { id: string; label: string; entries: DivideEntry<T>[] };

const STATE_ORDER = ["behind", "caught-up", "complete", "ongoing", "completed", "hiatus", "unknown", "lost"];
const STATE_LABEL: Record<string, string> = {
  behind: "続きの巻あり",
  "caught-up": "連載中・最新巻まで所持",
  complete: "完結・全巻所持",
  ongoing: "連載中",
  completed: "完結",
  hiatus: "休載中",
  unknown: "巻数の記録なし",
  lost: "見つからない作品",
};

const KANA_ROWS: [string, string][] = [
  ["ア", "アイウエオァィゥェォヴ"],
  ["カ", "カキクケコヵヶ"],
  ["サ", "サシスセソ"],
  ["タ", "タチツテトッ"],
  ["ナ", "ナニヌネノ"],
  ["ハ", "ハヒフヘホ"],
  ["マ", "マミムメモ"],
  ["ヤ", "ヤユヨャュョ"],
  ["ラ", "ラリルレロ"],
  ["ワ", "ワヲンヮ"],
];

/** 題名ヨミの頭の文字 → 行(ア行…ワ行 / 英数・記号)。 ひらがな・濁点・半角も同じ行に寄せる。 */
export function kanaRow(kana: string | undefined): string {
  const c0 = (kana ?? "").normalize("NFKC").trim().charAt(0);
  if (!c0) return "英数・記号";
  let c = c0.normalize("NFD").charAt(0);
  const code = c.charCodeAt(0);
  if (code >= 0x3041 && code <= 0x3096) c = String.fromCharCode(code + 0x60); // ひらがな → カタカナ
  for (const [row, chars] of KANA_ROWS) if (chars.includes(c)) return `${row}行`;
  return "英数・記号";
}

function stateOf<T>(e: DivideEntry<T>): string {
  if (e.noteKind) return e.noteKind === "complete-behind" ? "behind" : e.noteKind;
  if (!e.facts) return "lost";
  return e.facts.status && STATE_LABEL[e.facts.status] ? e.facts.status : "unknown";
}

function bucket<T>(entries: DivideEntry<T>[], keyOf: (e: DivideEntry<T>) => string): Map<string, DivideEntry<T>[]> {
  const m = new Map<string, DivideEntry<T>[]>();
  for (const e of entries) {
    const k = keyOf(e);
    const g = m.get(k);
    if (g) g.push(e);
    else m.set(k, [e]);
  }
  return m;
}

const LAST = "￿"; // 「不明」等の仕切りを最後へ

/**
 * 仕切る。 並びの中の順(入力の順)は各仕切りの中でも保つ。
 * genreName / publisherName = 表示名(無ければ key のまま)。
 */
export function divide<T>(
  entries: DivideEntry<T>[],
  mode: DivideMode,
  names: { genre?: (k: string) => string | undefined; publisher?: (k: string) => string | undefined } = {},
): DivideSection<T>[] {
  if (mode === "none" || !entries.length) return [{ id: "all", label: "", entries }];

  if (mode === "state") {
    const m = bucket(entries, stateOf);
    return STATE_ORDER.filter((k) => m.has(k)).map((k) => ({ id: k, label: STATE_LABEL[k], entries: m.get(k)! }));
  }

  if (mode === "genre") {
    // この棚でいちばん多いジャンルへ寄せる(同数はジャンル名の順)
    const count = new Map<string, number>();
    for (const e of entries) for (const g of e.facts?.genres ?? []) count.set(g, (count.get(g) ?? 0) + 1);
    const nameOf = (g: string) => names.genre?.(g) ?? g;
    const pick = (e: DivideEntry<T>) => {
      const gs = e.facts?.genres ?? [];
      if (!gs.length) return LAST;
      return [...gs].sort((a, b) => count.get(b)! - count.get(a)! || nameOf(a).localeCompare(nameOf(b), "ja"))[0];
    };
    const m = bucket(entries, pick);
    return [...m.entries()]
      .sort(([a, x], [b, y]) => (a === LAST ? 1 : b === LAST ? -1 : y.length - x.length || nameOf(a).localeCompare(nameOf(b), "ja")))
      .map(([k, es]) => ({ id: `g:${k}`, label: k === LAST ? "ジャンル未設定" : nameOf(k), entries: es }));
  }

  if (mode === "author") {
    const m = bucket(entries, (e) => e.facts?.author?.name || LAST);
    const kanaOf = new Map(entries.map((e) => [e.facts?.author?.name || LAST, e.facts?.author?.kana || e.facts?.author?.name || LAST]));
    return [...m.entries()]
      .sort(([a], [b]) => (a === LAST ? 1 : b === LAST ? -1 : kanaOf.get(a)!.localeCompare(kanaOf.get(b)!, "ja")))
      .map(([k, es]) => ({ id: `a:${k}`, label: k === LAST ? "著者不明" : k, entries: es }));
  }

  if (mode === "publisher") {
    const nameOf = (p: string) => names.publisher?.(p) ?? p;
    const m = bucket(entries, (e) => e.facts?.publisher || LAST);
    return [...m.entries()]
      .sort(([a, x], [b, y]) => (a === LAST ? 1 : b === LAST ? -1 : y.length - x.length || nameOf(a).localeCompare(nameOf(b), "ja")))
      .map(([k, es]) => ({ id: `p:${k}`, label: k === LAST ? "出版社不明" : nameOf(k), entries: es }));
  }

  // kana: 行ごと・行の中は題名ヨミ順
  const rows = [...KANA_ROWS.map(([r]) => `${r}行`), "英数・記号"];
  const m = bucket(entries, (e) => kanaRow(e.facts?.titleKana));
  return rows
    .filter((r) => m.has(r))
    .map((r) => ({
      id: `k:${r}`,
      label: r,
      entries: [...m.get(r)!].sort((a, b) => (a.facts?.titleKana ?? "").localeCompare(b.facts?.titleKana ?? "", "ja")),
    }));
}
