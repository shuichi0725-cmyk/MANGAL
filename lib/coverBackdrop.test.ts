import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

/**
 * 書影の白地バックドロップ番人 (= 2026-09-02 「めぞん一刻の書影が黒い斑点」から)
 *
 * 楽天の `.gif` 書影URLは、サムネイルサーバが **アルファ付き RGBA PNG** に変換して返す
 * (実測: 本番の .gif 書影 9,473件のうち 7.7% が透明ピクセル持ち)。
 * 楽天のページは白背景なので透けても白=正常に見えるが、MANGALはダーク背景なので
 * 透過部分から背景が透けて **黒い斑点** になる。
 *
 * 対策は描画側で「書影は必ず白地の上に置く」こと(= className に `bg-white`)。
 * これはURLの種類に依存しない恒久策なので、**今後どんな書影が増えても効く**。
 * 唯一の穴は「新しいコンポーネントで bg-white を書き忘れる」ことなので、
 * このテストが img/Image を全部数え上げて強制する。
 *
 * 書影でない画像(アバター等)は、タグ内か直前行に `not-a-cover` と書いて明示的に外す。
 * ★黙って外すな = 何が書影でないのかを人が読める形で残すためのマーカー。
 */

const ROOT = join(__dirname, "..");
const SCAN_DIRS = ["components", "app"];
const EXEMPT_MARKER = "not-a-cover";

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name === ".next" || name.startsWith(".")) continue;
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (name.endsWith(".tsx")) out.push(p);
  }
  return out;
}

type Tag = { file: string; line: number; text: string; prev: string };

/** `<img` / `<Image` の開始タグを、対応する `/>` か `>` まで拾う。 */
function findImageTags(src: string, file: string): Tag[] {
  const tags: Tag[] = [];
  const re = /<(img|Image)(?=[\s/>])/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(src)) !== null) {
    const start = m.index;
    let depth = 0;
    let end = start;
    for (let i = start; i < src.length; i++) {
      const c = src[i];
      if (c === "{") depth++;
      else if (c === "}") depth--;
      else if (c === ">" && depth === 0) {
        end = i + 1;
        break;
      }
    }
    const before = src.slice(0, start);
    const line = before.split("\n").length;
    const prevLine = before.split("\n").slice(-2, -1)[0] ?? "";
    tags.push({ file, line, text: src.slice(start, end), prev: prevLine });
  }
  return tags;
}

describe("書影は必ず白地の上に置く (透過PNG × ダーク背景の斑点を防ぐ)", () => {
  const files = SCAN_DIRS.flatMap((d) => walk(join(ROOT, d)));

  it("scan対象の tsx が見つかる", () => {
    expect(files.length).toBeGreaterThan(20);
  });

  it("すべての <img> / <Image> が bg-white を持つ (書影でないものは not-a-cover で明示除外)", () => {
    const offenders: string[] = [];
    let checked = 0;

    for (const f of files) {
      const src = readFileSync(f, "utf8");
      for (const tag of findImageTags(src, f)) {
        if (tag.text.includes(EXEMPT_MARKER) || tag.prev.includes(EXEMPT_MARKER)) continue;
        checked++;
        if (!/\bbg-white\b/.test(tag.text)) {
          offenders.push(`${relative(ROOT, f).replace(/\\/g, "/")}:${tag.line}`);
        }
      }
    }

    // 書影を描く箇所が消えていないことも同時に見る(検査が空振りしていないか)
    expect(checked).toBeGreaterThanOrEqual(9);
    expect(
      offenders,
      `書影の img に bg-white が無い。楽天の .gif 書影は透過付き RGBA PNG で返るため、` +
        `ダーク背景だと黒い斑点として透ける。className に bg-white を足すか、` +
        `書影でないなら タグ内/直前行に "${EXEMPT_MARKER}" と書いて除外理由を残すこと。\n` +
        offenders.join("\n"),
    ).toEqual([]);
  });
});
