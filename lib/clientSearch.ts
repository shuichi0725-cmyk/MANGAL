"use client";

import { kanaToRomaji, normalizeForSearch, romajiToHiragana } from "./romaji";
import type { MangaListItem } from "./schema";

/**
 * ★検索v2(2026-07-14 会議決定・穏当ルート) → v2.1(2026-07-21):
 *  - 検索専用索引を廃止し一覧索引を共有。照合材料は初回1回だけここで前計算(haystack)
 *    → 以後は 1作品=1回の .includes(旧: キー入力ごとに作品ごと正規化6-10回+カナ→ローマ字変換)。
 *  - 正規化はTS一箇所(normalizeForSearch)のみ=Python側と二重実装しない(ドリフト封じ)。
 *  - 照合: 題名系(title/kana/subtitle/alt)+著者を併走マージ(2026-07-19: 旧2段は作家名入り題で著者検索が沈黙)。
 *  - ★複数語AND(2026-07-21): 空白区切りの各語をANDで照合(「ワンピース 尾田」型。旧実装は
 *    正規化が空白を全削除し連結1語として照合=2語クエリが全滅していた)。
 *  - ★alt(別名・英題)は常時マージ(2026-07-21): 初回検索時に遅延fetchし、到着後は haystack に
 *    畳み込んで題名と同格で照合(旧「ヒット0の時だけ別走査」は、片語が題名・片語がaltの
 *    AND検索や、題名にも当たる語のalt作品を取りこぼす)。
 *  - 逐次絞り込み: クエリが前回の延長なら前回ヒット集合内だけ再走査(AND照合は単調なので安全)。
 *  - romaji列は廃止: クエリ側で romaji→かな 変換して kana と照合(逆方向 kana→romaji も照合)。
 */

/** 母音の連続を1つに圧縮(ローマ字長音ゆらぎの同一視: wanpiisu/wanpisu/wanpi-su) */
function collapseVowels(s: string): string {
  return s.replace(/([aeiou])\1+/g, "$1");
}

type Hay = { title: string[]; au: string[]; kanaRoma: string[]; t0: string[]; k0: string[] };
let _hay: Hay | null = null;
let _hayOf: MangaListItem[] | null = null;
let _hayAltV = -1; // hayに畳み込み済みのaltバージョン

let _alt: Record<string, string[]> | null = null; // slug → 別名リスト(正規化済み)
let _altV = 0; // altが届く/差し替わる度に+1(=hay再構築の合図)
let _altInflight = false;
const _altListeners = new Set<() => void>();

function buildHay(items: MangaListItem[]): Hay {
  const title: string[] = new Array(items.length);
  const au: string[] = new Array(items.length);
  const kanaRoma: string[] = new Array(items.length);
  const t0: string[] = new Array(items.length); // 正規化title単体(完全/前方一致tier判定用 2026-07-23)
  const k0: string[] = new Array(items.length); // 正規化kana単体
  for (let i = 0; i < items.length; i++) {
    const m = items[i];
    const alts = _alt ? _alt[m.slug] : undefined;
    // 題名系 = title/kana/subtitle + alt(別名・英題。ロード済みなら常時同格で照合)
    title[i] =
      [m.title, m.title_kana, m.subtitle || ""].map(normalizeForSearch).join("") +
      (alts ? alts.join("") : "");
    // 著者= 名+かな+かなのローマ字形(かな/ローマ字入力の著者検索も題名と同機構で。2026-07-19)
    au[i] = [...(m.authors || []), ...(m.original_authors || [])]
      .flatMap((a) => [
        normalizeForSearch(a.name),
        a.kana ? normalizeForSearch(a.kana) : "",
        a.kana ? collapseVowels(normalizeForSearch(kanaToRomaji(a.kana))) : "",
      ])
      .join("");
    // かな→ローマ字形(= ローマ字クエリの照合先。旧title_romaji列の代替)。
    // ★母音連続を圧縮(wanpiisu→wanpisu): 長音表記ゆらぎ(wanpi-su/wanpiisu/wanpisu)を同一視
    kanaRoma[i] = collapseVowels(normalizeForSearch(kanaToRomaji(m.title_kana || "")));
    t0[i] = normalizeForSearch(m.title);
    k0[i] = normalizeForSearch(m.title_kana || "");
  }
  return { title, au, kanaRoma, t0, k0 };
}

function ensureHay(items: MangaListItem[]): Hay {
  if (_hay && _hayOf === items && _hayAltV === _altV) return _hay;
  _hay = buildHay(items);
  _hayOf = items;
  _hayAltV = _altV;
  _lastKey = ""; // 索引が替わったら絞り込みキャッシュ破棄
  _lastIdx = null;
  return _hay;
}

/** 索引ロード後の手すきで前計算を先回り(検索開始時のワンショット遅延を消す)。 */
export function prewarmSearch(items: MangaListItem[]): void {
  if (_hay && _hayOf === items && _hayAltV === _altV) return;
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
      _altV++;
      _altListeners.forEach((fn) => fn());
    })
    .catch(() => {
      _alt = {};
    });
}

/** テスト用: alt索引を直接注入(fetch不要)。nullで未ロード状態に戻す。 */
export function __setAltIndexForTest(raw: Record<string, string[]> | null): void {
  if (raw === null) {
    _alt = null;
  } else {
    const norm: Record<string, string[]> = {};
    for (const [slug, alts] of Object.entries(raw)) norm[slug] = alts.map(normalizeForSearch);
    _alt = norm;
  }
  _altV++;
}

/** alt(別名)到着時に再検索させたいコンポーネント用の購読。 戻り値=解除。 */
export function onAltLoaded(fn: () => void): () => void {
  _altListeners.add(fn);
  return () => _altListeners.delete(fn);
}

// 逐次絞り込みキャッシュ(クエリ延長時は前回ヒットの行だけ再走査)。
// AND照合は各語・語追加とも単調(ヒット集合は縮むだけ)なので延長判定は正規化語連結キーで安全。
let _lastKey = "";
let _lastIdx: number[] | null = null;

type Forms = { q: string; qKana: string; qRoma: string; jp: boolean };

/** 1語ぶんの照合形を作る(1クエリ1回)。 */
function tokenForms(token: string): Forms {
  const q = normalizeForSearch(token);
  // ★案B(2026-07-23 ユーザ裁定): かな/漢字を含む語はローマ字橋を使わない。
  //   橋はローマ字入力者のための機能で、日本語入力に適用すると「イース」→isu が
  //   arisu/ofisu 等に爆発ヒットする(実測: イース3,522件→835件)。
  const jp = /[ぁ-んァ-ヶ一-龯々ゝゞ]/.test(token);
  const qKana = normalizeForSearch(romajiToHiragana(q)); // ローマ字入力→かな
  const qRoma = jp ? "" : collapseVowels(normalizeForSearch(kanaToRomaji(token))); // かな入力→ローマ字(母音圧縮)
  return { q, qKana, qRoma, jp };
}

/** 1作品×1語の照合。戻り値=一致した経路の強さ(0=不一致 / 1=題名系 / 2=著者 / 3=ローマ字橋)。 */
function rowMatchTier(hay: Hay, i: number, f: Forms): number {
  if (hay.title[i].includes(f.q) || (f.qKana && f.qKana !== f.q && hay.title[i].includes(f.qKana))) return 1;
  if (hay.au[i].includes(f.q) || (f.qKana && f.qKana !== f.q && hay.au[i].includes(f.qKana))) return 2;
  if (f.qRoma && (hay.kanaRoma[i].includes(f.qRoma) || hay.au[i].includes(f.qRoma))) return 3;
  return 0;
}

/**
 * ★検索本体v2.2(2026-07-23 案A): マッチした slug → 一致tier の Map を返す。
 * tier(小さいほど強い): 0=完全一致(題orかな) / 1=前方一致 / 2=題名系部分一致 /
 * 3=著者一致 / 4=ローマ字橋のみ。複数語は「最弱の語」のtier(AND全語の支えの強さ)。
 * 呼び手は検索中かつ並び順既定の時に tier で安定ソートする(同tier内=従来順)。
 * alt は初回検索で遅延fetch(到着で onAltLoaded 通知→呼び直し→hayに畳み込み済みで照合)。
 */
export function searchWithTiers(query: string, items: MangaListItem[]): Map<string, number> {
  const out = new Map<string, number>();
  const tokens = query.trim().split(/\s+/).filter(Boolean);
  if (!tokens.length) return out;
  if (!_alt) fetchAlt(); // 検索する人だけaltを読む(一覧閲覧のみの人に3MBを課さない)
  const hay = ensureHay(items);
  const forms = tokens.map(tokenForms).filter((f) => f.q);
  if (!forms.length) return out;
  const fullQ = normalizeForSearch(query); // 完全/前方一致は全文で判定(空白は正規化で消える)

  // 走査対象: 逐次絞り込み(前回クエリの延長なら前回ヒット行だけ再走査)
  const key = forms.map((f) => f.q).join(" ");
  const scanAll = !(_lastIdx && _lastKey && key.startsWith(_lastKey) && key !== _lastKey);
  const scanLen = scanAll ? items.length : (_lastIdx as number[]).length;
  const hits: number[] = [];

  for (let s = 0; s < scanLen; s++) {
    const i = scanAll ? s : (_lastIdx as number[])[s];
    let worst = 0; // 語ごとの最弱経路
    let ok = true;
    for (const f of forms) {
      const tr = rowMatchTier(hay, i, f);
      if (!tr) {
        ok = false;
        break;
      }
      if (tr > worst) worst = tr;
    }
    if (!ok) continue;
    hits.push(i);
    // tier確定: 完全一致(0)/前方一致(1)は全文×題/かな単体で判定、以外は経路tier+1(2..4)
    let tier: number;
    if (hay.t0[i] === fullQ || hay.k0[i] === fullQ) tier = 0;
    else if (fullQ && (hay.t0[i].startsWith(fullQ) || hay.k0[i].startsWith(fullQ))) tier = 1;
    else tier = worst + 1; // 1→2(題部分一致), 2→3(著者), 3→4(ローマ字橋)
    out.set(items[i].slug, tier);
  }

  _lastKey = key;
  _lastIdx = hits;
  return out;
}

/** 互換API: マッチした slug 集合(一覧 filter と AND 合成して使う)。 */
export function searchSlugs(query: string, items: MangaListItem[]): Set<string> {
  return new Set(searchWithTiers(query, items).keys());
}
