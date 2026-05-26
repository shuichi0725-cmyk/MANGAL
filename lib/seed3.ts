/**
 * 種3 (= series-supplement.yml) の Zod schema + reader。
 *
 * 種3 は MADB 由来 (= 種2) で取れない 8 fields を AI 一括補完で事前生成し、
 * data/seeds/series-supplement.yml に commit しておく形式。 promote-bulk が
 * 起動時に読み込み、 yaml 出力時に各 series へ補完する。
 *
 * keying: (qid + baseTitle) 複合 key で series を identify。 slug 不安定対策。
 *
 * fields:
 *   - slug          (= folder name、 promote-bulk の baseSlug 上書き候補)
 *   - magazine      (= 連載誌、 magazines.yml の key)
 *   - demographic   (= 少年/青年/etc.、 demographics.yml の key)
 *   - genres        (= 1-4 tags、 genres.yml の key)
 *   - synopsis      (= 80-200 char の独自要約)
 *   - status        (= ongoing / completed / hiatus)
 *   - anime_adapted (= optional bool)
 *   - awards        (= optional 受賞歴 array)
 *
 * 不明な entry は AI が "unknown" を返す → 種3 entry 作らない / null field。
 * promote-bulk fallback で TODO_genre / "" / null 化。
 */
import fs from "node:fs";
import { z } from "zod";
import yaml from "yaml";

export const Status = z.enum(["ongoing", "completed", "hiatus"]);
export const Demographic = z.enum([
  "shounen",
  "shoujo",
  "seinen",
  "josei",
  "kodomo",
  "other",
]);

export const Seed3EntrySchema = z.object({
  /** (qid + baseTitle) 複合 ID。 例: "Q3782468|進撃の巨人" / "ノークレジット|タイトル" */
  key: z.string().min(1),
  /** AI 提案 slug。 promote-bulk の自動 slug より優先する */
  slug: z.string().regex(/^[a-z0-9-]+$/).optional(),
  /** HP 表示用 フリガナ (= スペースなし、 カタカナ)。 例: "ジョジョノキミョウナボウケン" */
  title_kana: z.string().optional(),
  /** slug 生成元 フリガナ (= MADB ja-hrkt 仕様、 スペース区切り)。 例: "ジョジョ ノ キミョウナ ボウケン" */
  title_kana_segmented: z.string().optional(),
  /** subtitle あり entry 用 (= 上記 title_kana と同仕様、 副題側) */
  subtitle_kana: z.string().optional(),
  subtitle_kana_segmented: z.string().optional(),
  magazine: z.string().nullable().optional(),
  demographic: Demographic.optional(),
  genres: z.array(z.string()).optional(),
  synopsis: z.string().optional(),
  status: Status.optional(),
  anime_adapted: z.boolean().optional(),
  awards: z.array(z.string()).optional(),
  alternative_titles: z
    .object({
      en: z.string().nullable().optional(),
      fr: z.string().nullable().optional(),
      de: z.string().nullable().optional(),
      it: z.string().nullable().optional(),
      pt: z.string().nullable().optional(),
    })
    .optional(),
});
export type Seed3Entry = z.infer<typeof Seed3EntrySchema>;

export const Seed3FileSchema = z.object({
  schema_version: z.union([z.literal(1), z.literal(2)]),
  generated_at: z.string(),
  generator: z.string(),
  series: z.array(Seed3EntrySchema),
});
export type Seed3File = z.infer<typeof Seed3FileSchema>;

const DEFAULT_PATH = "data/seeds/series-supplement-v2.yml";

/**
 * 種3 ファイル を 読んで (key → entry) Map を返す。
 * file 不在時は 空 Map (= 種3 抜きで動作可能、 fallback)。
 */
export function loadSeed3(path: string = DEFAULT_PATH): Map<string, Seed3Entry> {
  if (!fs.existsSync(path)) return new Map();
  const text = fs.readFileSync(path, "utf8");
  const raw = yaml.parse(text);
  const parsed = Seed3FileSchema.safeParse(raw);
  if (!parsed.success) {
    throw new Error(
      `[seed3] schema validation failed for ${path}:\n${parsed.error.issues
        .slice(0, 5)
        .map((i) => `  ${i.path.join(".")}: ${i.message}`)
        .join("\n")}`,
    );
  }
  const map = new Map<string, Seed3Entry>();
  for (const entry of parsed.data.series) {
    map.set(entry.key, entry);
  }
  return map;
}

/**
 * (qid, baseTitle) → 種3 key 生成。 qid 無し series は "noqid" prefix で
 * baseTitle のみ。
 */
export function seed3Key(qid: string | null, baseTitle: string): string {
  return `${qid ?? "noqid"}|${baseTitle}`;
}

/**
 * 種3 file を出力。 atomic write (= temp → rename)。
 */
export function writeSeed3(file: Seed3File, path: string = DEFAULT_PATH): void {
  const validated = Seed3FileSchema.parse(file);
  const tmp = `${path}.tmp`;
  fs.mkdirSync(require("node:path").dirname(path), { recursive: true });
  fs.writeFileSync(tmp, yaml.stringify(validated));
  fs.renameSync(tmp, path);
}
