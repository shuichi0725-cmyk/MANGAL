/**
 * 既存の data/manga/<slug>.yml に対し、ISBN リストから openBD で
 * 各巻の cover_url と release_date を一括取得して書き戻す。
 *
 * 使い方:
 *   npm run fetch:volumes -- --slug one-piece --isbns 9784088725093,9784088725161,...
 *
 *   --slug   対象作品の slug
 *   --isbns  カンマ区切りの ISBN13。並びがそのまま 第1巻 第2巻... に対応
 *   --start  既存の `volumes[]` を残しつつ第N巻から追加したい時の番号(任意)
 */
import fs from "node:fs";
import path from "node:path";
import YAML from "yaml";

type OpenBdItem = {
  summary?: {
    isbn?: string;
    title?: string;
    pubdate?: string;
    cover?: string;
  };
};

type ParsedArgs = {
  slug: string;
  isbns: string[];
  start: number;
};

function parseArgs(argv: string[]): ParsedArgs {
  const out: ParsedArgs = { slug: "", isbns: [], start: 1 };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = argv[i + 1];
    if (a === "--slug" && next) {
      out.slug = next;
      i++;
    } else if (a === "--isbns" && next) {
      out.isbns = next
        .split(",")
        .map((s) => s.trim())
        .filter((s) => /^\d{10,13}$/.test(s));
      i++;
    } else if (a === "--start" && next) {
      out.start = Number(next);
      i++;
    }
  }
  return out;
}

function normalizePubdate(raw?: string): string | null {
  if (!raw) return null;
  const digits = raw.replace(/[^0-9]/g, "");
  if (digits.length === 8) {
    return `${digits.slice(0, 4)}-${digits.slice(4, 6)}-${digits.slice(6, 8)}`;
  }
  if (digits.length === 6) {
    return `${digits.slice(0, 4)}-${digits.slice(4, 6)}`;
  }
  if (digits.length === 4) return digits;
  return null;
}

async function fetchOpenBd(isbns: string[]): Promise<(OpenBdItem | null)[]> {
  const results: (OpenBdItem | null)[] = [];
  // openBD は ?isbn=a,b,c の一括取得をサポート（最大 1000 件）
  const url = `https://api.openbd.jp/v1/get?isbn=${isbns.join(",")}&pretty`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`openBD fetch failed: ${res.status}`);
  const json = (await res.json()) as (OpenBdItem | null)[];
  results.push(...json);
  return results;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.slug || args.isbns.length === 0) {
    console.error(
      "Usage: npm run fetch:volumes -- --slug <slug> --isbns <isbn1,isbn2,...> [--start N]",
    );
    process.exit(1);
  }

  const filePath = path.join(process.cwd(), "data", "manga", `${args.slug}.yml`);
  if (!fs.existsSync(filePath)) {
    console.error(`Not found: ${filePath}`);
    process.exit(1);
  }

  const doc = YAML.parseDocument(fs.readFileSync(filePath, "utf8"));

  console.log(`[fetch] openBD ${args.isbns.length} ISBN(s)`);
  const items = await fetchOpenBd(args.isbns);

  type Vol = {
    number: number;
    asin: string | null;
    isbn13: string | number | null;
    cover_url: string | null;
    release_date: string | null;
  };

  const existing = ((doc.get("volumes") as YAML.YAMLSeq | undefined)?.toJSON() ??
    []) as Vol[];
  const byNumber = new Map<number, Vol>(existing.map((v) => [v.number, v]));

  for (let i = 0; i < args.isbns.length; i++) {
    const isbn = args.isbns[i];
    const num = args.start + i;
    const item = items[i];
    const cover = item?.summary?.cover?.trim() || null;
    const date = normalizePubdate(item?.summary?.pubdate);
    const prev = byNumber.get(num) ?? {
      number: num,
      asin: null,
      isbn13: null,
      cover_url: null,
      release_date: null,
    };
    byNumber.set(num, {
      number: num,
      asin: prev.asin,
      isbn13: isbn,
      cover_url: cover ?? prev.cover_url,
      release_date: date ?? prev.release_date,
    });
    console.log(
      `[vol ${String(num).padStart(3, " ")}] ${isbn}` +
        (cover ? " 表紙OK" : " 表紙無") +
        (date ? ` ${date}` : ""),
    );
  }

  const sorted = Array.from(byNumber.values()).sort((a, b) => a.number - b.number);
  doc.set("volumes", sorted);
  fs.writeFileSync(filePath, doc.toString({ lineWidth: 0 }), "utf8");
  console.log(`\n[wrote] ${filePath}  (${sorted.length} volumes)`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
