"use client";

import { nowMs, perfDiag, since } from "./perfDiag";
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

/** ★曖昧部分一致(2026-08-12 ユーザ報告「ぎゃわんぶらー」で0件): Wu-Manber bitap。
 *  pattern が text の中に「編集距離k以内の部分文字列」として現れるかを O(text長×k) で判定。
 *  厳密検索がヒット0の時だけのフォールバック専用(平常時のコストはゼロ)。pattern≤31字(bitマスク上限)。 */
function fuzzyIncludes(text: string, pattern: string, k: number): boolean {
  const m = pattern.length;
  if (m === 0 || m > 31 || text.length === 0) return false;
  const alpha = new Map<string, number>();
  for (let i = 0; i < m; i++) alpha.set(pattern[i], (alpha.get(pattern[i]) ?? 0) | (1 << i));
  const accept = 1 << (m - 1);
  const R: number[] = new Array(k + 1).fill(0);
  for (let j = 0; j < text.length; j++) {
    const cm = alpha.get(text[j]) ?? 0;
    let prevOld = R[0]; // R[d-1] の更新前の値
    R[0] = (((R[0] << 1) | 1) & cm) >>> 0;
    for (let d = 1; d <= k; d++) {
      const old = R[d];
      // 一致 | 置換(prevOld<<1) | 挿入(prevOld) | 削除(R[d-1]新<<1)
      R[d] = (((((old << 1) | 1) & cm) | prevOld | (prevOld << 1) | (R[d - 1] << 1) | 1) >>> 0);
      prevOld = old;
    }
    if (R[k] & accept) return true;
  }
  return false;
}

type Hay = { title: string[]; au: string[]; kanaRoma: string[]; t0: string[]; k0: string[] };
let _hay: Hay | null = null;
let _hayOf: MangaListItem[] | null = null;
let _hayAltV = -1; // hayに畳み込み済みのaltバージョン
let _hayHasAlt = false; // 現hayに別名を畳み込み済みか(=追記だけで更新できるかの判定)

let _alt: Record<string, string[]> | null = null; // slug → 別名リスト(正規化済み)
let _altV = 0; // altが届く/差し替わる度に+1(=hay再構築の合図)
let _altInflight = false;
const _altListeners = new Set<() => void>();

/** hayの器だけ用意する(中身は fillHay が埋める)。 */
function allocHay(n: number): Hay {
  return {
    title: new Array(n).fill(""),
    au: new Array(n).fill(""),
    kanaRoma: new Array(n).fill(""),
    t0: new Array(n).fill(""), // 正規化title単体(完全/前方一致tier判定用 2026-07-23)
    k0: new Array(n).fill(""), // 正規化kana単体
  };
}

/** hayの [from, to) 行ぶんを埋める。呼んだ時点の _alt を畳み込む。 */
function fillHay(items: MangaListItem[], hay: Hay, from: number, to: number): void {
  for (let i = from; i < to; i++) {
    const m = items[i];
    const alts = _alt ? _alt[m.slug] : undefined;
    // ★t0/k0 は題名欄の材料と同一なので使い回す(2026-08-01: 旧実装は同じ
    //   normalizeForSearch を1行につき2回よけいに呼んでいた)。
    const nTitle = normalizeForSearch(m.title);
    const nKana = normalizeForSearch(m.title_kana || "");
    // 題名系 = title/kana/subtitle + alt(別名・英題。ロード済みなら常時同格で照合)
    hay.title[i] =
      nTitle + nKana + normalizeForSearch(m.subtitle || "") + (alts ? alts.join("") : "");
    // 著者= 名+かな+かなのローマ字形(かな/ローマ字入力の著者検索も題名と同機構で。2026-07-19)
    hay.au[i] = [...(m.authors || []), ...(m.original_authors || [])]
      .flatMap((a) => [
        normalizeForSearch(a.name),
        a.kana ? normalizeForSearch(a.kana) : "",
        a.kana ? collapseVowels(normalizeForSearch(kanaToRomaji(a.kana))) : "",
      ])
      .join("");
    // かな→ローマ字形(= ローマ字クエリの照合先。旧title_romaji列の代替)。
    // ★母音連続を圧縮(wanpiisu→wanpisu): 長音表記ゆらぎ(wanpi-su/wanpiisu/wanpisu)を同一視
    hay.kanaRoma[i] = collapseVowels(normalizeForSearch(kanaToRomaji(m.title_kana || "")));
    hay.t0[i] = nTitle;
    hay.k0[i] = nKana;
  }
}

/**
 * ★haystackは「細切れに前計算」する(2026-08-01)。
 *
 * 旧: prewarmSearch が requestIdleCallback の中で67k件を一気に構築していた。
 * idle に載せても★1本の巨大タスク★なので、走り出したら主スレッドは最後まで返らない
 * (本番実測4.5秒。初期表示の直後に固まる体感の正体)。
 * 新: 器だけ先に作り、空き時間の許す範囲で行を埋め、足りなければ次の空き時間へ回す。
 * 埋まりきる前に検索が来たら、その場で残りを同期で埋める(結果は常に完全)。
 */
// 1回の刻み幅。空き時間が続く限り下の do-while が続けて回すので、小さくしても総量は変わらず、
// 「一区切りの長さ」だけが短くなる(=描画が詰まらない)。本番実測で500行あたり約20ms。
const FILL_CHUNK = 500;
let _hayFilled = 0; // 先頭から何行ぶん埋まっているか
let _fillScheduled = false;

function scheduleFill(items: MangaListItem[]): void {
  if (_fillScheduled) return;
  _fillScheduled = true;
  const step = (deadline?: { timeRemaining: () => number }) => {
    _fillScheduled = false;
    if (!_hay || _hayOf !== items) return; // 索引が差し替わった=この前計算は用済み
    const t0 = nowMs();
    const from0 = _hayFilled;
    do {
      const to = Math.min(_hayFilled + FILL_CHUNK, items.length);
      fillHay(items, _hay, _hayFilled, to);
      _hayFilled = to;
    } while (_hayFilled < items.length && deadline && deadline.timeRemaining() > 4);
    perfDiag.hayIdleMs += since(t0);
    perfDiag.hayIdleRows += _hayFilled - from0;
    if (_hayFilled < items.length) scheduleFill(items);
  };
  if (typeof requestIdleCallback === "function") requestIdleCallback(step, { timeout: 3000 });
  else setTimeout(step, 0);
}

function ensureHay(items: MangaListItem[]): Hay {
  // 器が無い/索引が別物 → 作り直し
  if (!_hay || _hayOf !== items) {
    _hay = allocHay(items.length);
    _hayOf = items;
    _hayFilled = 0;
    _hayAltV = _altV;
    _hayHasAlt = !!_alt;
    _lastKey = ""; // 索引が替わったら絞り込みキャッシュ破棄
    _lastIdx = null;
  } else if (_hayAltV !== _altV) {
    // ★alt到着だけなら題名欄に追記して済ませる(2026-08-01)。
    //   旧: altが届くたび67k件を全再計算していた(本番実測5.1秒)。これが「検索して件数が
    //   出た直後にまた固まる」体感の主因。alt は題名系の照合材料を★増やす方向にしか
    //   働かない★ので、未畳み込みのhayには文字列追記だけで等価な結果になる。
    //   まだ埋めていない行は fillHay が最新の _alt を見て畳み込むので触らなくてよい。
    if (!_hayHasAlt && _alt) {
      for (let i = 0; i < _hayFilled; i++) {
        const alts = _alt[items[i].slug];
        if (alts && alts.length) _hay.title[i] += alts.join("");
      }
      _hayHasAlt = true;
    } else {
      // 別名の差し替え(テスト注入・再fetch)は追記では表せない → 全部作り直す
      _hay = allocHay(items.length);
      _hayFilled = 0;
      _hayHasAlt = !!_alt;
    }
    _hayAltV = _altV;
    _lastKey = ""; // 照合材料が変わった=前回ヒット外にも当たりうる。絞り込みキャッシュ破棄
    _lastIdx = null;
  }
  // 前計算が追いついていなければ、ここで残りを同期で埋める(検索結果は常に完全)
  if (_hayFilled < items.length) {
    // ★ここが「検索を押した瞬間の固まり」。実機の数字を採るため計測する(perfDiag)
    const t0 = nowMs();
    const n = items.length - _hayFilled;
    fillHay(items, _hay, _hayFilled, items.length);
    _hayFilled = items.length;
    perfDiag.haySyncMs += since(t0);
    perfDiag.haySyncRows += n;
  }
  return _hay;
}

/** 索引ロード後の手すきで前計算を先回り(検索開始時のワンショット遅延を消す)。 */
export function prewarmSearch(items: MangaListItem[]): void {
  if (_hay && _hayOf === items && _hayAltV === _altV && _hayFilled === items.length) return;
  if (!_hay || _hayOf !== items) {
    _hay = allocHay(items.length);
    _hayOf = items;
    _hayFilled = 0;
    _hayAltV = _altV;
    _hayHasAlt = !!_alt;
    _lastKey = "";
    _lastIdx = null;
  }
  scheduleFill(items);
}

function fetchAlt(): void {
  if (_alt || _altInflight) return;
  _altInflight = true;
  const _tAlt = nowMs();
  fetch("/manga-alt-index.json")
    .then((r) => (r.ok ? r.json() : {}))
    .then((raw: Record<string, string[]>) => {
      const norm: Record<string, string[]> = {};
      for (const [slug, alts] of Object.entries(raw)) norm[slug] = alts.map(normalizeForSearch);
      _alt = norm;
      _altV++;
      perfDiag.altFetchMs = since(_tAlt);
      _altListeners.forEach((fn) => fn());
    })
    .catch(() => {
      _alt = {};
    });
}

/** ホーム到着ウォーム用(2026-08-31): 別名索引を先読みし、初回検索後の後追い再照合を無くす。冪等。 */
export function prewarmAlt(): void {
  fetchAlt();
}

/** alt索引(別名)を取得中か(=題名ヒット0の直後、別名での再照合がまだ終わっていない)。
 *  検索UIが「0件」と断言してよいかの判定に使う(2026-08-18 偽0件対策=B案)。 */
export function isAltLoading(): boolean {
  return _altInflight && _alt === null;
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

/** テスト用: 逐次絞り込みキャッシュだけを捨てる(haystackは作り直さない)。
 *  スナップショット試験で「クエリを毎回まっさらな状態から引いた結果」を得るために使う。 */
export function __resetSearchCacheForTest(): void {
  _lastKey = "";
  _lastIdx = null;
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
  const _t0 = nowMs();
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

  // ★曖昧フォールバック(2026-08-12): 厳密照合が0件の時だけ、編集距離1〜2の近似部分一致を全行走査。
  //   tier=5(最弱)。単語1語×正規化4字以上のみ(短語は誤爆が多すぎる)。多語ANDは対象外。
  //   逐次絞り込みキャッシュは残さない(曖昧ヒット集合は延長クエリの上位集合と保証できないため)。
  if (out.size === 0 && forms.length === 1) {
    const f = forms[0];
    const pat = f.q.slice(0, 31);
    const k = pat.length >= 8 ? 2 : pat.length >= 4 ? 1 : 0;
    if (k > 0) {
      const patKana = f.qKana && f.qKana !== f.q ? f.qKana.slice(0, 31) : "";
      const patRoma = f.qRoma ? f.qRoma.slice(0, 31) : "";
      for (let i = 0; i < items.length; i++) {
        if (
          fuzzyIncludes(hay.title[i], pat, k) ||
          (patKana && fuzzyIncludes(hay.title[i], patKana, k)) ||
          (patRoma && fuzzyIncludes(hay.kanaRoma[i], patRoma, k))
        ) {
          out.set(items[i].slug, 5);
        }
      }
      if (out.size > 0) {
        _lastKey = "";
        _lastIdx = null;
        perfDiag.searchMs = since(_t0);
        perfDiag.searchHits = out.size;
        return out;
      }
    }
  }

  _lastKey = key;
  _lastIdx = hits;
  perfDiag.searchMs = since(_t0);
  perfDiag.searchHits = out.size;
  return out;
}

/** 互換API: マッチした slug 集合(一覧 filter と AND 合成して使う)。 */
export function searchSlugs(query: string, items: MangaListItem[]): Set<string> {
  return new Set(searchWithTiers(query, items).keys());
}
