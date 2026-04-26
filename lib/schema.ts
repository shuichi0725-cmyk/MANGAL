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
  asin: z.string().nullable().optional(),
  isbn13: z.union([z.string(), z.number()]).nullable().optional(),
  cover_url: z.string().url().nullable().optional(),
  release_date: z
    .string()
    .regex(/^\d{4}(-\d{2}(-\d{2})?)?$/)
    .nullable()
    .optional(),
});
export type Volume = z.infer<typeof VolumeSchema>;

export const MangaSchema = z.object({
  slug: z.string().regex(/^[a-z0-9-]+$/, "slug は小文字英数字とハイフンのみ"),
  title: z.string().min(1),
  title_kana: z.string().min(1),
  title_romaji: z.string().min(1),
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
  volumes: z.array(VolumeSchema).min(1),
});
export type Manga = z.infer<typeof MangaSchema>;

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
