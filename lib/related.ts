import type { Manga } from "./schema";

/** 関連作品の選定ロジック(表示は components/RelatedWorks.tsx)。
 *  ①シリーズ/フランチャイズ(題名の前方一致) ②同作者(作画/原作の名前共有) ③pin。
 *  ★2026-08-31 SEO: 強シグナルが乏しい頁(約8%は0件=孤立頁)への穴埋め層を追加
 *  (同誌→同ジャンルを発表年の近い順で充填=全頁を作品間リンク網に入れる)。
 *  vitest から import できるよう .tsx から分離(vitest は JSX 変換なし構成)。 */
export function computeRelated(manga: Manga, all: Manga[], limit = 10) {
  // ★空白違いの同一人物を束ねる(authorKey相当。蟹沢ちひろ分裂対策 2026-07-21)
  const nk = (s: string) => s.replace(/[\s　]+/g, "");
  const names = new Set(
    [...manga.authors, ...manga.original_authors].map((a) => nk(a.name)),
  );
  // ★多人数名義ガード(2026-07-15 ソーサリアン型=単巻読切連番の統合頁・著者14人):
  //   著者5人以上の頁は「同作者」スコアを使わない(各作家の全作品が無関係に並ぶため)。pin/シリーズ一致のみ。
  const manyAuthors = names.size >= 5;
  const t = manga.title;
  // ★pin: related_pin の slug は順序保持で最優先(例: ドラえもん→大長編ドラえもん)
  const pinRank = new Map((manga.related_pin ?? []).map((s, i) => [s, i]));
  const scored: Array<{ m: Manga; score: number; why: string }> = [];
  for (const m of all) {
    if (m.slug === manga.slug) continue;
    if (pinRank.has(m.slug)) {
      scored.push({ m, score: 1000 - (pinRank.get(m.slug) ?? 0), why: "シリーズ" });
      continue;
    }
    let score = 0;
    let why = "";
    // シリーズ/スピンオフ = 題名の前方一致(4字以上)
    const pre = t.length >= 4 && m.title.startsWith(t.slice(0, Math.min(t.length, 6)));
    const pre2 = m.title.length >= 4 && t.startsWith(m.title.slice(0, Math.min(m.title.length, 6)));
    if (pre || pre2) {
      score += 10;
      why = "シリーズ";
    }
    const shared = !manyAuthors && [...m.authors, ...m.original_authors].some((a) => names.has(nk(a.name)));
    if (shared) {
      score += 5;
      if (!why) why = "同作者";
    }
    if (score > 0) scored.push({ m, score, why });
  }
  scored.sort((a, b) => b.score - a.score || (b.m.year_started ?? 0) - (a.m.year_started ?? 0));
  const strong = scored.slice(0, limit);
  // ★穴埋め(2026-08-31 SEO): 同誌→同ジャンルを「発表年の近い順」で充填。
  //   人気順でなく年の近さで選ぶ=有名作へのリンク集中を避け、無名頁にも被リンクが回る。
  if (strong.length >= FILL_TO) return strong;
  const { byMag, byGenre } = fillBuckets(all);
  const have = new Set(strong.map((s) => s.m.slug));
  have.add(manga.slug);
  const year = manga.year_started ?? 9999;
  const take = (m: Manga) => {
    if (have.has(m.slug)) return false;
    have.add(m.slug);
    return true;
  };
  const filled = [...strong];
  if (manga.magazine) {
    for (const m of nearestByYear(byMag.get(manga.magazine) ?? [], year, take, FILL_TO - filled.length))
      filled.push({ m, score: 1, why: "同誌" });
  }
  for (const g of manga.genres ?? []) {
    if (filled.length >= FILL_TO) break;
    for (const m of nearestByYear(byGenre.get(g) ?? [], year, take, FILL_TO - filled.length))
      filled.push({ m, score: 1, why: "同ジャンル" });
  }
  return filled;
}

/** 穴埋めが目指す件数(強シグナルがこれ以上あれば充填しない) */
const FILL_TO = 8;

/** 同誌/同ジャンルの年ソート済みバケット(module cache = 66kビルドで1回だけ構築)。
 *  ★per-page で全走査ソートすると 66k頁ビルドが数十分伸びるため、
 *  事前ソート+二分探索(nearestByYear)で1頁あたり O(log n + k) に抑える。 */
let _fillCache: { src: Manga[]; byMag: Map<string, Manga[]>; byGenre: Map<string, Manga[]> } | null = null;

function fillBuckets(all: Manga[]) {
  if (_fillCache && _fillCache.src === all) return _fillCache;
  const byMag = new Map<string, Manga[]>();
  const byGenre = new Map<string, Manga[]>();
  for (const m of all) {
    if (m.magazine) {
      const a = byMag.get(m.magazine);
      if (a) a.push(m);
      else byMag.set(m.magazine, [m]);
    }
    for (const g of m.genres ?? []) {
      const a = byGenre.get(g);
      if (a) a.push(m);
      else byGenre.set(g, [m]);
    }
  }
  // 決定的順序: 年→slug(ビルドごとに関連欄が揺れない)
  const cmp = (a: Manga, b: Manga) =>
    (a.year_started ?? 9999) - (b.year_started ?? 9999) || (a.slug < b.slug ? -1 : 1);
  for (const arr of byMag.values()) arr.sort(cmp);
  for (const arr of byGenre.values()) arr.sort(cmp);
  _fillCache = { src: all, byMag, byGenre };
  return _fillCache;
}

/** 年ソート済み配列から year に近い順に want 件拾う(二分探索+両側展開)。 */
function nearestByYear(arr: Manga[], year: number, take: (m: Manga) => boolean, want: number): Manga[] {
  if (want <= 0 || arr.length === 0) return [];
  let lo = 0;
  let hi = arr.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if ((arr[mid].year_started ?? 9999) < year) lo = mid + 1;
    else hi = mid;
  }
  const out: Manga[] = [];
  let l = lo - 1;
  let r = lo;
  while (out.length < want && (l >= 0 || r < arr.length)) {
    const dl = l >= 0 ? Math.abs((arr[l].year_started ?? 9999) - year) : Infinity;
    const dr = r < arr.length ? Math.abs((arr[r].year_started ?? 9999) - year) : Infinity;
    if (dr <= dl) {
      if (take(arr[r])) out.push(arr[r]);
      r++;
    } else {
      if (take(arr[l])) out.push(arr[l]);
      l--;
    }
  }
  return out;
}
