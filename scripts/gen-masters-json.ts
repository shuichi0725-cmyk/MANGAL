/**
 * 左レール用マスタの静的JSON生成 = public/data/masters.json
 *
 * ★なぜ要るか (2026-09-09):
 *   `app/layout.tsx` が `loadMasters()` の結果を `<FilterRail masters={...}>` に props で渡していたため、
 *   **全ルートの RSC ペイロードに 56.6KB が直列化**されていた。Next は同じペイロードを
 *   HTML内インライン + `.txt`(RSC) の2箇所に書くので、1ルート113KB。
 *   実測 = 56.6KB x 2 x 約92,000ルート = **約9.9GB**(out/ 19.0GB の52%)。
 *   `/contact` は全体80.6KBのうち69.4KB(86%)が全出版社リスト、という状態だった。
 *
 * ★ここで出すのは重い2つ(publishers ~46KB / magazines ~8KB = 全体の95%)だけ。
 *   genres(1.3KB) と demographics(0.2KB) は**props のまま**にしてある =
 *   常時見えているチップ(ジャンル/読者層)はサーバ描画のまま即出る = 見た目は不変。
 *   出版社・連載誌の節は既定で畳まれており(`Section` は閉じている間 children を描画しない)、
 *   開くまでチップ自体が要らない = 遅延ロードで実害が出ない。
 *
 * ★ローダは本番と同一(`loadMasters`)を使う = zod検証込みで、スキーマのずれが構造的に起きない。
 *   (Python で YAML を読み直す実装にすると、schema 変更時に静かにずれる)
 */
import fs from "node:fs";
import path from "node:path";
import { loadMasters } from "../lib/loadData";

const OUT = path.join(process.cwd(), "public", "data", "masters.json");

function main() {
  const { publishers, magazines } = loadMasters();
  if (!publishers.length || !magazines.length) {
    throw new Error(`マスタが空: publishers=${publishers.length} magazines=${magazines.length}`);
  }
  const payload = { publishers, magazines };
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(payload), "utf8");
  const kb = fs.statSync(OUT).size / 1024;
  console.log(
    `masters.json: publishers ${publishers.length.toLocaleString()}社 / magazines ${magazines.length.toLocaleString()}誌 → ${OUT} (${kb.toFixed(1)}KB)`,
  );
}

main();
