import { z } from "zod";

export const AuthorRole = z.enum(["writer", "artist", "writer_artist"]);
export type AuthorRoleT = z.infer<typeof AuthorRole>;

export const Status = z.enum(["ongoing", "completed", "hiatus"]);
export type StatusT = z.infer<typeof Status>;

export const Demographic = z.enum([
  "shounen",
  "shoujo",
  "seinen",
  "josei",
  "kodomo",
  "other",
]);
export type DemographicT = z.infer<typeof Demographic>;

export const AuthorSchema = z.object({
  name: z.string().min(1),
  role: AuthorRole,
});
export type Author = z.infer<typeof AuthorSchema>;

export const VolumeSchema = z.object({
  number: z.number().int().min(1),
  /** 巻ラベル (= 「上」「下」「特装版」等、 数字以外の表示文字。 既定 `第${number}巻` を上書きする) */
  volume_label: z.string().optional(),
  asin: z.string().nullable().optional(),
  kindle_asin: z.string().nullable().optional(),
  isbn13: z.union([z.string(), z.number()]).nullable().optional(),
  cover_url: z.string().url().nullable().optional(),
  release_date: z
    .string()
    .regex(/^\d{4}(-\d{2}(-\d{2})?)?$/)
    .nullable()
    .optional(),
  description: z.string().optional(),
});
export type Volume = z.infer<typeof VolumeSchema>;

export const EditionType = z.enum([
  "standard",
  "kanzenban",
  "bunkobon",
  "shinsoban",
  "aizoban",
  "wideban",
  "renewal",
  "anime",
  "other",
]);
export type EditionTypeT = z.infer<typeof EditionType>;

export const EditionSchema = z.object({
  type: EditionType,
  label: z.string().min(1),
  imprint: z.string().nullable().optional(),
  year_started: z.number().int().nullable().optional(),
  year_ended: z.number().int().nullable().optional(),
  volumes: z.array(VolumeSchema).min(1),
});
export type Edition = z.infer<typeof EditionSchema>;

export const AlternativeTitlesSchema = z.object({
  en: z.string().optional(),
  fr: z.string().optional(),
  de: z.string().optional(),
  it: z.string().optional(),
  pt: z.string().optional(),
});
export type AlternativeTitles = z.infer<typeof AlternativeTitlesSchema>;

export const MangaSchema = z.object({
  slug: z.string().regex(/^[a-z0-9-]+$/, "slug は小文字英数字とハイフンのみ"),
  title: z.string().min(1),
  title_kana: z.string().min(1),
  title_romaji: z.string().min(1),
  /** 副題 (= MADB title field の ` : ` 右側、 例: 「ジョジョの奇妙な冒険 Part8」) */
  subtitle: z.string().optional(),
  /** 副題ふりがな (= MADB kana の ` : ` 右側、 無い時は空) */
  subtitle_kana: z.string().optional(),
  year_started: z.number().int().min(1900).max(2100),
  year_ended: z.number().int().min(1900).max(2100).nullable(),
  status: Status,
  authors: z.array(AuthorSchema).min(1),
  original_authors: z.array(AuthorSchema).default([]),
  publisher: z.string().min(1),
  magazine: z.string().min(1).nullable().optional(),
  demographic: Demographic,
  genres: z.array(z.string().min(1)).min(1),
  synopsis: z.string().default(""),
  /** アニメ化されたか (= 何らかの形で映像化済) */
  anime_adapted: z.boolean().optional(),
  /** 最初のアニメ化年 (= 複数あれば一番古い) */
  anime_first_year: z.number().int().min(1900).max(2100).optional(),
  /** 海外配信タイトル / 別名。 検索の柔軟性 + SEO 用 */
  alternative_titles: AlternativeTitlesSchema.optional(),
  /** 受賞歴。 自由記述 (例: "講談社漫画賞 少年部門 1985") */
  awards: z.array(z.string()).optional(),
  /** Wikidata の QID (例: "Q282470")、 cross-reference / debug 用 */
  wikidata_qid: z.string().regex(/^Q\d+$/).optional(),
  /** 日本語 Wikipedia 記事 URL (= fetch:wikipedia で発見した canonical link) */
  wikipedia_url: z.string().url().optional(),
  /** AniList 由来 genres (= 種3 genres と並列保持、 上書きしない、 比較用) */
  genres_anilist: z.array(z.string()).optional(),
  /** AniList 由来 tags (= 案2 filter 適用後 = Demographic + Theme rank≥60 + Cast/Setting rank≥70) */
  tags: z
    .array(
      z.object({
        name: z.string(),
        category: z.string(),
        rank: z.number().int().min(0).max(100),
      }),
    )
    .optional(),
  /** AniList entry ID (= source 追跡、 後の更新差分取得用) */
  anilist_id: z.number().int().positive().optional(),
  editions: z.array(EditionSchema).min(1),
});
export type Manga = z.infer<typeof MangaSchema>;

export function primaryEdition(manga: Manga): Edition {
  return manga.editions[0];
}

export function primaryVolume(manga: Manga): Volume | undefined {
  return manga.editions[0]?.volumes[0];
}

export function allVolumes(manga: Manga): Volume[] {
  return manga.editions.flatMap((e) => e.volumes);
}

export const PublisherSchema = z.object({
  key: z.string(),
  name: z.string(),
});
export type Publisher = z.infer<typeof PublisherSchema>;

export const MagazineSchema = z.object({
  key: z.string(),
  name: z.string(),
  publisher: z.string(),
  demographic: Demographic,
});
export type Magazine = z.infer<typeof MagazineSchema>;

export const GenreSchema = z.object({
  key: z.string(),
  name: z.string(),
});
export type Genre = z.infer<typeof GenreSchema>;

export const DemographicLabelSchema = z.object({
  key: Demographic,
  name: z.string(),
});
export type DemographicLabel = z.infer<typeof DemographicLabelSchema>;

export type DataBundle = {
  manga: Manga[];
  publishers: Publisher[];
  magazines: Magazine[];
  genres: Genre[];
  demographics: DemographicLabel[];
};
