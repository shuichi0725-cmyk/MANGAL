/**
 * 使い方:
 *   npm run fetch:openbd -- 9784088725093 9784091210562 ...
 *   または
 *   echo "9784088725093" | npm run fetch:openbd
 *
 * 取得した書誌から data/manga/<slug>.yml の雛形を生成する。
 * slug 衝突時はファイル末尾に -2 を付ける。手動調整を前提にした「下書き」用途。
 */
import fs from "node:fs";
import path from "node:path";
import readline from "node:readline";
import YAML from "yaml";

type OpenBdItem = {
  summary?: {
    isbn?: string;
    title?: string;
    volume?: string;
    publisher?: string;
    pubdate?: string;
    cover?: string;
    author?: string;
  };
};

async function fetchOpenBd(isbns: string[]): Promise<(OpenBdItem | null)[]> {
  const url = `https://api.openbd.jp/v1/get?isbn=${isbns.join(",")}&pretty`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`openBD fetch failed: ${res.status}`);
  return (await res.json()) as (OpenBdItem | null)[];
}

function slugify(input: string): string {
  return input
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-")
    .slice(0, 60);
}

function yearFromPubdate(pubdate?: string): number | null {
  if (!pubdate) return null;
  const m = pubdate.match(/(\d{4})/);
  return m ? Number(m[1]) : null;
}

async function readStdin(): Promise<string[]> {
  if (process.stdin.isTTY) return [];
  const rl = readline.createInterface({ input: process.stdin });
  const lines: string[] = [];
  for await (const line of rl) {
    const t = line.trim();
    if (t) lines.push(t);
  }
  return lines;
}

async function main() {
  const args = process.argv.slice(2).filter((a) => /^\d{10,13}$/.test(a));
  const stdin = await readStdin();
  const isbns = Array.from(new Set([...args, ...stdin])).filter((x) =>
    /^\d{10,13}$/.test(x),
  );

  if (isbns.length === 0) {
    console.error("ISBN を引数または標準入力で指定してください");
    process.exitCode = 1;
    return;
  }

  const results = await fetchOpenBd(isbns);
  const outDir = path.join(process.cwd(), "data", "manga");
  fs.mkdirSync(outDir, { recursive: true });

  for (let i = 0; i < isbns.length; i++) {
    const isbn = isbns[i];
    const item = results[i];
    if (!item?.summary) {
      console.warn(`[skip] ${isbn}: openBD にデータ無し`);
      continue;
    }
    const s = item.summary;
    const title = s.title?.trim() ?? `unknown-${isbn}`;
    const slug = slugify(title) || `manga-${isbn}`;
    const filePath = path.join(outDir, `${slug}.yml`);

    if (fs.existsSync(filePath)) {
      console.warn(`[skip] ${slug}.yml は既に存在`);
      continue;
    }

    const draft = {
      slug,
      title,
      title_kana: "TODO",
      title_romaji: "TODO",
      year_started: yearFromPubdate(s.pubdate) ?? 0,
      year_ended: null,
      status: "ongoing",
      authors: [{ name: s.author ?? "TODO", role: "writer_artist" }],
      original_authors: [],
      publisher: "TODO",
      magazine: null,
      demographic: "shounen",
      genres: ["TODO"],
      synopsis: "",
      volume_1: { asin: null, isbn13: isbn, cover_url: s.cover ?? null },
    };

    fs.writeFileSync(filePath, YAML.stringify(draft, { lineWidth: 0 }), "utf8");
    console.log(`[wrote] ${filePath}`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
