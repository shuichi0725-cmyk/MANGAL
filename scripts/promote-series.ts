/**
 * SQLite に投入済みのシリーズを `data/manga/<slug>.yml` に昇格させる。
 * NDL から取れない人手必須メタ (publisher/magazine/demographic/genres/synopsis)
 * は CLI 引数で受け取り、Zod 検証を通過させてから書き出す。
 *
 *   npm run promote:series -- \
 *     --qid Q219948 \
 *     --slug urusei-yatsura \
 *     --title-match "うる星やつら" \
 *     --title-romaji "urusei yatsura" \
 *     --publisher shogakukan \
 *     --magazine weekly-shonen-sunday \
 *     --demographic shounen \
 *     --genres comedy,romcom,sci-fi \
 *     --status completed \
 *     --synopsis "高校生の諸星あたると..."
 *
 * 仕様:
 *   - is_extra=1 / number<1 の volume は除外（Zod の number.min(1) 制約のため）
 *   - editions は year_started の昇順で並べる
 *   - title_kana は --title-kana > SQLite の series.title_kana > "TODO_kana" の順
 *   - 既存の data/manga/<slug>.yml は --force なしでは上書きしない
 */
import "./_env";
import fs from "node:fs";
import path from "node:path";
import YAML from "yaml";
import { openDb, type DB } from "./_db";
import { MangaSchema } from "../lib/schema";

type Args = {
  qid: string;
  slug: string;
  titleMatch: string | null;
  seriesId: number | null;
  publisher: string;
  magazine: string | null;
  demographic: string;
  genres: string[];
  status: "ongoing" | "completed" | "hiatus";
  synopsis: string;
  titleKana: string | null;
  titleRomaji: string;
  out: string | null;
  force: boolean;
  dryRun: boolean;
};

function parseArgs(argv: string[]): Args {
  const out: Args = {
    qid: "",
    slug: "",
    titleMatch: null,
    seriesId: null,
    publisher: "",
    magazine: null,
    demographic: "",
    genres: [],
    status: "completed",
    synopsis: "",
    titleKana: null,
    titleRomaji: "",
    out: null,
    force: false,
    dryRun: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = argv[i + 1];
    const take = () => {
      i++;
      return next ?? "";
    };
    if (a === "--qid" && next) out.qid = take();
    else if (a === "--slug" && next) out.slug = take();
    else if (a === "--title-match" && next) out.titleMatch = take();
    else if (a === "--series-id" && next) out.seriesId = Number(take());
    else if (a === "--publisher" && next) out.publisher = take();
    else if (a === "--magazine" && next) {
      const v = take();
      out.magazine = v ? v : null;
    } else if (a === "--demographic" && next) out.demographic = take();
    else if (a === "--genres" && next) {
      out.genres = take()
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
    } else if (a === "--status" && next) {
      const v = take();
      if (v === "ongoing" || v === "completed" || v === "hiatus") {
        out.status = v;
      } else {
        throw new Error(`--status must be ongoing|completed|hiatus, got '${v}'`);
      }
    } else if (a === "--synopsis" && next) out.synopsis = take();
    else if (a === "--title-kana" && next) out.titleKana = take();
    else if (a === "--title-romaji" && next) out.titleRomaji = take();
    else if (a === "--out" && next) out.out = take();
    else if (a === "--force") out.force = true;
    else if (a === "--dry-run") out.dryRun = true;
  }
  return out;
}

type SeriesRow = {
  id: number;
  series_key: string;
  qid: string | null;
  title: string;
  title_kana: string | null;
  year_started: number | null;
  year_ended: number | null;
  status: string | null;
  publisher_key: string | null;
  magazine_key: string | null;
};

function findSeries(
  db: DB,
  mangakaId: number,
  args: Args,
): SeriesRow | undefined {
  if (args.seriesId !== null) {
    return db
      .prepare("SELECT * FROM series WHERE id = ?")
      .get(args.seriesId) as SeriesRow | undefined;
  }
  if (!args.titleMatch) return undefined;
  // title 部分一致 + 巻数最大のシリーズを採用
  const candidates = db
    .prepare(
      `SELECT s.*,
              COUNT(DISTINCT v.id) AS vols
       FROM series s
       JOIN series_authors sa ON sa.series_id = s.id
       LEFT JOIN editions e ON e.series_id = s.id
       LEFT JOIN volumes  v ON v.edition_id = e.id
       WHERE sa.mangaka_id = ? AND s.title LIKE ?
       GROUP BY s.id
       ORDER BY vols DESC, s.id
       LIMIT 1`,
    )
    .get(mangakaId, `%${args.titleMatch}%`) as
    | (SeriesRow & { vols: number })
    | undefined;
  return candidates;
}

type EditionRow = {
  id: number;
  type: string;
  label: string;
  imprint: string | null;
  year_started: number | null;
  year_ended: number | null;
};

type VolumeRow = {
  number: number;
  isbn13: string;
  release_date: string | null;
  cover_url: string | null;
  asin: string | null;
};

function buildEditions(db: DB, seriesId: number) {
  const editions = db
    .prepare(
      `SELECT id, type, label, imprint, year_started, year_ended
       FROM editions
       WHERE series_id = ?
       ORDER BY COALESCE(year_started, 9999), type`,
    )
    .all(seriesId) as EditionRow[];

  const out = editions.map((e) => {
    const vols = db
      .prepare(
        `SELECT number, isbn13, release_date, cover_url, asin
         FROM volumes
         WHERE edition_id = ? AND is_extra = 0 AND number >= 1
         ORDER BY number, isbn13`,
      )
      .all(e.id) as VolumeRow[];

    // 同一 (edition, number) で複数 ISBN があるケース（NDL 重複の名残）は
    // 最初の 1 件だけ採用。重複は db:report --top で警告済み。
    const seenNumbers = new Set<number>();
    const uniqueVols = vols.filter((v) => {
      if (seenNumbers.has(v.number)) return false;
      seenNumbers.add(v.number);
      return true;
    });

    return {
      type: e.type,
      label: e.label,
      ...(e.imprint ? { imprint: e.imprint } : {}),
      ...(e.year_started !== null ? { year_started: e.year_started } : {}),
      ...(e.year_ended !== null ? { year_ended: e.year_ended } : {}),
      volumes: uniqueVols.map((v) => ({
        number: v.number,
        asin: v.asin,
        isbn13: v.isbn13,
        cover_url: v.cover_url,
        release_date: v.release_date,
      })),
    };
  });

  return out.filter((e) => e.volumes.length > 0);
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.qid || !args.slug || !args.publisher || !args.demographic) {
    console.error(
      "Usage: --qid Q219948 --slug urusei-yatsura --title-match うる星やつら \\\n" +
        "       --publisher shogakukan --demographic shounen --genres comedy,romcom,sci-fi \\\n" +
        "       --title-romaji 'urusei yatsura' [--magazine weekly-shonen-sunday] \\\n" +
        "       [--status completed] [--synopsis '...'] [--title-kana うるせいやつら]",
    );
    process.exit(1);
  }
  if (args.genres.length === 0) {
    console.error("--genres は 1 つ以上必要");
    process.exit(1);
  }
  if (!args.titleRomaji) {
    console.error("--title-romaji は必須");
    process.exit(1);
  }

  const db = openDb();

  const mangaka = db
    .prepare("SELECT id, name FROM mangaka WHERE qid = ?")
    .get(args.qid) as { id: number; name: string } | undefined;
  if (!mangaka) {
    console.error(`mangaka qid=${args.qid} が SQLite に見つかりません。`);
    process.exit(1);
  }

  const series = findSeries(db, mangaka.id, args);
  if (!series) {
    console.error(
      `series が見つかりません (mangaka ${mangaka.name} / title-match '${args.titleMatch}' / series-id ${args.seriesId}).`,
    );
    process.exit(1);
  }
  console.log(
    `[promote] series #${series.id} '${series.title}' (mangaka ${mangaka.name})`,
  );

  const editions = buildEditions(db, series.id);
  if (editions.length === 0) {
    console.error("採用可能な edition がありません (全 edition が is_extra のみ等)");
    process.exit(1);
  }

  // year_started / year_ended は standard 優先 → 無ければ最も古い edition から
  const standardEdition =
    editions.find((e) => e.type === "standard") ?? editions[0];
  const yearStarted =
    standardEdition.year_started ?? series.year_started ?? null;
  const yearEnded =
    standardEdition.year_ended ?? series.year_ended ?? null;

  const manga = {
    slug: args.slug,
    title: series.title,
    title_kana: args.titleKana ?? series.title_kana ?? "TODO_kana",
    title_romaji: args.titleRomaji,
    year_started: yearStarted ?? 2000,
    year_ended: yearEnded ?? null,
    status: args.status,
    authors: [{ name: mangaka.name, role: "writer_artist" as const }],
    original_authors: [],
    publisher: args.publisher,
    magazine: args.magazine,
    demographic: args.demographic,
    genres: args.genres,
    synopsis: args.synopsis,
    editions,
  };

  const result = MangaSchema.safeParse(manga);
  if (!result.success) {
    console.error("Zod validation failed:");
    console.error(JSON.stringify(result.error.format(), null, 2));
    process.exit(1);
  }

  const outPath = args.out ?? path.join("data", "manga", `${args.slug}.yml`);
  if (!args.force && fs.existsSync(outPath)) {
    console.error(
      `${outPath} は既に存在します。上書きするには --force を付けてください。`,
    );
    process.exit(1);
  }

  const yamlText =
    `# Promoted from SQLite NDL pipeline by scripts/promote-series.ts\n` +
    `# Source mangaka: ${mangaka.name} (${args.qid}); Source series: #${series.id}\n` +
    YAML.stringify(result.data);

  if (args.dryRun) {
    console.log(`[dry-run] would write to ${outPath}:\n${yamlText}`);
  } else {
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    fs.writeFileSync(outPath, yamlText, "utf8");
    console.log(`[wrote] ${outPath}`);
  }

  console.log("\n=== summary ===");
  console.log(`  slug      : ${args.slug}`);
  console.log(`  title     : ${result.data.title}`);
  console.log(`  publisher : ${args.publisher}`);
  console.log(`  magazine  : ${args.magazine ?? "(none)"}`);
  console.log(`  demographic: ${args.demographic}`);
  console.log(`  genres    : ${args.genres.join(", ")}`);
  console.log(`  editions  : ${editions.length}`);
  for (const e of editions) {
    console.log(
      `    ${e.type.padEnd(12)} ${e.label.padEnd(16)} ${e.year_started ?? "?"}-${e.year_ended ?? "?"} vols=${e.volumes.length}`,
    );
  }

  db.close();
}

main();
