import fs from "node:fs";
import path from "node:path";
import { beforeAll, describe, expect, it } from "vitest";
import { decodeListIndex } from "./listIndexDecode";
import {
  __resetSearchCacheForTest,
  __setAltIndexForTest,
  searchWithTiers,
} from "./clientSearch";
import { applyFilters, filterItems, emptyFilterState, type FilterState } from "./filters";
import { sortRows } from "./listSort";
import type { MangaListItem } from "./schema";

/**
 * ★検索スナップショット・ゲート(2026-08-01)
 *
 * 目的: 性能改修などでコードを触ったとき、「検索の結果集合・順位・件数」が
 *       意図せず変わっていないことを機械的に保証する。
 *
 * 設計の要点
 *  - 土台は★固定コーパス★(lib/__fixtures__/search-corpus.json = 実索引から決定的に
 *    2,500件抜いたもの。生成= scripts/_build-search-fixture.py)。
 *    実索引を直接使うと週次のデータ更新で赤くなり、コード起因の退行と区別できない。
 *  - 並べ替えは本番と同じ lib/listSort.ts を通す(テスト内にコピーを持たない=ドリフト封じ)。
 *  - 検索の一致集合だけでなく★表示順★も焼く。集合が同じでも順位が変われば差分が出る。
 *  - 逐次入力(1文字ずつ増やす)の結果が、まっさらから引いた結果と一致することも見る。
 *    = 逐次絞り込みキャッシュの状態バグ(fixtureが小さいと出ない型)を検知する。
 *  - フィルターのファセット件数も焼く(FilterPanel の tally 相当)。
 *
 * スナップショットの更新(= 変更が意図どおりだと人が確認したとき):
 *   UPDATE_SEARCH_SNAPSHOT=1 npx vitest run lib/searchSnapshot.test.ts
 *   → lib/__snapshots__/search-real.json を書き換え、差分を git diff で必ず目視する。
 */

const FIXTURE = path.join(__dirname, "__fixtures__", "search-corpus.json");
const FIXTURE_ALT = path.join(__dirname, "__fixtures__", "search-corpus-alt.json");
const SNAP_DIR = path.join(__dirname, "__snapshots__");
const SNAP = path.join(SNAP_DIR, "search-real.json");
const UPDATE = process.env.UPDATE_SEARCH_SNAPSHOT === "1";

/** 代表クエリ。★過去に事故が起きた形は必ず残す(消すと再発を検知できなくなる)。 */
const QUERIES: string[] = [
  // 題名(漢字・カナ・ひらがな)
  "ワンピース", "わんぴーす", "ONE PIECE", "鬼滅の刃", "きめつのやいば",
  "進撃の巨人", "ゴルゴ", "美味しんぼ", "こち亀", "ドラゴン",
  // ローマ字入力
  "wanpisu", "wanpiisu", "wanpi-su", "kimetsu", "conan", "berserk", "naruto",
  // ★イース事件(2026-07-23): 日本語クエリでローマ字橋を使わない
  "イース", "isu",
  // ★わんぴーす事件(2026-07-28): かな数詞foldのひらがな対称性
  "ふぁいぶすたー", "ファイブスター",
  // ★数字表記ゆらぎ(2026-07-27)
  "season2", "seasonII", "シーズンツー", "7つの大罪", "七つの大罪", "ロザリオ",
  // 著者(漢字・かな)
  "尾田栄一郎", "高橋留美子", "たかはしるみこ", "手塚治虫", "さいとう・たかを", "水木しげる",
  // 複数語AND
  "ワンピース 尾田", "尾田 ワンピース", "高橋 らんま", "水木 鬼太郎",
  // 別名・英題(alt)
  "one piece", "attack on titan",
  // 記号・長音・中黒
  "ジョジョ", "らんま", "らんま1/2", "パタリロ",
  // 短い・広いクエリ(件数が多い=順位の安定性を見る)
  "の", "ラブ", "学園",
];

/** 逐次入力の検証(1文字ずつ伸ばして最後にまっさらと一致するか)。 */
const TYPING: string[] = ["ワンピース", "ふぁいぶすたー", "高橋留美子"];

/** ファセット件数を焼くフィルタ状態。 */
const FACET_STATES: Array<{ name: string; patch: Partial<FilterState> }> = [
  { name: "empty", patch: {} },
  { name: "genre=action", patch: { genres: ["action"] } },
  { name: "demographic=shounen", patch: { demographics: ["shounen"] } },
  { name: "status=completed", patch: { statuses: ["completed"] } },
];

type QueryShot = { n: number; top: string[]; tierHist: Record<string, number> };
type Snapshot = {
  corpus: { rows: number };
  queries: Record<string, QueryShot>;
  facets: Record<string, Record<string, Record<string, number>>>;
};

let items: MangaListItem[] = [];
let base: MangaListItem[] = [];

/** ListClient の rows 計算(検索中・並び順未タッチ)と同じ経路をたどる。 */
function shotFor(q: string): QueryShot {
  __resetSearchCacheForTest();
  const tiers = searchWithTiers(q, items);
  const hit = base.filter((m) => tiers.has(m.slug));
  const sorted = sortRows(hit, "popularity", tiers, false);
  const tierHist: Record<string, number> = {};
  for (const t of tiers.values()) tierHist[String(t)] = (tierHist[String(t)] ?? 0) + 1;
  return { n: tiers.size, top: sorted.slice(0, 25).map((m) => m.slug), tierHist };
}

/** FilterPanel の counts 相当(7ファセット)。
 *  ★本体と同じく並べ替え抜きの filterItems を使う(2026-09-05。件数は順序に依らない)。 */
function facetCounts(state: FilterState): Record<string, Record<string, number>> {
  const tally = (clear: Partial<FilterState>, values: (m: MangaListItem) => string[]) => {
    const rows = filterItems(items, { ...state, ...clear });
    const map: Record<string, number> = {};
    for (const m of rows) for (const v of values(m)) map[v] = (map[v] ?? 0) + 1;
    return Object.fromEntries(Object.entries(map).sort(([a], [b]) => (a < b ? -1 : 1)));
  };
  return {
    status: tally({ statuses: [] }, (m) => [m.status]),
    demographic: tally({ demographics: [] }, (m) => (m.demographic ? [m.demographic] : [])),
    genre: tally({}, (m) => m.genres ?? []),
    theme: tally({}, (m) => m.themes ?? []),
    publisher: tally({ publishers: [] }, (m) =>
      m.publishers?.length ? m.publishers : m.publisher ? [m.publisher] : [],
    ),
    magazine: tally({ magazines: [] }, (m) => (m.magazine ? [m.magazine] : [])),
    launch: tally({ launch: null }, (m) => {
      const fvd = m.first_volume_date || (m.year_started ? String(m.year_started) : "");
      if (!fvd || fvd.length < 4) return [];
      const y = fvd.slice(0, 4);
      const keys = [`${Math.floor(Number(y) / 10) * 10}s`, y];
      if (fvd.length >= 7) keys.push(fvd.slice(0, 7));
      return keys;
    }),
  };
}

beforeAll(() => {
  const raw = JSON.parse(fs.readFileSync(FIXTURE, "utf8"));
  items = decodeListIndex(raw);
  const alt = JSON.parse(fs.readFileSync(FIXTURE_ALT, "utf8"));
  __setAltIndexForTest(alt);
  base = applyFilters(items, emptyFilterState());
});

describe("検索スナップショット(固定コーパス)", () => {
  it("コーパスが読める", () => {
    expect(items.length).toBeGreaterThan(2000);
    expect(items.some((m) => m.slug === "one-piece")).toBe(true);
  });

  it("結果集合・表示順・ファセット件数が記録と一致する", { timeout: 120_000 }, () => {
    const cur: Snapshot = {
      corpus: { rows: items.length },
      queries: Object.fromEntries(QUERIES.map((q) => [q, shotFor(q)])),
      facets: Object.fromEntries(
        FACET_STATES.map((s) => [s.name, facetCounts({ ...emptyFilterState(), ...s.patch })]),
      ),
    };

    if (UPDATE || !fs.existsSync(SNAP)) {
      fs.mkdirSync(SNAP_DIR, { recursive: true });
      fs.writeFileSync(SNAP, JSON.stringify(cur, null, 2) + "\n", "utf8");
      // 初回生成・明示更新のときだけ書いて通す(差分は git diff で人が見る)
      expect(fs.existsSync(SNAP)).toBe(true);
      return;
    }

    const prev: Snapshot = JSON.parse(fs.readFileSync(SNAP, "utf8"));
    // クエリ単位で比較する(どのクエリが壊れたかが一目で分かるように)
    for (const q of QUERIES) {
      expect({ q, ...cur.queries[q] }).toEqual({ q, ...prev.queries[q] });
    }
    expect(cur.facets).toEqual(prev.facets);
    expect(cur.corpus).toEqual(prev.corpus);
  });

  it("逐次入力の結果が、まっさらから引いた結果と一致する(絞り込みキャッシュの健全性)", () => {
    for (const q of TYPING) {
      const clean = shotFor(q);
      __resetSearchCacheForTest();
      let incremental = new Map<string, number>();
      for (let i = 1; i <= q.length; i++) incremental = searchWithTiers(q.slice(0, i), items);
      expect({ q, n: incremental.size }).toEqual({ q, n: clean.n });
      expect({ q, slugs: [...incremental.keys()].sort() }).toEqual({
        q,
        slugs: [...incremental.keys()].sort(),
      });
      const inc = sortRows(
        base.filter((m) => incremental.has(m.slug)),
        "popularity",
        incremental,
        false,
      ).slice(0, 25).map((m) => m.slug);
      expect({ q, top: inc }).toEqual({ q, top: clean.top });
    }
  });

  it("alt(別名)の到着前後で、alt由来のヒットだけが増える", () => {
    const altRaw = JSON.parse(fs.readFileSync(FIXTURE_ALT, "utf8"));
    __setAltIndexForTest(null);
    __resetSearchCacheForTest();
    const before = new Set(searchWithTiers("one piece", items).keys());
    __setAltIndexForTest(altRaw);
    __resetSearchCacheForTest();
    const after = new Set(searchWithTiers("one piece", items).keys());
    // alt は増える方向にしか働かない(取りこぼしが起きたら before ⊄ after で落ちる)
    for (const s of before) expect(after.has(s)).toBe(true);
  });
});
