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
} from "./schema";
import { z } from "zod";

// MANGAL_DATA_DIR でデータルートを差し替え可(= サンプル/プレビュー build 用)。 既定 = ./data
const DATA_DIR = process.env.MANGAL_DATA_DIR
  ? path.resolve(process.env.MANGAL_DATA_DIR)
  : path.join(process.cwd(), "data");

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

let cached: DataBundle | null = null;

export function loadAllManga(): DataBundle {
  if (cached) return cached;

  const publishers: Publisher[] = readMasterRecord(
    path.join(DATA_DIR, "publishers.yml"),
    PublisherSchema,
  );
  const magazines: Magazine[] = readMasterRecord(
    path.join(DATA_DIR, "magazines.yml"),
    MagazineSchema,
  );
  const genres: Genre[] = readMasterRecord(
    path.join(DATA_DIR, "genres.yml"),
    GenreSchema,
  );
  const demographics: DemographicLabel[] = readMasterRecord(
    path.join(DATA_DIR, "demographics.yml"),
    DemographicLabelSchema,
  );

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

  // ★画集 = 別ストリーム (data/art-books/)。 manga と混ぜない。 promote が
  // 別出力した yml を同期する運用。 ディレクトリ不在時は空配列で build を通す。
  const artBooksDir = path.join(DATA_DIR, "art-books");
  const artBookFiles = fs.existsSync(artBooksDir)
    ? fs
        .readdirSync(artBooksDir)
        .filter((f) => f.endsWith(".yml") || f.endsWith(".yaml"))
    : [];
  const artBooks: ArtBook[] = artBookFiles
    .map((f) => readYaml(path.join(artBooksDir, f), ArtBookSchema))
    // 既定: adult 画集は本番に出さない (確実側)
    .filter((a) => !a.adult);
  artBooks.sort((a, b) => a.artist.localeCompare(b.artist, "ja") || a.title.localeCompare(b.title, "ja"));

  cached = { manga, artBooks, publishers, magazines, genres, demographics };
  return cached;
}
