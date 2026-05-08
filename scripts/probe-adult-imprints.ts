/**
 * adult_imprints seed の false-positive 検出 probe。
 *
 * 目的: MADB JSON-LD を 1 パス scan し、 adult_imprints テーブルにある
 * imprint ごとに以下を集計:
 *   - 総 hit 数 (= editions.imprint == imprint の record 数)
 *   - true-positive (= contentRating="成年コミック" 同時に立っている)
 *   - false-positive (= contentRating="" だが imprint match)
 *   - false-positive のサンプルタイトル
 *
 * false-positive 率が高い imprint = mainstream。 seed から除外候補。
 *
 * 使い方:
 *   tsx scripts/probe-adult-imprints.ts --jsonld-path .cache/madb/metadata101.json
 */
import "./_env";
import fs from "node:fs";
import chain from "stream-chain";
import sjParser from "stream-json";
import streamArray from "stream-json/streamers/stream-array.js";
import pick from "stream-json/filters/pick.js";
import { extractRecord, type MadbJsonLdRecord } from "../lib/madb-jsonld";
import { openDb } from "./_db";

type Args = { jsonldPath: string | null; limit: number | null };

function parseArgs(argv: string[]): Args {
  const out: Args = { jsonldPath: null, limit: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = argv[i + 1];
    if (a === "--jsonld-path" && next) {
      out.jsonldPath = next;
      i++;
    } else if (a === "--limit" && next) {
      out.limit = Number(next);
      i++;
    }
  }
  return out;
}

type ImprintStat = {
  imprint: string;
  total: number;
  truePositive: number;
  falsePositive: number;
  falsePositiveSamples: string[];
};

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  if (!args.jsonldPath) {
    console.error("usage: probe-adult-imprints --jsonld-path <path> [--limit N]");
    process.exit(1);
  }

  const db = openDb();
  const adultImprints = new Set<string>();
  for (const r of db.prepare("SELECT imprint FROM adult_imprints").all() as {
    imprint: string;
  }[]) {
    adultImprints.add(r.imprint.normalize("NFKC"));
  }
  db.close();
  console.log(`[seed] adult_imprints loaded: ${adultImprints.size}`);

  const stats = new Map<string, ImprintStat>();
  for (const imp of adultImprints) {
    stats.set(imp, {
      imprint: imp,
      total: 0,
      truePositive: 0,
      falsePositive: 0,
      falsePositiveSamples: [],
    });
  }

  let processed = 0;
  const stream = chain([
    fs.createReadStream(args.jsonldPath),
    sjParser(),
    pick({ filter: /^@graph$/ }),
    streamArray(),
  ]);

  for await (const item of stream) {
    const value = (item as { key: number; value: MadbJsonLdRecord }).value;
    processed++;
    if (args.limit !== null && processed > args.limit) break;
    if (processed % 50000 === 0) {
      console.log(`[progress] ${processed}`);
    }
    const rec = extractRecord(value);
    if (!rec) continue;
    if (!rec.brand) continue;
    const norm = rec.brand.normalize("NFKC");
    const stat = stats.get(norm);
    if (!stat) continue;
    stat.total++;
    if (rec.rating === "成年コミック") {
      stat.truePositive++;
    } else {
      stat.falsePositive++;
      if (stat.falsePositiveSamples.length < 3) {
        stat.falsePositiveSamples.push(rec.title || "(no title)");
      }
    }
  }

  console.log(`\n[scan] processed=${processed}\n`);

  // false-positive 多い順に並べる (= mainstream 度高い)
  const sorted = [...stats.values()]
    .filter((s) => s.total > 0)
    .sort((a, b) => b.falsePositive - a.falsePositive);

  console.log(
    "imprint | total | TP (成年=true) | FP (成年=false) | FP rate | FP samples",
  );
  console.log(
    "------ | ----- | -------------- | --------------- | ------- | -----------",
  );
  for (const s of sorted) {
    const fpRate =
      s.total > 0 ? ((s.falsePositive / s.total) * 100).toFixed(1) : "?";
    const samples = s.falsePositiveSamples.join(" / ");
    console.log(
      `${s.imprint} | ${s.total} | ${s.truePositive} | ${s.falsePositive} | ${fpRate}% | ${samples}`,
    );
  }

  // hit ゼロ entry (= seed にあるが MADB に出ない) を別表示
  const zeroHit = [...stats.values()].filter((s) => s.total === 0);
  console.log(
    `\n[zero-hit] ${zeroHit.length} adult_imprints entries had no records in MADB`,
  );
  if (zeroHit.length > 0 && zeroHit.length <= 30) {
    for (const s of zeroHit) console.log(`  ${s.imprint}`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
