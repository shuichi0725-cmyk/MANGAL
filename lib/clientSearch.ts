"use client";

import { kanaToRomaji, normalizeForSearch, romajiToHiragana } from "./romaji";
import type { MangaListItem } from "./schema";

/**
 * ★検索v2(2026-07-14 会議決定・穏当ルート):
 *  - 検索専用索引を廃止し一覧索引を共有。照合材料は初回1回だけここで前計算(haystack)
 *    → 以後は 1作品=1回の .includes(旧: キー入力ごとに作品ごと正規化6-10回+カナ→ローマ字変換)。
 *  - 正規化はTS一箇所(normalizeForSearch)のみ=Python側と二重実装しない(ドリフト封じ)。
 *  - 照合: ①題名系(title/kana/subtitle)+②著者を併走マージ(2026-07-19: 旧2段は作家名入り題で著者検索が沈黙) → 0なら ③別名(alt=遅延fetch)。
 *  - 逐次絞り込み: クエリが前回の延長なら前回ヒット集合内だけ再走査。
 *  - romaji列は廃止: クエリ側で romaji→かな 変換して kana と照合(逆方向 kana→romaji も照合)。
 */

/** 母音の連続を1つに圧縮(ローマ字長音ゆらぎの同一視: wanpiisu/wanpisu/wanpi-su) */
function collapseVowels(s: string): string {
  return s.replace(/([aeiou])\1+/g, "$1");
}

type Hay = { title: string[]; au: string[]; kanaRoma: string[] };
let _hay: Hay | null = null;
let _hayOf: MangaListItem[] | null = null;

let _alt: Record<string, string[]> | null = null; // slug → 別名リスト(正規化済み)
let _altInflight = false;
const _altListeners = new Set<() => void>();

function buildHay(items: MangaListItem[]): Hay {
  const title: string[] = new Array(items.length);
  const au: string[] = new Array(items.length);
  const kanaRoma: string[] = new Array(items.length);
  for (let i = 0; i < items.length; i++) {
    const m = items[i];
    title[i] = [m.title, m.title_kana, m.subtitle || ""].map(normalizeForSearch).join("");
    // 著者= 名+かな+かなのローマ字形(かな/ローマ字入力の著者検索も題名と同機構で。2026-07-19)
    au[i] = [...(m.authors || []), ...(m.original_authors || [])]
      .flatMap((a) => [
        normalizeForSearch(a.name),
        a.kana ? normalizeForSearch(a.kana) : "",
        a.kana ? collapseVowels(normalizeForSearch(kanaToRomaji(a.kana))) : "",
      ])
      .join("");
    // かな→ローマ字形(= ローマ字クエリの照合先。旧title_romaji列の代替)。
    // ★母音連続を圧縮(wanpiisu→wanpisu): 長音表記ゆらぎ(wanpi-su/wanpiisu/wanpisu)を同一視
    kanaRoma[i] = collapseVowels(normalizeForSearch(kanaToRomaji(m.title_kana || "")));
  }
  return { title, au, kanaRoma };
}

function ensureHay(items: MangaListItem[]): Hay {
  if (_hay && _hayOf === items) return _hay;
  _hay = buildHay(items);
  _hayOf = items;
  _lastQuery = ""; // 索引が替わったら絞り込みキャッシュ破棄
  _lastIdx = null;
  return _hay;
}

/** 索引ロード後の手すきで前計算を先回り(検索開始時のワンショット遅延を消す)。 */
export function prewarmSearch(items: MangaListItem[]): void {
  if (_hay && _hayOf === items) return;
  const run = () => ensureHay(items);
  if (typeof requestIdleCallback === "function") requestIdleCallback(run, { timeout: 3000 });
  else setTimeout(run, 300);
}

function fetchAlt(): void {
  if (_alt || _altInflight) return;
  _altInflight = true;
  fetch("/manga-alt-index.json")
    .then((r) => (r.ok ? r.json() : {}))
    .then((raw: Record<string, string[]>) => {
      const norm: Record<string, string[]> = {};
      for (const [slug, alts] of Object.entries(raw)) norm[slug] = alts.map(normalizeForSearch);
      _alt = norm;
      _altListeners.forEach((fn) => fn());
    })
    .catch(() => {
      _alt = {};
    });
}

/** alt(別名)到着時に再検索させたいコンポーネント用の購読。 戻り値=解除。 */
export function onAltLoaded(fn: () => void): () => void {
  _altListeners.add(fn);
  return () => _altListeners.delete(fn);
}

// 逐次絞り込みキャッシュ(クエリ延長時は前回ヒットの行だけ再走査)。
// ★①②統合走査(2026-07-19)なので延長クエリは常に前回集合の再走査で安全(③alt由来0件時は_lastIdx空=全走査に戻る)
let _lastQuery = "";
let _lastIdx: number[] | null = null;

/** クエリの照合形を作る(1クエリ1回)。 */
function queryForms(query: string): { q: string; qKana: string; qRoma: string } {
  const q = normalizeForSearch(query);
  const qKana = normalizeForSearch(romajiToHiragana(q)); // ローマ字入力→かな
  const qRoma = collapseVowels(normalizeForSearch(kanaToRomaji(query))); // かな入力→ローマ字(母音圧縮)
  return { q, qKana, qRoma };
}

/**
 * 検索本体: マッチした slug 集合を返す(一覧 filter と AND 合成して使う)。
 * ③alt は未ロード時 fetch を蹴って現時点の結果を返す(到着で onAltLoaded 通知→呼び直し)。
 */
export function searchSlugs(query: string, items: MangaListItem[]): Set<string> {
  const out = new Set<string>();
  if (!query.trim()) return out;
  const hay = ensureHay(items);
  const { q, qKana, qRoma } = queryForms(query);
  if (!q) return out;

  // 走査対象: 逐次絞り込み(前回クエリの延長なら前回ヒット行だけ再走査。①②は同一走査に統合済=単調なので常に安全)
  const scanAll = !(_lastIdx && _lastQuery && q.startsWith(_lastQuery) && q !== _lastQuery);
  const scanLen = scanAll ? items.length : (_lastIdx as number[]).length;
  const hits: number[] = [];

  // ①+② 題名系(title/kana/subtitle + かなのローマ字形)と著者を併走マージ。
  // ★旧「著者は題名ヒット0の時だけ」は、作家名が題に入る作家(高橋留美子劇場/水木しげる漫画大全集型)で
  //   著者検索が丸ごと沈黙する実害(2026-07-19ユーザ報告: 高橋留美子=題名一致のみ・永野護=正常の非対称)。
  for (let s = 0; s < scanLen; s++) {
    const i = scanAll ? s : (_lastIdx as number[])[s];
    if (
      hay.title[i].includes(q) ||
      (qKana && qKana !== q && hay.title[i].includes(qKana)) ||
      (qRoma && hay.kanaRoma[i].includes(qRoma)) ||
      hay.au[i].includes(q) ||
      (qKana && qKana !== q && hay.au[i].includes(qKana)) ||
      (qRoma && hay.au[i].includes(qRoma))
    )
      hits.push(i);
  }
  // ③ 別名・英題(まだ0の時だけ。未ロードなら fetch を蹴る=到着後に再検索される)
  if (hits.length === 0) {
    if (!_alt) fetchAlt();
    else {
      for (let i = 0; i < items.length; i++) {
        const alts = _alt[items[i].slug];
        if (alts && alts.some((a) => a.includes(q) || (qKana && a.includes(qKana)))) hits.push(i);
      }
    }
  }

  _lastQuery = q;
  _lastIdx = hits;
  for (const i of hits) out.add(items[i].slug);
  return out;
}
