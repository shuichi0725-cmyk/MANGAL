import fs from "node:fs";
import path from "node:path";
import YAML from "yaml";
import {
  type DataBundle,
  type Manga,
  MangaSchema,
  type ArtBook,
  ArtBookSchema,
  type Publisher,
  PublisherSchema,
  type Magazine,
  MagazineSchema,
  type Genre,
  GenreSchema,
  type DemographicLabel,
  DemographicLabelSchema,
  type MangaListItem,
  type ListBundle,
} from "./schema";
import { z } from "zod";

// MANGAL_DATA_DIR でデータルートを差し替え可(= サンプル/プレビュー build 用)。 既定 = ./data
const DATA_DIR = process.env.MANGAL_DATA_DIR
  ? path.resolve(process.env.MANGAL_DATA_DIR)
  : path.join(process.cwd(), "data");

// 一覧用 軽量索引 (= data/manga-list-index.json)。 トップ/一覧/フィルタ/カードはこれを使う
// (= full manga.v2 を props で送らない = 数十MB → 数MB)。 build 時生成 (_build-list-index.py)。
let _listIndex: MangaListItem[] | null = null;
// ★軽量化: 索引は {f:フィールド順, d:値配列[]} の配列形式 → ここで MangaListItem[] に復元
//   (client useMangaIndex と同じデコード)。 旧形式(オブジェクト配列)も互換。
function decodeListIndex(raw: unknown): MangaListItem[] {
  if (Array.isArray(raw)) return raw as MangaListItem[];
  const { f, d } = raw as { f: string[]; d: unknown[][] };
  return d.map((arr) => {
    const o: Record<string, unknown> = {};
    for (let i = 0; i < f.length; i++) {
      const v = arr[i];
      if (v !== null && v !== undefined) o[f[i]] = v;
    }
    return o as unknown as MangaListItem;
  });
}
export function loadMangaListIndex(): MangaListItem[] {
  if (_listIndex) return _listIndex;
  const p = path.join(DATA_DIR, "manga-list-index.json");
  // 索引が無い環境(= データ準備中/未生成)でも build を通すため空配列フォールバック。
  if (!fs.existsSync(p)) {
    console.warn(`[loadData] 一覧索引が無い (${p}) → 空一覧。 _build-list-index.py 要実行`);
    _listIndex = [];
    return _listIndex;
  }
  const list = decodeListIndex(JSON.parse(fs.readFileSync(p, "utf8")));
  // catch は別ファイル → server側では build時に merge(SSGカードのため。 client は遅延ロード)
  const cp = path.join(DATA_DIR, "manga-catch-index.json");
  if (fs.existsSync(cp)) {
    const cm = JSON.parse(fs.readFileSync(cp, "utf8")) as Record<string, string>;
    for (const m of list) {
      const c = cm[m.slug];
      if (c) (m as { catch?: string }).catch = c;
    }
  }
  _listIndex = list;
  return _listIndex;
}

function readYaml<S extends z.ZodTypeAny>(file: string, schema: S): z.infer<S> {
  const raw = fs.readFileSync(file, "utf8");
  const parsed = YAML.parse(raw);
  const result = schema.safeParse(parsed);
  if (!result.success) {
    throw new Error(
      `データ検証エラー: ${file}\n${JSON.stringify(result.error.format(), null, 2)}`,
    );
  }
  return result.data;
}

function readMasterRecord<S extends z.ZodTypeAny>(
  file: string,
  itemSchema: S,
): z.infer<S>[] {
  const raw = fs.readFileSync(file, "utf8");
  const parsed = YAML.parse(raw) as Record<string, Record<string, unknown>>;
  const items: z.infer<S>[] = [];
  for (const [key, value] of Object.entries(parsed)) {
    const merged = { key, ...value };
    const result = itemSchema.safeParse(merged);
    if (!result.success) {
      throw new Error(
        `マスタ検証エラー: ${file} key=${key}\n${JSON.stringify(result.error.format(), null, 2)}`,
      );
    }
    items.push(result.data);
  }
  return items;
}

let _genreIntros: Record<string, string> | null = null;
/** ジャンル別ランディングの AIキュレーション導入文(data/seeds/genre-intros.yml)。 無ければ空。 */
export function loadGenreIntros(): Record<string, string> {
  if (_genreIntros) return _genreIntros;
  try {
    const p = path.join(DATA_DIR, "seeds", "genre-intros.yml");
    const parsed = YAML.parse(fs.readFileSync(p, "utf8")) as { intros?: Record<string, string> };
    _genreIntros = parsed?.intros ?? {};
  } catch {
    _genreIntros = {};
  }
  return _genreIntros;
}

let _tagI18n: Record<string, { ja: string; genre: string }> | null = null;
/** AniListタグ → {ja 和訳, genre 近いmasterキー}(data/seeds/tag-i18n.yml)。
 *  詳細ページの「要素」欄表示用。 無ければ空。 */
export function loadTagI18n(): Record<string, { ja: string; genre: string }> {
  if (_tagI18n) return _tagI18n;
  try {
    const p = path.join(DATA_DIR, "seeds", "tag-i18n.yml");
    const parsed = YAML.parse(fs.readFileSync(p, "utf8")) as {
      tags?: Record<string, { ja: string; genre: string }>;
    };
    _tagI18n = parsed?.tags ?? {};
  } catch {
    _tagI18n = {};
  }
  return _tagI18n;
}

export type AiReview = { vendor: string; model: string; text: string };
export type AiReviewSection = {
  setsu: number;
  slug: string;
  title: string;
  author: string;
  prompt: string;
  reviews: AiReview[];
};
let _aiReviews: AiReviewSection[] | null = null;
/** AI書評家リーグ(corner9): data/seeds/ai-reviews.yml。 節(setsu)降順=最新が先頭。 [[ai_review_league_operation]] */
export function loadAiReviews(): AiReviewSection[] {
  if (_aiReviews) return _aiReviews;
  try {
    const p = path.join(DATA_DIR, "seeds", "ai-reviews.yml");
    const parsed = YAML.parse(fs.readFileSync(p, "utf8")) as { sections?: AiReviewSection[] };
    _aiReviews = (parsed?.sections ?? [])
      .filter((s) => s && s.reviews && s.reviews.length > 0)
      .slice()
      .sort((a, b) => b.setsu - a.setsu);
  } catch {
    _aiReviews = [];
  }
  return _aiReviews;
}

// ★master (= publishers/magazines/genres/demographics) のみ読む軽量ローダ。
//   一覧索引と組む時に manga 65k を読まずに済む (= loadListBundle 用)。
type Masters = {
  publishers: Publisher[];
  magazines: Magazine[];
  genres: Genre[];
  demographics: DemographicLabel[];
};
let _masters: Masters | null = null;
export function loadMasters(): Masters {
  if (_masters) return _masters;
  _masters = {
    publishers: readMasterRecord(path.join(DATA_DIR, "publishers.yml"), PublisherSchema),
    magazines: readMasterRecord(path.join(DATA_DIR, "magazines.yml"), MagazineSchema),
    genres: readMasterRecord(path.join(DATA_DIR, "genres.yml"), GenreSchema),
    demographics: readMasterRecord(path.join(DATA_DIR, "demographics.yml"), DemographicLabelSchema),
  };
  return _masters;
}

// 画集 (= data/art-books、 161件程度) のみ読む軽量ローダ。
let _artBooks: ArtBook[] | null = null;
export function loadArtBooks(): ArtBook[] {
  if (_artBooks) return _artBooks;
  const artBooksDir = path.join(DATA_DIR, "art-books");
  const files = fs.existsSync(artBooksDir)
    ? fs.readdirSync(artBooksDir).filter((f) => f.endsWith(".yml") || f.endsWith(".yaml"))
    : [];
  const arr = files
    .map((f) => readYaml(path.join(artBooksDir, f), ArtBookSchema))
    .filter((a) => !a.adult); // 既定: adult 画集は本番に出さない
  arr.sort((a, b) => a.artist.localeCompare(b.artist, "ja") || a.title.localeCompare(b.title, "ja"));
  _artBooks = arr;
  return _artBooks;
}

// ★一覧表示用バンドル = 軽量索引 + master + 画集 (= full manga.v2 を読まない)。
//   トップ/一覧/ジャンル/検索はこれを使う。 詳細ページのみ loadAllManga (full)。
let _listBundle: ListBundle | null = null;
export function loadListBundle(): ListBundle {
  if (_listBundle) return _listBundle;
  const m = loadMasters();
  _listBundle = {
    manga: loadMangaListIndex(),
    artBooks: loadArtBooks(),
    publishers: m.publishers,
    magazines: m.magazines,
    genres: m.genres,
    demographics: m.demographics,
  };
  return _listBundle;
}

let cached: DataBundle | null = null;

export function loadAllManga(): DataBundle {
  if (cached) return cached;

  const { publishers, magazines, genres, demographics } = loadMasters();

  const publisherKeys = new Set(publishers.map((p) => p.key));
  const magazineKeys = new Set(magazines.map((m) => m.key));
  const genreKeys = new Set(genres.map((g) => g.key));

  const mangaDir = path.join(DATA_DIR, "manga");
  // CI で全 yaml 削除した状態 (= データ準備中) でも build を通すため、
  // ディレクトリ不在時は空配列で扱う。 通常運用では .gitkeep があるため
  // ディレクトリは存在する。
  const files = fs.existsSync(mangaDir)
    ? fs
        .readdirSync(mangaDir)
        .filter((f) => f.endsWith(".yml") || f.endsWith(".yaml"))
    : [];

  // ★堅牢化(2026-06-13): 1ページの不良(schema違反/未定義キー)で全体を落とさない。
  //   不良は skip + 警告(本番でも1頁が全サイトを500にしない安全網)。 schema検証自体は維持。
  //   既知の根因: ①著者名 "029" 等の数値見え文字列を PyYAML が無quote出力→JS yaml が数値解釈
  //   ②genre 'other'(master外)。 どちらも promote側で恒久修正予定。
  let _skipped = 0;
  const manga: Manga[] = [];
  for (const f of files) {
    try {
      const m: Manga = readYaml(path.join(mangaDir, f), MangaSchema);
      if (m.publisher !== "(unknown)" && !publisherKeys.has(m.publisher)) {
        throw new Error(`未定義の publisher: ${m.publisher}`);
      }
      for (const pk of m.publishers) {
        if (!publisherKeys.has(pk)) throw new Error(`未定義の publishers[]: ${pk}`);
      }
      if (m.magazine && !magazineKeys.has(m.magazine)) {
        throw new Error(`未定義の magazine: ${m.magazine}`);
      }
      for (const g of m.genres) {
        if (!genreKeys.has(g)) throw new Error(`未定義の genre: ${g}`);
      }
      manga.push(m);
    } catch (e) {
      _skipped += 1;
      if (_skipped <= 30) {
        console.warn(`[loadData] skip ${f}: ${String((e as Error).message).split("\n")[0]}`);
      }
    }
  }
  if (_skipped > 0) console.warn(`[loadData] ★${_skipped} ページを skip(schema/キー不良)`);

  manga.sort((a, b) => a.year_started - b.year_started || a.title.localeCompare(b.title, "ja"));

  // ★画集 = 別ストリーム (data/art-books/)。 manga と混ぜない。 軽量ローダ経由。
  const artBooks = loadArtBooks();

  cached = { manga, artBooks, publishers, magazines, genres, demographics };
  return cached;
}
