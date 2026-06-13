/**
 * R2 ハッシュ差分アップロード(★ドラフト・未デプロイ)。 [[hosting_worker_r2_architecture]]
 *
 * out/(next export 出力)を R2 バケットへ。 ★変化したファイルだけ上げる(Class A書込を最小化)。
 *   - ローカル各ファイルの sha256 を計算 → 前回 manifest(.cache/r2-manifest.json)と比較
 *   - 新規/変更のみ `wrangler r2 object put` で上げる(蒸留差分=数百ファイル→無料枠余裕)
 *   - 削除されたキーは r2 object delete(任意・--prune)
 * ★初回フル(~14万)は per-file だと遅い → rclone(S3互換)推奨。 差分運用はこのscriptで十分。
 *
 * 使い方: node scripts/_r2-upload.mjs [--bucket mangal-site] [--prune] [--dry]
 * 前提: wrangler ログイン済み + R2バケット作成済み。
 */
import { createHash } from "node:crypto";
import { readFileSync, readdirSync, statSync, existsSync, writeFileSync, mkdirSync } from "node:fs";
import { join, relative, dirname } from "node:path";
import { execFileSync } from "node:child_process";

const ROOT = process.cwd();
const OUT = join(ROOT, "out");
const MANIFEST = join(ROOT, ".cache", "r2-manifest.json");
const args = process.argv.slice(2);
const BUCKET = (args[args.indexOf("--bucket") + 1] && args.includes("--bucket")) ? args[args.indexOf("--bucket") + 1] : "mangal-site";
const PRUNE = args.includes("--prune");
const DRY = args.includes("--dry");

function walk(dir, acc = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, acc);
    else acc.push(p);
  }
  return acc;
}
function sha(p) { return createHash("sha256").update(readFileSync(p)).digest("hex"); }

function main() {
  if (!existsSync(OUT)) { console.error("out/ が無い。 先に next build(static export)。"); process.exit(1); }
  const prev = existsSync(MANIFEST) ? JSON.parse(readFileSync(MANIFEST, "utf8")) : {};
  const next = {};
  const toPut = [];
  for (const p of walk(OUT)) {
    const key = relative(OUT, p).split("\\").join("/"); // R2キー(posix)
    const h = sha(p);
    next[key] = h;
    if (prev[key] !== h) toPut.push([key, p]);
  }
  const toDel = Object.keys(prev).filter((k) => !(k in next));

  console.log(`ローカル ${Object.keys(next).length} files / 変更 ${toPut.length} / 削除候補 ${toDel.length}`);
  if (DRY) { console.log("(--dry: アップロードせず終了)"); return; }

  let n = 0;
  for (const [key, p] of toPut) {
    execFileSync("wrangler", ["r2", "object", "put", `${BUCKET}/${key}`, "--file", p, "--remote"], { stdio: "ignore" });
    if (++n % 200 === 0) console.log(`  ...${n}/${toPut.length} put`);
  }
  if (PRUNE) {
    for (const key of toDel) {
      execFileSync("wrangler", ["r2", "object", "delete", `${BUCKET}/${key}`, "--remote"], { stdio: "ignore" });
    }
    console.log(`prune: ${toDel.length} 削除`);
  }
  mkdirSync(dirname(MANIFEST), { recursive: true });
  writeFileSync(MANIFEST, JSON.stringify(next));
  console.log(`完了: put ${toPut.length} / manifest更新 ${MANIFEST}`);
}
main();
