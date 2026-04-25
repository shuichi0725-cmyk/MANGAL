import fs from "node:fs";
import path from "node:path";
import YAML from "yaml";
import {
  type DataBundle,
  type Manga,
  MangaSchema,
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

const DATA_DIR = path.join(process.cwd(), "data");

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
  const files = fs
    .readdirSync(mangaDir)
    .filter((f) => f.endsWith(".yml") || f.endsWith(".yaml"));

  const manga: Manga[] = files.map((f) => {
    const m: Manga = readYaml(path.join(mangaDir, f), MangaSchema);
    if (!publisherKeys.has(m.publisher)) {
      throw new Error(`未定義の publisher: ${m.publisher} (${f})`);
    }
    if (m.magazine && !magazineKeys.has(m.magazine)) {
      throw new Error(`未定義の magazine: ${m.magazine} (${f})`);
    }
    for (const g of m.genres) {
      if (!genreKeys.has(g)) {
        throw new Error(`未定義の genre: ${g} (${f})`);
      }
    }
    return m;
  });

  manga.sort((a, b) => a.year_started - b.year_started || a.title.localeCompare(b.title, "ja"));

  cached = { manga, publishers, magazines, genres, demographics };
  return cached;
}
