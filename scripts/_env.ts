/**
 * tsx で起動するスクリプト用の最小 dotenv ローダ。
 * `.env.local` → `.env` の順で読み、既存の process.env は上書きしない。
 * Next.js のサーバランタイムと違い、tsx 単体起動だと .env.local が
 * 読まれないので、各スクリプトの先頭で side-effect import する想定。
 *
 *   import "./_env";   // 一行入れるだけ
 */
import fs from "node:fs";
import path from "node:path";

function loadFile(filePath: string): void {
  if (!fs.existsSync(filePath)) return;
  const text = fs.readFileSync(filePath, "utf8");
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq < 0) continue;
    const key = line.slice(0, eq).trim();
    if (!/^[A-Z_][A-Z0-9_]*$/.test(key)) continue;
    if (process.env[key] !== undefined) continue;
    let value = line.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    process.env[key] = value;
  }
}

const cwd = process.cwd();
loadFile(path.join(cwd, ".env.local"));
loadFile(path.join(cwd, ".env"));
