/**
 * draft → 本番昇格スクリプト (Option 1, 2026-05-06).
 *
 * `data/manga/_drafts/<slug>.yml` のうち placeholder (TODO_kana / TODO_genre /
 * TODO_publisher / magazine: null / synopsis: "") を 1 つも持たない 「production-
 * ready」 な draft を、 `data/manga/<slug>.yml` に移動 (= 本番投入) する。
 *
 *   npm run promote:drafts                # production-ready のみ promote
 *   npm run promote:drafts -- --dry-run   # 書かずにサマリだけ
 *   npm run promote:drafts -- --force     # 既存 data/manga/<slug>.yml を上書き
 *   npm run promote:drafts -- --filter X  # ファイル名 substring filter
 *
 * 処理:
 *   1. _drafts/*.yml を全部読む
 *   2. placeholder pattern check (前段の Drafts quality stats と同じルール)
 *   3. 0 placeholder のものだけ:
 *      a. 先頭の review コメントブロックを除去
 *      b. YAML パース → Zod MangaSchema 検証
 *      c. data/manga/<slug>.yml が無いか、 --force あれば書き出し
 *   4. 末尾で loadAllManga() を呼んで全体整合性を確認 (= masters の publisher/
 *      magazine/genre key 全部解決するか)
 */
import "./_env";
import fs from "node:fs";
import path from "node:path";
import YAML from "yaml";
import { MangaSchema } from "../lib/schema";
import { loadAllManga } from "../lib/loadData";

const DRAFTS_DIR = path.join(process.cwd(), "data", "manga", "_drafts");
const PROD_DIR = path.join(process.cwd(), "data", "manga");

type Args = {
  dryRun: boolean;
  force: boolean;
  filter: string | null;
};

function parseArgs(argv: string[]): Args {
  const out: Args = { dryRun: false, force: false, filter: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--dry-run") out.dryRun = true;
    else if (a === "--force") out.force = true;
    else if (a === "--filter" && argv[i + 1]) out.filter = argv[++i];
  }
  return out;
}

/**
 * placeholder 検出。 Drafts quality stats step (workflow) と同じルールで
 * 走る。 5 種いずれかが残っていたら production-ready ではない。
 */
function findPlaceholders(yamlText: string): string[] {
  const found: string[] = [];
  if (/^title_kana: TODO_kana$/m.test(yamlText)) found.push("title_kana");
  if (/^magazine: null$/m.test(yamlText)) found.push("magazine");
  if (/^ {2}- TODO_genre$/m.test(yamlText)) found.push("genres");
  if (/^publisher: TODO_publisher$/m.test(yamlText)) found.push("publisher");
  if (/^synopsis: ""$/m.test(yamlText)) found.push("synopsis");
  return found;
}

/**
 * draft 先頭の `# ...` 連続コメント行を除去。 1 行目の本文 (= `slug:` 等) まで。
 * 既存 data/manga/ の本番ファイルはコメント無しが慣例。
 */
function stripDraftHeader(yamlText: string): string {
  const lines = yamlText.split("\n");
  let i = 0;
  while (
    i < lines.length &&
    (lines[i].startsWith("#") || lines[i].trim() === "")
  ) {
    i++;
  }
  return lines.slice(i).join("\n");
}

function main(): void {
  const args = parseArgs(process.argv.slice(2));

  if (!fs.existsSync(DRAFTS_DIR)) {
    console.error(`[error] drafts dir not found: ${DRAFTS_DIR}`);
    console.error(`Run "npm run promote:bulk" first.`);
    process.exit(1);
  }

  const draftFiles = fs
    .readdirSync(DRAFTS_DIR)
    .filter((f) => f.endsWith(".yml"))
    .filter((f) => !args.filter || f.includes(args.filter));

  console.log(
    `[promote-drafts] scanning ${draftFiles.length} drafts in ${DRAFTS_DIR}` +
      (args.dryRun ? " (dry-run)" : ""),
  );

  const stats = {
    total: draftFiles.length,
    ready: 0,
    promoted: 0,
    skippedExisting: 0,
    skippedPlaceholder: 0,
    skippedInvalid: 0,
  };

  for (const file of draftFiles) {
    const draftPath = path.join(DRAFTS_DIR, file);
    const yamlText = fs.readFileSync(draftPath, "utf8");
    const placeholders = findPlaceholders(yamlText);

    if (placeholders.length > 0) {
      stats.skippedPlaceholder++;
      continue;
    }
    stats.ready++;

    const prodPath = path.join(PROD_DIR, file);
    if (fs.existsSync(prodPath) && !args.force) {
      stats.skippedExisting++;
      console.log(`  [skip-existing] ${file}`);
      continue;
    }

    const cleaned = stripDraftHeader(yamlText);

    // Zod 検証 (master キー解決は loadAllManga で別途やる)
    try {
      const obj = YAML.parse(cleaned);
      MangaSchema.parse(obj);
    } catch (err) {
      // Zod error は JSON で structured。 path + message のサマリにする。
      let msg: string;
      if (err && typeof err === "object" && "issues" in err) {
        const issues = (err as { issues: Array<{ path: (string | number)[]; message: string }> }).issues;
        msg = issues
          .slice(0, 3)
          .map((i) => `${i.path.join(".") || "(root)"}: ${i.message}`)
          .join("; ");
      } else {
        msg = err instanceof Error ? err.message.slice(0, 200) : String(err);
      }
      console.warn(`  [invalid] ${file}: ${msg}`);
      stats.skippedInvalid++;
      continue;
    }

    if (args.dryRun) {
      console.log(`  [would-promote] ${file}`);
    } else {
      fs.writeFileSync(prodPath, cleaned, "utf8");
      console.log(`  [promoted] ${file}`);
    }
    stats.promoted++;
  }

  // 全体整合性チェック (実書込みした後のみ意味あり)
  if (!args.dryRun && stats.promoted > 0) {
    try {
      const data = loadAllManga();
      console.log(
        `\n[final] data/manga/ has ${data.manga.length} manga loaded by loadAllManga (validation passed)`,
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(`\n[ERROR] loadAllManga validation failed: ${msg.slice(0, 200)}`);
      process.exit(1);
    }
  }

  console.log(`\n=== promote-drafts summary ===`);
  console.log(`  total drafts scanned : ${stats.total}`);
  console.log(`  production-ready     : ${stats.ready}`);
  console.log(`  promoted             : ${stats.promoted}`);
  console.log(`  skipped (existing)   : ${stats.skippedExisting}`);
  console.log(`  skipped (placeholder): ${stats.skippedPlaceholder}`);
  console.log(`  skipped (invalid)    : ${stats.skippedInvalid}`);
}

main();
