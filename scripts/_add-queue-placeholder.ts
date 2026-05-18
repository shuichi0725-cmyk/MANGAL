import "./_env";
import { readFileSync } from "node:fs";
import yaml from "yaml";
import { loadSeed3, writeSeed3, type Seed3Entry } from "../lib/seed3";

const start = Number(process.argv[2] ?? 2000);
const end = Number(process.argv[3] ?? 4000);
if (!Number.isFinite(start) || !Number.isFinite(end) || start >= end) {
  console.error("usage: tsx scripts/_add-queue-placeholder.ts <start-idx> <end-idx>");
  console.error("       (= 0-based half-open range over _ai-fill-queue.yml entries)");
  process.exit(1);
}

const queue = yaml.parse(readFileSync("data/seeds/_ai-fill-queue.yml", "utf8")) as {
  entries: { key: string }[];
};

const existing = loadSeed3();
const before = existing.size;
let added = 0;
let skipped = 0;
for (let i = start; i < end; i++) {
  const e = queue.entries[i];
  if (!e) break;
  if (existing.has(e.key)) {
    skipped++;
    continue;
  }
  const placeholder: Seed3Entry = { key: e.key };
  existing.set(e.key, placeholder);
  added++;
}

writeSeed3({
  schema_version: 1,
  generated_at: new Date().toISOString(),
  generator: "claude-opus-4-7-direct-fill",
  series: [...existing.values()].sort((a, b) => a.key.localeCompare(b.key)),
});

console.log(`[placeholder] range=[${start},${end}), added=${added}, skipped(already exists)=${skipped}, total=${before}→${existing.size}`);
