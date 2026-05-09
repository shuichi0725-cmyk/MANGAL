/**
 * 種3 entries に Opus 直筆 fill を 適用する 汎用 runner。
 * data file (= JSON) を 引数で受け取り、 既存 entries を key match で 上書き。
 *
 * 起動: npx tsx scripts/_apply-fills.ts data/seeds/_fills/batch-001.json
 */
import "./_env";
import { readFileSync } from "node:fs";
import { writeSeed3, loadSeed3, type Seed3Entry, type Seed3File } from "../lib/seed3";

const fillsPath = process.argv[2];
if (!fillsPath) {
  console.error("usage: tsx scripts/_apply-fills.ts <fills.json>");
  process.exit(1);
}

type Fill = Omit<Seed3Entry, "key">;
const fills = JSON.parse(readFileSync(fillsPath, "utf8")) as Record<string, Fill>;

const existing = loadSeed3();
console.log(`[apply] existing: ${existing.size}, fills: ${Object.keys(fills).length}`);

let applied = 0;
let missingKeys: string[] = [];
for (const [key, fill] of Object.entries(fills)) {
  const cur = existing.get(key);
  if (!cur) {
    missingKeys.push(key);
    continue;
  }
  const merged: Seed3Entry = {
    key,
    ...(cur.slug || fill.slug ? { slug: fill.slug ?? cur.slug } : {}),
    ...(fill.magazine !== undefined ? { magazine: fill.magazine } : (cur.magazine !== undefined ? { magazine: cur.magazine } : {})),
    ...(fill.demographic ?? cur.demographic ? { demographic: fill.demographic ?? cur.demographic } : {}),
    ...(fill.genres && fill.genres.length > 0 ? { genres: fill.genres } : (cur.genres && cur.genres.length > 0 ? { genres: cur.genres } : {})),
    ...(fill.synopsis ?? cur.synopsis ? { synopsis: fill.synopsis ?? cur.synopsis } : {}),
    ...(fill.status ?? cur.status ? { status: fill.status ?? cur.status } : {}),
    ...(fill.anime_adapted !== undefined ? { anime_adapted: fill.anime_adapted } : (cur.anime_adapted !== undefined ? { anime_adapted: cur.anime_adapted } : {})),
    ...(fill.awards && fill.awards.length > 0 ? { awards: fill.awards } : (cur.awards && cur.awards.length > 0 ? { awards: cur.awards } : {})),
    ...(fill.alternative_titles ?? cur.alternative_titles ? { alternative_titles: fill.alternative_titles ?? cur.alternative_titles } : {}),
  };
  existing.set(key, merged);
  applied++;
}

if (missingKeys.length > 0) {
  console.warn(`[apply] missing keys (= no template entry, skipping):`);
  for (const k of missingKeys.slice(0, 10)) console.warn(`  ${k}`);
  if (missingKeys.length > 10) console.warn(`  ... and ${missingKeys.length - 10} more`);
}

const file: Seed3File = {
  schema_version: 1,
  generated_at: new Date().toISOString(),
  generator: "claude-opus-4-7-direct-fill",
  series: [...existing.values()].sort((a, b) => a.key.localeCompare(b.key)),
};
writeSeed3(file);

console.log(`[apply] done: applied=${applied}, missing=${missingKeys.length}, total entries=${existing.size}`);
