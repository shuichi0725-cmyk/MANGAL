import { z } from "zod";

export const AuthorRole = z.enum(["writer", "artist", "writer_artist", "editor"]);
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
  /** 著者読み(カタカナ)= 50音索引用。 MADB metadata504(作者master)公式ヨミ由来。 無ければ省略 */
  kana: z.string().optional(),
  /** 著者ローマ字(ヘボン、kana由来)= 検索補助。 無ければ省略 */
  romaji: z.string().optional(),
});
export type Author = z.infer<typeof AuthorSchema>;

/** credits = 著作でない副次クレジット(編集/監修/訳/装丁/解説/企画/協力 等)。
 *  生MADB役割タグ由来。 著者欄・50音索引・著者フィルターには入れない=フリガナ不要。
 *  表示専用 + キーワード検索の対象には入れる。 */
export const CreditSchema = z.object({
  name: z.string().min(1),
  /** 表示役割ラベル(例: 編集 / 監修 / 翻訳 / 装丁・デザイン / 解説 / 企画 / 協力) */
  role: z.string().min(1),
});
export type Credit = z.infer<typeof CreditSchema>;

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
  /** 巻ごとの作画者 (= 学習まんが等、 巻によって作画が異なる作品。 省略時はページ著者を使う) */
  artists: z.array(z.string().min(1)).optional(),
  /** 巻ごとの監修者 (= 学習まんが等の歴史学者監修。 省略可) */
  supervisors: z.array(z.string().min(1)).optional(),
});
export type Volume = z.infer<typeof VolumeSchema>;

export const EditionType = z.enum([
  "standard",
  "kanzenban",
  "bunkobon",
  "shinsoban",
  "aizoban",
  "wideban",
  "deluxe",
  "renewal",
  "anime",
  "other",
]);
export type EditionTypeT = z.infer<typeof EditionType>;

export const EditionSchema = z.object({
  type: EditionType,
  label: z.string().min(1),
  /** 出版社 (= 版ごと。 再販・他社化で作品内に複数出版社が在る場合に版単位で保持。
   *  単一出版社作品では作品 publisher と同じ。 省略時は作品 publisher を使う) */
  publisher: z.string().nullable().optional(),
  imprint: z.string().nullable().optional(),
  year_started: z.number().int().nullable().optional(),
  year_ended: z.number().int().nullable().optional(),
  volumes: z.array(VolumeSchema).min(1),
  /** 刷/バージョン (= 同一(出版社×type)で同巻数の別刷: 初版/新装版/復刻 等)。
   *  複数刷がある時のみ。 frontend は古い順タブで表示し、 既定は「全巻ISBN有りの最古刷」。
   *  edition.volumes は既定刷と同じ(版なし消費者の後方互換)。 */
  versions: z
    .array(
      z.object({
        label: z.string().min(1),
        year_started: z.number().int().nullable().optional(),
        volumes: z.array(VolumeSchema).min(1),
      }),
    )
    .optional(),
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
  /** 副次クレジット(編集/監修/訳/装丁/解説/企画/協力 等)。 表示+キーワード検索のみ、 著者扱いしない */
  credits: z.array(CreditSchema).default([]),
  /** キャッチコピー(30〜36字目安、カードで2行表示)。 知らない作品への興味喚起用 */
  catch: z.string().optional(),
  /** 代表出版社キー (= 最多巻の版。 ヘッダ表示用)。 全版が長尾社の時は "(unknown)" */
  publisher: z.string().min(1),
  /** 全版の出版社キー (= distinct、 フィルタ用)。 1作が複数社から出た場合に全社を保持。
   *  publisher は代表1社、 こちらは「どれかの版を出した社」全部 (= 集合フィルタ) */
  publishers: z.array(z.string()).default([]),
  magazine: z.string().min(1).nullable().optional(),
  demographic: Demographic,
  genres: z.array(z.string().min(1)).min(1),
  /** ★genres が信頼源(AniList/Wikipedia)でなく AI 暫定のみ = 低信頼。
   *  信頼源が来たら上書きされる(蒸留/第三の源で埋まる余地)。 trusted 由来時は省略/false。 */
  genres_provisional: z.boolean().optional(),
  synopsis: z.string().default(""),
  /** アニメ化されたか (= 何らかの形で映像化済) */
  anime_adapted: z.boolean().optional(),
  /** 最初のアニメ化年 (= 複数あれば一番古い) */
  anime_first_year: z.number().int().min(1900).max(2100).optional(),
  /** 海外配信タイトル / 別名。 検索の柔軟性 + SEO 用 */
  alternative_titles: AlternativeTitlesSchema.optional(),
  /** 受賞歴。 自由記述 (例: "講談社漫画賞 少年部門 1985") */
  awards: z.array(z.string()).optional(),
  /** Wikidata の QID (例: "Q282470")、 cross-reference / debug 用。 ★series.qid=著者QID */
  wikidata_qid: z.string().regex(/^Q\d+$/).optional(),
  /** 作品(work)の Wikidata QID。 AniList漫画ID(P8731)経由で一意取得。 著者QIDとは別 */
  work_wikidata_qid: z.string().regex(/^Q\d+$/).optional(),
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
  /** AniList 人気度(= リストに入れたユーザ数。 「人気順」discovery用。 コミュニティ不要で人気が出せる) */
  popularity: z.number().int().nonnegative().optional(),
  /** AniList 平均スコア(0-100)。 「高評価順」discovery用 */
  score: z.number().int().min(0).max(100).optional(),
  /** 他言語タイトル / 別名 (= AniList synonyms 由来、 alternative_titles.en 補助) */
  synonyms: z.array(z.string().min(1)).optional(),
  editions: z.array(EditionSchema).min(1),
});
export type Manga = z.infer<typeof MangaSchema>;

/**
 * 画集 (= 漫画家の画集/原画集/イラスト集)。 ★漫画とは別カテゴリ・別ストリーム。
 * Manga と別の軽量型 = `editions` を持たず `volumes` 直下 (画集は版分岐が薄い)。
 * volumes は通常の Volume と同形 = 書影・アフィリンクが同じ仕組みで効く。
 */
export const ArtBookLinkSchema = z.object({
  /** 紐付け先の漫画 slug */
  slug: z.string(),
  /** 画集 title が作品名を含む = その作品ページに優先表示 (§3-2 段階1) */
  title_match: z.boolean().default(false),
});
export type ArtBookLink = z.infer<typeof ArtBookLinkSchema>;

export const ArtBookSchema = z.object({
  slug: z.string().regex(/^[a-z0-9-]+$/, "slug は小文字英数字とハイフンのみ"),
  /** ★カテゴリ = 常に「画集」(漫画と別カテゴリで識別・フィルタ用) */
  category: z.string().default("画集"),
  title: z.string().min(1),
  title_kana: z.string().min(1),
  /** 分かち書きフリガナ (= slug生成用、 語境界スペース有)。 NDL spaced 由来。 任意 */
  title_kana_segmented: z.string().optional(),
  /** ローマ字。 ★ローマ字化生成器が未実装(GO待ち)のため任意。 暫定は空 */
  title_romaji: z.string().default(""),
  /** ★作画家 (artist role)。 原作者は入れない (ラノベ等) */
  artist: z.string().min(1),
  /** トリビュート/複数作画家の合同画集 (= 代表 artist に紐付けつつ印を残す) */
  multi_artist: z.boolean().optional(),
  /** true は表示除外 (= 既定で build 時に出力しない)。 データは保持 */
  adult: z.boolean().default(false),
  /** 紐付け漫画 (= build/promote 時に計算。 作画家一致 + title 一致は優先) */
  linked_works: z.array(ArtBookLinkSchema).default([]),
  publisher: z.string().min(1).nullable().optional(),
  year: z.number().int().min(1900).max(2100).nullable().optional(),
  /** series.qid (= 著者QID)、 cross-reference / debug 用 */
  wikidata_qid: z.string().regex(/^Q\d+$/).optional(),
  volumes: z.array(VolumeSchema).min(1),
});
export type ArtBook = z.infer<typeof ArtBookSchema>;

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
  /** ★画集 = manga[] とは別配列 (構造的に混ざらない保証) */
  artBooks: ArtBook[];
  publishers: Publisher[];
  magazines: Magazine[];
  genres: Genre[];
  demographics: DemographicLabel[];
};
