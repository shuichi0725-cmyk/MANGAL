/**
 * B-2 (2026-05-06): openBD bulk enrichment for `series.title_kana`.
 *
 * 試験 (probe-openbd.ts) の結果、 openBD の useful な情報は collationkey
 * (= ヨミガナ) のみ。 publisher は既に NDL 由来 fallback で 79% 埋まっている、
 * synopsis / cover / Cコード はカバー率 1〜2% で実用にならない。 そのため
 * このスクリプトは **title_kana だけ** を埋める専用設計。
 *
 * 実行順序: fetch:wikipedia の直後 (Wikipedia 由来 kana は優先、 残りを openBD
 * で埋める)。 既に title_kana が non-empty の series はスキップする。
 *
 * openBD: https://api.openbd.jp/v1/get?isbn=<comma-separated>
 */
import "./_env";
import { openDb, recordSource, tx } from "./_db";
import { cleanCollationKey } from "../lib/openbd-kana";

const OPENBD_API = "https://api.openbd.jp/v1/get";
const BATCH_SIZE = 500;
const REQUEST_INTERVAL_MS = 500;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

type OpenBDEntry = {
  onix?: {
    DescriptiveDetail?: {
      TitleDetail?:
        | {
            TitleElement?: {
              TitleText?: { content?: string; collationkey?: string };
            };
          }
        | Array<{
            TitleElement?: {
              TitleText?: { content?: string; collationkey?: string };
            };
          }>;
    };
  };
  summary?: {
    isbn?: string;
  };
};

function asArray<T>(x: T | T[] | undefined | null): T[] {
  if (x === null || x === undefined) return [];
  return Array.isArray(x) ? x : [x];
}

function extractCollationKey(entry: OpenBDEntry): string | null {
  const titleDetails = asArray(entry.onix?.DescriptiveDetail?.TitleDetail);
  for (const td of titleDetails) {
    const ck = td.TitleElement?.TitleText?.collationkey;
    if (ck) return ck;
  }
  return null;
}

async function main(): Promise<void> {
  const db = openDb();

  // Target: series whose title_kana is empty/null.
  // Wikipedia 由来 で既に埋まっているものは触らない。
  const targetSeries = db
    .prepare(
      `SELECT s.id, s.title
       FROM series s
       WHERE s.title_kana IS NULL OR s.title_kana = ''`,
    )
    .all() as { id: number; title: string }[];

  if (targetSeries.length === 0) {
    console.log("[openbd-bulk] no series need title_kana, exiting");
    db.close();
    return;
  }

  // For each target series, get its volumes' ISBN13.
  const targetIds = targetSeries.map((s) => s.id);
  const placeholder = targetIds.map(() => "?").join(",");
  const isbnRows = db
    .prepare(
      `SELECT v.isbn13 AS isbn13, e.series_id AS series_id
       FROM volumes v
       JOIN editions e ON v.edition_id = e.id
       WHERE v.isbn13 IS NOT NULL AND v.isbn13 != ''
         AND e.series_id IN (${placeholder})
       ORDER BY e.series_id, v.number`,
    )
    .all(...targetIds) as { isbn13: string; series_id: number }[];

  // Map ISBN → first series_id (handles dup ISBNs across editions).
  // Also build series_id → list of ISBNs for diagnostic.
  const isbnToSeries = new Map<string, number>();
  for (const r of isbnRows) {
    if (!isbnToSeries.has(r.isbn13)) isbnToSeries.set(r.isbn13, r.series_id);
  }
  const allIsbns = [...isbnToSeries.keys()];
  console.log(
    `[openbd-bulk] ${targetSeries.length} series need title_kana, ${allIsbns.length} ISBNs to query`,
  );

  if (allIsbns.length === 0) {
    db.close();
    return;
  }

  // Per-series: first non-empty cleaned kana wins (= first volume's value).
  const kanaPerSeries = new Map<number, { isbn: string; kana: string }>();

  let isbnFound = 0;
  let collationkeyExtracted = 0;
  for (let i = 0; i < allIsbns.length; i += BATCH_SIZE) {
    const batch = allIsbns.slice(i, i + BATCH_SIZE);
    if (i > 0) await sleep(REQUEST_INTERVAL_MS);

    const url = `${OPENBD_API}?isbn=${batch.join(",")}`;
    let json: Array<OpenBDEntry | null>;
    try {
      const res = await fetch(url, {
        headers: {
          "User-Agent":
            "MANGAL-OpenBDBulk/0.1 (+https://github.com/shuichi0725-cmyk/MANGAL)",
        },
      });
      if (!res.ok) {
        console.warn(
          `  batch ${i}-${i + batch.length}: HTTP ${res.status}, skipping`,
        );
        continue;
      }
      json = (await res.json()) as Array<OpenBDEntry | null>;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.warn(
        `  batch ${i}-${i + batch.length}: ${msg.slice(0, 100)}, skipping`,
      );
      continue;
    }

    for (let j = 0; j < json.length; j++) {
      const isbn = batch[j];
      const entry = json[j];
      const seriesId = isbnToSeries.get(isbn);
      if (!entry || !seriesId) continue;
      isbnFound++;

      const rawCk = extractCollationKey(entry);
      if (!rawCk) continue;
      collationkeyExtracted++;

      const kana = cleanCollationKey(rawCk);
      if (!kana) continue;

      // First volume of each series wins.
      if (!kanaPerSeries.has(seriesId)) {
        kanaPerSeries.set(seriesId, { isbn, kana });
      }
    }
    process.stdout.write(`.`);
  }
  console.log("");

  // Apply updates. Guarded by the same `title_kana IS NULL OR ''` predicate to
  // be safe against concurrent writes (no concurrency expected, but cheap).
  const updateStmt = db.prepare(
    `UPDATE series
     SET title_kana = ?,
         updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
     WHERE id = ? AND (title_kana IS NULL OR title_kana = '')`,
  );

  let updated = 0;
  tx(db, () => {
    for (const [sid, { isbn, kana }] of kanaPerSeries) {
      const result = updateStmt.run(kana, sid);
      if (result.changes > 0) {
        updated++;
        recordSource(db, "openbd", "series", String(sid), {
          isbn,
          collationkey_to_kana: kana,
        });
      }
    }
  });

  console.log(`\n=== fetch:openbd-bulk summary ===`);
  console.log(`  series queried           : ${targetSeries.length}`);
  console.log(`  ISBNs queried            : ${allIsbns.length}`);
  console.log(`  ISBNs found in openBD    : ${isbnFound}`);
  console.log(`  with collationkey raw    : ${collationkeyExtracted}`);
  console.log(`  series with usable kana  : ${kanaPerSeries.size}`);
  console.log(`  series.title_kana written: ${updated}`);

  db.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
