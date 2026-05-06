/**
 * Tier 2: data/seeds/adult-imprints.yml の Zod schema + reader。
 *
 * yaml は scripts/clean-imprint-dump.ts が raw dump から自動生成する。
 * 手書きの追記もできるが、 raw dump 側に追加するのが正攻法。
 *
 * adult_imprints テーブルへ INSERT するのは imprints セクションのみ。
 * distribution_channels セクションは当面 (= signal weight 設計を確認するまで)
 * INSERT しない。 ambiguous は false-positive 防止のため絶対に INSERT しない。
 */
import fs from "node:fs";
import { z } from "zod";
import YAML from "yaml";

export const AdultImprintEntrySchema = z.object({
  imprint: z.string().min(1),
  publisher: z.string().min(1),
  count: z.number().int().nonnegative(),
});
export type AdultImprintEntry = z.infer<typeof AdultImprintEntrySchema>;

export const AdultDistributionChannelSchema = z.object({
  imprint: z.string().min(1),
  notes: z.string().optional(),
});
export type AdultDistributionChannel = z.infer<
  typeof AdultDistributionChannelSchema
>;

export const AdultAmbiguousSchema = z.object({
  imprint: z.string().min(1),
  publishers: z.array(z.string()).min(1),
  note: z.string().optional(),
});
export type AdultAmbiguous = z.infer<typeof AdultAmbiguousSchema>;

export const AdultImprintsFileSchema = z.object({
  schema_version: z.number().int().positive(),
  imprints: z.array(AdultImprintEntrySchema),
  distribution_channels: z.array(AdultDistributionChannelSchema).optional(),
  ambiguous: z.array(AdultAmbiguousSchema).optional(),
});
export type AdultImprintsFile = z.infer<typeof AdultImprintsFileSchema>;

/**
 * yaml ファイルを読んで Zod 検証する。 失敗時は原因がわかる Error を投げる。
 */
export function loadAdultImprintsFile(filePath: string): AdultImprintsFile {
  if (!fs.existsSync(filePath)) {
    throw new Error(`adult-imprints yaml not found: ${filePath}`);
  }
  const raw = fs.readFileSync(filePath, "utf8");
  const parsed = YAML.parse(raw);
  const result = AdultImprintsFileSchema.safeParse(parsed);
  if (!result.success) {
    throw new Error(
      `adult-imprints 検証エラー: ${filePath}\n${JSON.stringify(result.error.format(), null, 2)}`,
    );
  }
  return result.data;
}
