/**
 * clean-madb-seed.ts
 *
 * MADB 公式 dump (= 種1 = `.cache/madb/metadata101.json` の `@graph` array)
 * を streaming で読み、 record 単位で normalize した同形式 JSON (= 種2 =
 * `.cache/madb/metadata101-clean.json`) を出力する。
 *
 *   ┌────────────────────┐   normalize per record    ┌──────────────────────────┐
 *   │ metadata101.json   │ ───────────────────────► │ metadata101-clean.json   │
 *   │ (= 種1, immutable) │   schema:creator         │ (= 種2, normalize 済)    │
 *   └────────────────────┘   schema:name            └──────────────────────────┘
 *
 * 種2 で適用する変換 (= 段階導入の Step 1):
 *
 * 1. **schema:creator**: 旧 format `"[著]浦沢直樹,スタジオ・ナッツ"` を
 *    `["浦沢直樹", "スタジオ・ナッツ"]` に展開 (= cleanCreatorStrings 適用)。
 *    新 format (= clean array) は pass through。 これにより fetch-madb 側の
 *    extractRecord に冪等な二重 normalize がかかっても結果同じ。
 *
 * 2. **schema:name**: ja-hrkt 値群から「カタカナ/ひらがな含む値」 を最優先で
 *    ja-hrkt slot に残し、 ASCII-only 値は en slot に降格 (= rebuildSchemaName
 *    適用)。 進撃の巨人 / ZETMAN / PSYREN 等の 8.7% mixed records が直撃で
 *    解決され、 「attack on titan」 等の英文ヨミ採用が無くなる。
 *
 * 他 field (= schema:isbn / schema:position / schema:image / dcterms:creator
 * / schema:brand / schema:publisher / etc.) は **完全 pass through**。
 *
 * 設計原則:
 * - 種1 の record 数 と 種2 の record 数は **完全一致** を保証 (= zero data loss)。
 *   出力時に件数を track し、 入力件数と乖離したら error で停止。
 * - 種2 は git 管理外 (= .cache/ 配下、 既に gitignore)。
 * - extractRecord 側の cleanCreatorStrings / findKanaLiteral は維持
 *   (= defense in depth、 種1 を直接読む verify-coverage 等の tool が
 *   壊れないため)。
 *
 * 使い方:
 *   npx tsx scripts/clean-madb-seed.ts \
 *     --in  .cache/madb/metadata101.json \
 *     --out .cache/madb/metadata101-clean.json
 *
 * 大容量出力対応:
 *   入力 627MB / 出力 ~700MB を想定。 全体を JSON.stringify で 1 文字列に
 *   組むと Node の string size limit (= 0x1fffffe8 chars ≈ 512MB) で失敗
 *   するため、 fs.WriteStream で `[`, record JSON, `,`, ..., `]` を逐次書き
 *   出す stream 方式を採用。
 */
import "./_env";
import fs from "node:fs";
import chain from "stream-chain";
import sjParser from "stream-json";
import streamArray from "stream-json/streamers/stream-array.js";
import pick from "stream-json/filters/pick.js";

import {
  cleanCreatorStrings,
  flattenStringArray,
  rebuildSchemaName,
  type MadbJsonLdRecord,
} from "../lib/madb-jsonld";

type Args = {
  inPath: string;
  outPath: string;
};

function parseArgs(argv: string[]): Args {
  const out: Args = {
    inPath: ".cache/madb/metadata101.json",
    outPath: ".cache/madb/metadata101-clean.json",
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = argv[i + 1];
    if (a === "--in" && next) {
      out.inPath = next;
      i++;
    } else if (a === "--out" && next) {
      out.outPath = next;
      i++;
    }
  }
  return out;
}

/**
 * 1 record を normalize。 入力をそのまま variation する形ではなく、
 * shallow copy + 修正対象 field のみ上書きで返す (= 他 field 不変保証)。
 */
function normalizeRecord(
  raw: MadbJsonLdRecord,
  stats: NormalizeStats,
): MadbJsonLdRecord {
  const out: MadbJsonLdRecord = { ...raw };

  // 1. schema:creator: [著] strip + comma split
  if (raw["schema:creator"] !== undefined) {
    const flat = flattenStringArray(raw["schema:creator"]);
    const cleaned = cleanCreatorStrings(flat);
    // 何か変わったか judge: cleaned が flat と元の content / 件数 が違えば変更扱い
    const changed =
      cleaned.length !== flat.length ||
      cleaned.some((c, i) => c !== flat[i]);
    if (changed) {
      out["schema:creator"] = cleaned;
      stats.creatorNormalized++;
    } else {
      // 形式維持: 元 array なら array、 string なら string そのまま
      out["schema:creator"] = raw["schema:creator"];
    }
  }

  // 2. schema:name: ja-hrkt mixed → カタカナ優先 + ASCII を en に降格
  if (raw["schema:name"] !== undefined) {
    const before = raw["schema:name"];
    const after = rebuildSchemaName(before);
    out["schema:name"] = after;
    if (Array.isArray(before) && Array.isArray(after)) {
      // before 配列要素数 vs after 配列要素数の差 / 内容差 で変更判定
      const changed =
        before.length !== after.length ||
        JSON.stringify(before) !== JSON.stringify(after);
      if (changed) stats.schemaNameRebuilt++;
      else stats.schemaNameUnchanged++;
    } else {
      stats.schemaNameUnchanged++;
    }
  }

  return out;
}

type NormalizeStats = {
  totalRead: number;
  totalWritten: number;
  creatorNormalized: number;
  schemaNameRebuilt: number;
  schemaNameUnchanged: number;
};

async function main() {
  const args = parseArgs(process.argv.slice(2));

  if (!fs.existsSync(args.inPath)) {
    console.error(`[err] input not found: ${args.inPath}`);
    process.exit(1);
  }

  console.log(`[clean-madb-seed] in=${args.inPath} out=${args.outPath}`);

  const stats: NormalizeStats = {
    totalRead: 0,
    totalWritten: 0,
    creatorNormalized: 0,
    schemaNameRebuilt: 0,
    schemaNameUnchanged: 0,
  };

  // 出力 stream open。 JSON-LD 全体は { "@graph": [...record, ...record] }
  // 形式なので、 ブラケット + record を逐次書き出す。
  const outFp = fs.openSync(args.outPath, "w");
  const writeChunk = (chunk: string): void => {
    fs.writeSync(outFp, chunk);
  };

  writeChunk('{"@graph":[');

  const stream = chain([
    fs.createReadStream(args.inPath),
    sjParser(),
    pick({ filter: /^@graph$/ }),
    streamArray(),
  ]);

  for await (const item of stream as AsyncIterable<{
    key: number;
    value: MadbJsonLdRecord;
  }>) {
    stats.totalRead++;
    const cleaned = normalizeRecord(item.value, stats);
    if (stats.totalWritten > 0) writeChunk(",");
    writeChunk(JSON.stringify(cleaned));
    stats.totalWritten++;
    if (stats.totalWritten % 50000 === 0) {
      console.log(`  [progress] ${stats.totalWritten} records written`);
    }
  }

  writeChunk("]}");
  fs.closeSync(outFp);

  console.log("\n=== clean-madb-seed summary ===");
  console.log(`  total records read     : ${stats.totalRead}`);
  console.log(`  total records written  : ${stats.totalWritten}`);
  console.log(`  creator normalized     : ${stats.creatorNormalized}`);
  console.log(`  schema:name rebuilt    : ${stats.schemaNameRebuilt}`);
  console.log(`  schema:name unchanged  : ${stats.schemaNameUnchanged}`);
  console.log(`  output                 : ${args.outPath}`);

  if (stats.totalRead !== stats.totalWritten) {
    console.error(
      `\n[err] record count mismatch: read=${stats.totalRead}, written=${stats.totalWritten}`,
    );
    process.exit(1);
  }
  console.log(`\n[ok] zero data loss verified (= same record count)`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
