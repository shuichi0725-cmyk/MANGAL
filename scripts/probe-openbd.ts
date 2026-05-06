/**
 * B-2 (2026-05-06): openBD coverage probe (read-only).
 *
 * fetch:wikipedia の hit rate が 18% で構造的天井に達したため、 NDL から
 * すでに取れている ISBN を openBD で引いて、 不足している field
 * (title_kana / publisher / synopsis / subject codes) をどこまで埋められる
 * かを測定する。
 *
 * このスクリプトは **DB を変更しない**。 coverage と sample のみを
 * stdout に出力。 結果が良ければ次フェーズで `scripts/fetch-openbd.ts`
 * を bulk DB enrichment 仕様に書き換え (or 新設) する。
 *
 * openBD: https://api.openbd.jp/v1/get?isbn=<comma-separated>
 *   - 認証不要、 free
 *   - bulk 1 req = 1000 ISBN まで OK (公式)
 *   - 1.7K ISBN なら 2 req で済む
 */
import "./_env";
import { openDb } from "./_db";

const OPENBD_API = "https://api.openbd.jp/v1/get";
const BATCH_SIZE = 500;
const REQUEST_INTERVAL_MS = 500;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

type OpenBDEntry = {
  onix?: {
    DescriptiveDetail?: {
      TitleDetail?: Array<{
        TitleElement?: {
          TitleText?: { content?: string; collationkey?: string };
        };
      }>;
      Subject?: Array<{
        SubjectCode?: string;
        SubjectSchemeIdentifier?: string;
        SubjectHeadingText?: string;
      }>;
    };
    CollateralDetail?: {
      TextContent?: Array<{ TextType?: string; Text?: string }>;
    };
  };
  summary?: {
    title?: string;
    author?: string;
    publisher?: string;
    pubdate?: string;
    cover?: string;
    isbn?: string;
  };
};

function pct(num: number, denom: number): string {
  if (denom === 0) return "  -%";
  return `${Math.round((num * 100) / denom)
    .toString()
    .padStart(3, " ")}%`;
}

type SeriesAggregate = {
  publisher: string | null;
  kana: string | null;
  synopsis: string | null;
  cover: string | null;
  subjectCodes: string[];
};

async function main(): Promise<void> {
  const db = openDb();

  // Get all (volume_isbn, series_id) pairs.
  const rows = db
    .prepare(
      `SELECT v.isbn13 AS isbn13, e.series_id AS series_id, s.title AS series_title
       FROM volumes v
       JOIN editions e ON v.edition_id = e.id
       JOIN series s ON e.series_id = s.id
       WHERE v.isbn13 IS NOT NULL AND v.isbn13 != ''`,
    )
    .all() as { isbn13: string; series_id: number; series_title: string }[];

  const isbnToSeries = new Map<string, number>();
  const seriesIdToTitle = new Map<number, string>();
  for (const r of rows) {
    if (!isbnToSeries.has(r.isbn13)) isbnToSeries.set(r.isbn13, r.series_id);
    seriesIdToTitle.set(r.series_id, r.series_title);
  }

  const allIsbns = [...isbnToSeries.keys()];
  const totalSeries = seriesIdToTitle.size;
  console.log(
    `[openbd-probe] ${allIsbns.length} unique ISBNs across ${totalSeries} series`,
  );

  const stats = {
    isbnQueried: 0,
    isbnFound: 0,
    hasPublisher: 0,
    hasCollationkey: 0,
    hasSynopsis: 0,
    hasSubjectC: 0,
    hasCover: 0,
  };
  const seriesData = new Map<number, SeriesAggregate>();

  for (let i = 0; i < allIsbns.length; i += BATCH_SIZE) {
    const batch = allIsbns.slice(i, i + BATCH_SIZE);
    if (i > 0) await sleep(REQUEST_INTERVAL_MS);

    const url = `${OPENBD_API}?isbn=${batch.join(",")}`;
    let json: Array<OpenBDEntry | null>;
    try {
      const res = await fetch(url, {
        headers: {
          "User-Agent":
            "MANGAL-OpenBDProbe/0.1 (+https://github.com/shuichi0725-cmyk/MANGAL)",
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
      stats.isbnQueried++;
      const isbn = batch[j];
      const entry = json[j];
      const seriesId = isbnToSeries.get(isbn);
      if (!entry || !seriesId) continue;
      stats.isbnFound++;

      const pub = entry.summary?.publisher?.trim() || null;
      const cover = entry.summary?.cover || null;
      const titleDetails = entry.onix?.DescriptiveDetail?.TitleDetail ?? [];
      let kana: string | null = null;
      for (const td of titleDetails) {
        const ck = td.TitleElement?.TitleText?.collationkey;
        if (ck) {
          kana = ck;
          break;
        }
      }
      const text03 = entry.onix?.CollateralDetail?.TextContent?.find(
        (t) => t.TextType === "03",
      )?.Text;
      const synopsis = text03?.trim() || null;
      // Cコード = 日本図書コード分類。 SubjectSchemeIdentifier: "78"
      const subjectC =
        entry.onix?.DescriptiveDetail?.Subject?.filter(
          (s) => s.SubjectSchemeIdentifier === "78",
        ).map((s) => s.SubjectCode ?? "") ?? [];

      if (pub) stats.hasPublisher++;
      if (kana) stats.hasCollationkey++;
      if (synopsis) stats.hasSynopsis++;
      if (subjectC.length > 0) stats.hasSubjectC++;
      if (cover) stats.hasCover++;

      const existing: SeriesAggregate = seriesData.get(seriesId) ?? {
        publisher: null,
        kana: null,
        synopsis: null,
        cover: null,
        subjectCodes: [],
      };
      // Take first non-null per series (= first volume's data).
      if (!existing.publisher && pub) existing.publisher = pub;
      if (!existing.kana && kana) existing.kana = kana;
      if (!existing.synopsis && synopsis) existing.synopsis = synopsis;
      if (!existing.cover && cover) existing.cover = cover;
      for (const c of subjectC) {
        if (c && !existing.subjectCodes.includes(c)) {
          existing.subjectCodes.push(c);
        }
      }
      seriesData.set(seriesId, existing);
    }

    process.stdout.write(`.`);
  }
  console.log("");

  console.log("\n=== openBD probe coverage (per ISBN) ===");
  console.log(`  ISBNs queried        : ${stats.isbnQueried}`);
  console.log(
    `  ISBNs found          : ${stats.isbnFound} (${pct(stats.isbnFound, stats.isbnQueried)})`,
  );
  console.log(
    `  has publisher        : ${stats.hasPublisher} (${pct(stats.hasPublisher, stats.isbnFound)} of found)`,
  );
  console.log(
    `  has collationkey     : ${stats.hasCollationkey} (${pct(stats.hasCollationkey, stats.isbnFound)} of found)`,
  );
  console.log(
    `  has synopsis         : ${stats.hasSynopsis} (${pct(stats.hasSynopsis, stats.isbnFound)} of found)`,
  );
  console.log(
    `  has C-code           : ${stats.hasSubjectC} (${pct(stats.hasSubjectC, stats.isbnFound)} of found)`,
  );
  console.log(
    `  has cover            : ${stats.hasCover} (${pct(stats.hasCover, stats.isbnFound)} of found)`,
  );

  console.log("\n=== openBD probe coverage (per series) ===");
  const covered = seriesData.size;
  const withPub = [...seriesData.values()].filter((s) => s.publisher).length;
  const withKana = [...seriesData.values()].filter((s) => s.kana).length;
  const withSyn = [...seriesData.values()].filter((s) => s.synopsis).length;
  const withSubject = [...seriesData.values()].filter(
    (s) => s.subjectCodes.length > 0,
  ).length;
  const withCover = [...seriesData.values()].filter((s) => s.cover).length;
  console.log(
    `  series covered (>= 1 ISBN found) : ${covered} / ${totalSeries} (${pct(covered, totalSeries)})`,
  );
  console.log(
    `  with publisher       : ${withPub} (${pct(withPub, totalSeries)} of all series)`,
  );
  console.log(
    `  with collationkey    : ${withKana} (${pct(withKana, totalSeries)})`,
  );
  console.log(
    `  with synopsis        : ${withSyn} (${pct(withSyn, totalSeries)})`,
  );
  console.log(
    `  with C-code          : ${withSubject} (${pct(withSubject, totalSeries)})`,
  );
  console.log(
    `  with cover           : ${withCover} (${pct(withCover, totalSeries)})`,
  );

  // Sample observations: 5 series with synopsis, 10 with kana, 10 with C-code
  console.log("\n=== sample synopses (first 5 with non-empty) ===");
  let n = 0;
  for (const [sid, data] of seriesData) {
    if (!data.synopsis) continue;
    n++;
    if (n > 5) break;
    const t = seriesIdToTitle.get(sid) ?? `series-${sid}`;
    console.log(
      `  [${t}] ${data.synopsis.slice(0, 200).replace(/\n/g, " ")}${data.synopsis.length > 200 ? "..." : ""}`,
    );
  }

  console.log("\n=== sample collationkeys (first 10) ===");
  n = 0;
  for (const [sid, data] of seriesData) {
    if (!data.kana) continue;
    n++;
    if (n > 10) break;
    const t = seriesIdToTitle.get(sid) ?? `series-${sid}`;
    console.log(`  [${t}] ${data.kana}`);
  }

  console.log("\n=== sample C-code distribution (top 20) ===");
  const codeCount = new Map<string, number>();
  for (const data of seriesData.values()) {
    for (const c of data.subjectCodes) {
      codeCount.set(c, (codeCount.get(c) ?? 0) + 1);
    }
  }
  const topCodes = [...codeCount.entries()].sort((a, b) => b[1] - a[1]).slice(0, 20);
  for (const [code, count] of topCodes) {
    console.log(`  ${count.toString().padStart(3, " ")}× ${code}`);
  }

  db.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
