/**
 * Tier 2: data/seeds/adult-imprints.yml の Zod schema + reader。
 *
 * yaml は scripts/clean-imprint-dump.ts が raw dump から自動生成する。
 * 手書きの追記もできるが、 raw dump 側に追加するのが正攻法。
 *
 * adult_imprints テーブルへ INSERT するのは imprints セクションのみ。
 * 他のセクションは false-positive 防止のため絶対に INSERT しない:
 *   - distribution_channels: imprint は adult だが publisher が配信プラットフォーム
 *   - ambiguous:             同名 imprint × 複数 publisher (= mainstream/adult collision)
 *   - false_positives:       probe-adult-imprints の結果 FP rate >=50% で
 *                            mainstream 寄りと判明した seed (= 過去に投入していたが
 *                            誤検出を起こすので除外)
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

/**
 * probe-adult-imprints (= MADB JSON-LD vs contentRating) で FP 率が高いと
 * 判明した seed。 imprints から除外し、 ここに記録 (= 履歴として残す)。
 */
export const AdultFalsePositiveSchema = z.object({
  imprint: z.string().min(1),
  publisher: z.string().min(1),
  fp_total: z.number().int().nonnegative(),
  fp_rate: z.number().min(0).max(100),
  total_hits: z.number().int().nonnegative(),
  note: z.string().optional(),
});
export type AdultFalsePositive = z.infer<typeof AdultFalsePositiveSchema>;

export const AdultImprintsFileSchema = z.object({
  schema_version: z.number().int().positive(),
  imprints: z.array(AdultImprintEntrySchema),
  distribution_channels: z.array(AdultDistributionChannelSchema).optional(),
  ambiguous: z.array(AdultAmbiguousSchema).optional(),
  false_positives: z.array(AdultFalsePositiveSchema).optional(),
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
