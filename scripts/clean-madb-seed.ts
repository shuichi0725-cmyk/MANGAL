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
  splitMadbLiteral,
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
  imprintCanonical: Map<string, string>,
  publisherCanonical: Map<string, string>,
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

  // 3. schema:brand: 大文字小文字 揺れ統一 (= imprint canonical 形に置換)
  //    例: "My first big" / "My First BIG" / "My First Big" → "My first big" (= 最頻出)
  //    Pass 1 (= aggregateImprints) で集計済の canonical map を参照。
  //    string 値は置換、 object (= ヨミ etc.) / @id 参照 は pass through。
  //    case 違いが無い (= group 内 form 1 個) imprint は何も変わらない。
  if (raw["schema:brand"] !== undefined) {
    const before = raw["schema:brand"];
    const replaced = applyImprintCanonical(before, imprintCanonical) as
      | typeof before;
    out["schema:brand"] = replaced;
    if (JSON.stringify(before) !== JSON.stringify(replaced)) {
      stats.brandNormalized++;
    }
  }

  // 4. schema:publisher: ∥ split + case 揺れ統一
  //    例: "KADOKAWA ∥ カドカワ" → "KADOKAWA"
  //    例: "Kadokawa" → "KADOKAWA" (= canonical 引き)
  //    fetch-madb.ts:472 の `imprint = rec.imprint ?? rec.publisher` fallback
  //    経由で imprint に流れる publisher 値を 種2 で先に統一しておくことで、
  //    DB の editions.imprint で "KADOKAWA" / "Kadokawa" 混在を防ぐ。
  //    array なら各要素を再帰、 object (= ヨミ) は pass through。
  if (raw["schema:publisher"] !== undefined) {
    const before = raw["schema:publisher"];
    const replaced = applyPublisherCanonical(
      before,
      publisherCanonical,
    ) as typeof before;
    out["schema:publisher"] = replaced;
    if (JSON.stringify(before) !== JSON.stringify(replaced)) {
      stats.publisherNormalized++;
    }
  }

  return out;
}

/**
 * publisher 値に canonical map を適用。 string なら ∥ split で 漢字部分を取り出し、
 * lowercase 引きで canonical 形に置換。 array は再帰、 object は pass through。
 *
 *   "KADOKAWA ∥ カドカワ" → split → "KADOKAWA" → lookup → "KADOKAWA" (canonical)
 *   "Kadokawa"            → split → "Kadokawa" → lookup → "KADOKAWA" (canonical)
 *   "集英社 ∥ シュウエイシャ" → split → "集英社" → lookup → "集英社" (no change)
 *
 * 結果: 種2 の schema:publisher は ∥ 抜き + canonical case 形だけになる。
 * 既存 splitMadbLiteral を extractRecord で重複 apply しても冪等 (= no-op)。
 */
function applyPublisherCanonical(
  field: unknown,
  canonical: Map<string, string>,
): unknown {
  if (typeof field === "string") {
    const split = splitMadbLiteral(field);
    if (!split) return field;
    const key = split.normalize("NFKC").toLowerCase().trim();
    return canonical.get(key) ?? split;
  }
  if (Array.isArray(field)) {
    return field.map((x) => applyPublisherCanonical(x, canonical));
  }
  return field;
}

/**
 * brand 値に canonical map を適用。 string なら lowercase 引きで canonical に
 * 置換。 array なら各要素を再帰処理 (= object はそのまま、 string は置換)。
 * canonical map に key 不在なら元値を保持 (= 安全)。
 */
function applyImprintCanonical(
  field: unknown,
  canonical: Map<string, string>,
): unknown {
  if (typeof field === "string") {
    const key = field.normalize("NFKC").toLowerCase().trim();
    return canonical.get(key) ?? field;
  }
  if (Array.isArray(field)) {
    return field.map((x) => applyImprintCanonical(x, canonical));
  }
  return field;
}

/**
 * 同 lowercase key の中で 「最頻出 form」 を canonical として選択。 同点は
 * code-point 順 (= deterministic)。 単一 form の group は map に入れない
 * (= no-op で十分)。
 */
function pickCanonicalFromGroups(
  groups: Map<string, Map<string, number>>,
): { canonical: Map<string, string>; groupsWithVariation: number } {
  const canonical = new Map<string, string>();
  let groupsWithVariation = 0;
  for (const [lower, formMap] of groups) {
    if (formMap.size === 1) continue;
    groupsWithVariation++;
    let bestForm = "";
    let bestCount = -1;
    for (const [form, count] of formMap) {
      if (
        count > bestCount ||
        (count === bestCount && form < bestForm)
      ) {
        bestForm = form;
        bestCount = count;
      }
    }
    canonical.set(lower, bestForm);
  }
  return { canonical, groupsWithVariation };
}

/**
 * 1st pass: 全 record を scan して schema:brand と schema:publisher を同時集計。
 * 両 field とも 「最頻出 form を canonical として選ぶ」 同じ algorithm だが、
 * publisher は **∥ split 後の漢字部分** で集計する点が異なる (= 「集英社 ∥
 * シュウエイシャ」 の漢字部分 「集英社」 で grouping)。
 */
async function aggregateBrandsAndPublishers(
  inPath: string,
): Promise<{
  brandCanonical: Map<string, string>;
  brandTotalGroups: number;
  brandGroupsWithVariation: number;
  publisherCanonical: Map<string, string>;
  publisherTotalGroups: number;
  publisherGroupsWithVariation: number;
}> {
  const brandGroups = new Map<string, Map<string, number>>();
  const publisherGroups = new Map<string, Map<string, number>>();

  const stream = chain([
    fs.createReadStream(inPath),
    sjParser(),
    pick({ filter: /^@graph$/ }),
    streamArray(),
  ]);

  let recordsScanned = 0;
  for await (const item of stream as AsyncIterable<{
    key: number;
    value: MadbJsonLdRecord;
  }>) {
    recordsScanned++;

    // brand 集計: NFKC + lowercase + trim を group key に。
    // form は NFKC + trim で保管 (= 末尾の全角空白等を削除、 case は保持)。
    // これで 「きみとぼくCOLLECTION　」 (末尾 U+3000) と 「きみとぼくcollection」
    // が同 group に集約され、 canonical も末尾空白なしの形になる。
    const brand = item.value["schema:brand"];
    if (brand !== undefined && brand !== null) {
      const visitBrand = (v: unknown): void => {
        if (typeof v === "string" && v) {
          const key = v.normalize("NFKC").toLowerCase().trim();
          if (!key) return;
          const form = v.normalize("NFKC").trim();
          const inner = brandGroups.get(key);
          if (inner) inner.set(form, (inner.get(form) || 0) + 1);
          else brandGroups.set(key, new Map([[form, 1]]));
        } else if (Array.isArray(v)) {
          for (const x of v) visitBrand(x);
        }
      };
      visitBrand(brand);
    }

    // publisher 集計: ∥ split → NFKC + lowercase + trim を key に
    const pub = item.value["schema:publisher"];
    if (pub !== undefined && pub !== null) {
      const visitPub = (v: unknown): void => {
        if (typeof v === "string" && v) {
          const split = splitMadbLiteral(v);
          if (!split) return;
          const key = split.normalize("NFKC").toLowerCase().trim();
          if (!key) return;
          const form = split.normalize("NFKC").trim();
          const inner = publisherGroups.get(key);
          if (inner) inner.set(form, (inner.get(form) || 0) + 1);
          else publisherGroups.set(key, new Map([[form, 1]]));
        } else if (Array.isArray(v)) {
          for (const x of v) visitPub(x);
        }
      };
      visitPub(pub);
    }

    if (recordsScanned % 100000 === 0) {
      console.log(`  [agg-pass] ${recordsScanned} records scanned`);
    }
  }

  const brandResult = pickCanonicalFromGroups(brandGroups);
  const publisherResult = pickCanonicalFromGroups(publisherGroups);

  return {
    brandCanonical: brandResult.canonical,
    brandTotalGroups: brandGroups.size,
    brandGroupsWithVariation: brandResult.groupsWithVariation,
    publisherCanonical: publisherResult.canonical,
    publisherTotalGroups: publisherGroups.size,
    publisherGroupsWithVariation: publisherResult.groupsWithVariation,
  };
}

type NormalizeStats = {
  totalRead: number;
  totalWritten: number;
  creatorNormalized: number;
  schemaNameRebuilt: number;
  schemaNameUnchanged: number;
  brandNormalized: number;
  publisherNormalized: number;
};

async function main() {
  const args = parseArgs(process.argv.slice(2));

  if (!fs.existsSync(args.inPath)) {
    console.error(`[err] input not found: ${args.inPath}`);
    process.exit(1);
  }

  console.log(`[clean-madb-seed] in=${args.inPath} out=${args.outPath}`);

  // === Pass 1: brand + publisher 集計 ===
  console.log(`\n[pass 1/2] aggregating brand + publisher case variations...`);
  const t0 = Date.now();
  const aggResult = await aggregateBrandsAndPublishers(args.inPath);
  const elapsed1 = ((Date.now() - t0) / 1000).toFixed(1);
  console.log(
    `  done in ${elapsed1}s:\n` +
      `    brand     ${aggResult.brandTotalGroups} unique groups, ${aggResult.brandGroupsWithVariation} with case var, ${aggResult.brandCanonical.size} canonical\n` +
      `    publisher ${aggResult.publisherTotalGroups} unique groups (after ∥ split), ${aggResult.publisherGroupsWithVariation} with case var, ${aggResult.publisherCanonical.size} canonical`,
  );

  const stats: NormalizeStats = {
    totalRead: 0,
    totalWritten: 0,
    creatorNormalized: 0,
    schemaNameRebuilt: 0,
    schemaNameUnchanged: 0,
    brandNormalized: 0,
    publisherNormalized: 0,
  };

  // === Pass 2: 出力 ===
  console.log(`\n[pass 2/2] writing normalized records...`);
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
    const cleaned = normalizeRecord(
      item.value,
      stats,
      aggResult.brandCanonical,
      aggResult.publisherCanonical,
    );
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
  console.log(`  brand normalized       : ${stats.brandNormalized}`);
  console.log(`  publisher normalized   : ${stats.publisherNormalized}`);
  console.log(`  brand groups           : ${aggResult.brandTotalGroups}`);
  console.log(`  brand w/ case var      : ${aggResult.brandGroupsWithVariation}`);
  console.log(`  publisher groups       : ${aggResult.publisherTotalGroups}`);
  console.log(`  publisher w/ case var  : ${aggResult.publisherGroupsWithVariation}`);
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
