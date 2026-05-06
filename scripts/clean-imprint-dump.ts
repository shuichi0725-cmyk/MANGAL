/**
 * Tier 2 Phase 0: raw imprint dump (data/seeds/_raw-imprint-dump.txt) を解析して
 * data/seeds/adult-imprints.yml を生成する。
 *
 *   npm run seed:adult-imprints:clean
 *
 * 入力フォーマット:
 *   <imprint>(<count>)
 *   <空行>
 *   <publisher>
 *   <空行x1〜2>
 *   ...
 *
 * 出力フォーマット (data/seeds/adult-imprints.yml):
 *   schema_version: 1
 *   imprints:
 *     - imprint: <NFKC正規化済名>
 *       publisher: <NFKC正規化済名>
 *       count: <int>
 *   distribution_channels:
 *     - imprint: <NFKC正規化済名>
 *       notes: "<コメント>"
 *   ambiguous:
 *     - imprint: <NFKC正規化済名>
 *       publishers: [<list>]
 *       note: "<コメント>"
 *
 * クリーンアップ規則:
 *   1. NFKC 正規化 + 前後空白除去
 *   2. count 同一 imprint で複数行 → max(count) を採用、 ただし publisher が
 *      別の場合は ambiguous (= adult/mainstream collision の可能性) として隔離
 *   3. count < 5 のエントリは捨てる (偶発的タグ防止)、 ただし
 *      AMOUNT_EXEMPT_PUBLISHERS リストの publisher は count 1 でも採用
 *      (フランス書院・茜新社・ワニマガジン社 等の老舗 adult publisher の
 *      小規模 sub-imprint も拾うため)
 *   4. publisher が DISTRIBUTION_CHANNEL_PUBLISHERS にあるエントリは
 *      distribution_channels セクションに移し、 publisher は捨てる
 *      (DLwolf18 系: 1 つの imprint が複数配信プラットフォームで売られる pattern)
 */
import "./_env";
import fs from "node:fs";
import path from "node:path";

const RAW_PATH = path.join(process.cwd(), "data", "seeds", "_raw-imprint-dump.txt");
const OUT_PATH = path.join(process.cwd(), "data", "seeds", "adult-imprints.yml");

const COUNT_THRESHOLD = 5;

const AMOUNT_EXEMPT_PUBLISHERS = new Set(
  [
    "茜新社",
    "茜新社(電子)",
    "ワニマガジン社",
    "フランス書院",
    "ティーアイネット",
    "ヒット出版社",
    "コアマガジン",
    "ジーオーティー",
    "ジーウォーク",
    "オークス",
    "三和出版",
    "一水社",
    "クロエ出版",
    "DEEPER-ZERO",
    "FILL-IN",
    "Bevy",
    "セ・キララ文庫",
    "キルタイムコミュニケーション",
    "ぶんか社",
    "サン出版",
    "マガジン・マガジン",
    "コミックハウス",
    "若生出版",
    "久保書店",
  ].map(normalize),
);

const DISTRIBUTION_CHANNEL_PUBLISHERS = new Set(
  [
    "Webtoon Koi Contents",
    "Nuon",
    "FACON",
    "All Contents & VR",
    "StorySoop",
    "Mr.Blue",
    "Toons family",
    "NUWARU",
    "WEBTOON TV",
    "DLsite成年オリジナル",
    "TOPCO JAPAN",
    "Caleido",
    "comico",
    "TMEプラス",
    "TMEプラス/ウィルクリエイション",
    "デジタルコミック流通ネットワーク",
    "Mobile Media Research",
    "モバイルメディアリサーチ",
    "レジンコミックス",
    "レジンコミックス / Kidari Studio",
  ].map(normalize),
);

function normalize(s: string): string {
  return s.normalize("NFKC").trim();
}

type RawEntry = { imprint: string; publisher: string; count: number };

function parseRawDump(text: string): RawEntry[] {
  const lines = text.split(/\r?\n/);
  const entries: RawEntry[] = [];

  // 走査: コメント / 空行を跳ばしつつ、 「<imprint>(<count>)」 と <publisher>
  // のペアを 2 行単位で集める。 ペアは間に空行が 1 行以上挟まる。
  let i = 0;
  while (i < lines.length) {
    const line = lines[i].trim();
    if (!line || line.startsWith("#")) {
      i++;
      continue;
    }
    // 1 行目を imprint(count) として parse
    const m = line.match(/^(.*?)[(（](\d+)[)）]\s*$/);
    if (!m) {
      // 2 行目だけが先に流れることはないはず。 あれば skip。
      i++;
      continue;
    }
    const imprintRaw = m[1].trim();
    const count = Number(m[2]);
    if (!imprintRaw || !Number.isFinite(count)) {
      i++;
      continue;
    }
    // publisher 行を探す (次の non-empty / non-comment 行)
    let j = i + 1;
    while (j < lines.length) {
      const l2 = lines[j].trim();
      if (!l2 || l2.startsWith("#")) {
        j++;
        continue;
      }
      // 次が新しい imprint 行 (= 末尾に括弧+数字) なら publisher 不在 → skip
      if (/[(（]\d+[)）]\s*$/.test(l2)) break;
      entries.push({
        imprint: normalize(imprintRaw),
        publisher: normalize(l2),
        count,
      });
      j++;
      break;
    }
    i = j;
  }
  return entries;
}

type Imprint = { imprint: string; publisher: string; count: number };
type DistributionChannel = { imprint: string; notes: string };
type Ambiguous = {
  imprint: string;
  publishers: string[];
  note: string;
};

function classify(entries: RawEntry[]): {
  imprints: Imprint[];
  distribution_channels: DistributionChannel[];
  ambiguous: Ambiguous[];
} {
  // 1. distribution channel エントリは publisher 情報を捨てて imprint だけで集計
  const dcAgg = new Map<string, { count: number; publishers: Set<string> }>();
  const nonDc: RawEntry[] = [];
  for (const e of entries) {
    if (DISTRIBUTION_CHANNEL_PUBLISHERS.has(e.publisher)) {
      const cur = dcAgg.get(e.imprint) ?? {
        count: 0,
        publishers: new Set<string>(),
      };
      cur.count += e.count;
      cur.publishers.add(e.publisher);
      dcAgg.set(e.imprint, cur);
    } else {
      nonDc.push(e);
    }
  }

  // 2. imprint 単位で publisher 揺れを集計 (同名 imprint で異 publisher 多数 = ambiguous)
  const imprintGroups = new Map<string, RawEntry[]>();
  for (const e of nonDc) {
    const arr = imprintGroups.get(e.imprint) ?? [];
    arr.push(e);
    imprintGroups.set(e.imprint, arr);
  }

  const imprints: Imprint[] = [];
  const ambiguous: Ambiguous[] = [];
  for (const [imprint, group] of imprintGroups) {
    const publishers = new Set(group.map((g) => g.publisher));
    // 「双葉社」 と 「双葉社(アクションピザッツ)」 のような sub-imprint 注釈は
    // mainstream/adult collision の smoking gun。 ambiguous 扱い (seed に入れない)。
    if (hasSubImprintAnnotation(Array.from(publishers))) {
      ambiguous.push({
        imprint,
        publishers: Array.from(publishers).sort(),
        note: `sub-imprint 注釈あり (mainstream + adult の同名 imprint collision の可能性)、 seed には入れない`,
      });
      continue;
    }
    // 表記揺れ (NFKC や空白程度の差) を畳んだ後で複数残るなら ambiguous
    const distinct = collapseTrivialVariants(Array.from(publishers));
    if (distinct.length > 1) {
      ambiguous.push({
        imprint,
        publishers: Array.from(publishers).sort(),
        note: `同名 imprint × 複数 publisher (${distinct.length} groups) → adult/mainstream collision の可能性、 seed には入れない`,
      });
      continue;
    }
    // 単一 publisher → max count を採用
    const best = group.reduce((a, b) => (a.count >= b.count ? a : b));
    if (!shouldKeep(best)) continue;
    imprints.push(best);
  }

  // 3. distribution channel 出力
  const distribution_channels: DistributionChannel[] = [];
  for (const [imprint, agg] of dcAgg) {
    if (agg.count < COUNT_THRESHOLD) continue;
    const platforms = Array.from(agg.publishers).sort().join(" / ");
    distribution_channels.push({
      imprint,
      notes: `配信プラットフォーム: ${platforms} (合計 ${agg.count} 件)`,
    });
  }

  imprints.sort((a, b) => b.count - a.count);
  distribution_channels.sort((a, b) =>
    a.imprint.localeCompare(b.imprint, "ja"),
  );
  ambiguous.sort((a, b) => a.imprint.localeCompare(b.imprint, "ja"));

  return { imprints, distribution_channels, ambiguous };
}

function shouldKeep(e: RawEntry): boolean {
  if (e.count >= COUNT_THRESHOLD) return true;
  // count < 5 でも、 AMOUNT_EXEMPT_PUBLISHERS にある老舗 adult publisher は採用
  return AMOUNT_EXEMPT_PUBLISHERS.has(e.publisher);
}

function hasSubImprintAnnotation(publishers: string[]): boolean {
  // 「双葉社」 と 「双葉社(...)」 が同居 = sub-imprint 注釈による mainstream/adult
  // 区別。 これは collision 扱いするべき。
  const stripped = new Set<string>();
  let hasParen = false;
  for (const p of publishers) {
    const bare = p.replace(/[(（][^)）]*[)）]/g, "").trim();
    if (bare !== p) hasParen = true;
    stripped.add(bare);
  }
  return hasParen && stripped.size === 1 && publishers.length > 1;
}

function collapseTrivialVariants(publishers: string[]): string[] {
  // 表記揺れ (内部空白の異なるバリアント等) を 1 つに畳む。
  // 注: sub-imprint 注釈 (parenthetical) は collapse させない (= ambiguous 検出用)。
  const seen = new Set<string>();
  const out: string[] = [];
  for (const p of publishers) {
    const key = p.replace(/\s+/g, "");
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(p);
  }
  return out;
}

function emitYaml(out: {
  imprints: Imprint[];
  distribution_channels: DistributionChannel[];
  ambiguous: Ambiguous[];
}): string {
  const header =
    `# data/seeds/adult-imprints.yml\n` +
    `#\n` +
    `# 自動生成: scripts/clean-imprint-dump.ts (data/seeds/_raw-imprint-dump.txt より)。\n` +
    `# 編集する場合は raw dump を更新してから clean script を再実行する。\n` +
    `#\n` +
    `# 用途: scripts/seed-adult-imprints.ts が読み、 adult_imprints テーブルへ INSERT。\n` +
    `# computeAdultScore は editions.imprint がここに含まれる名前を substring 包含\n` +
    `# する場合 +3 シグナル (adult_imprint) を発火する (lib/adult-score.ts)。\n` +
    `#\n` +
    `# セクション:\n` +
    `#   imprints              : adult publisher が確定 (publisher も保持、 weight 用に count も)\n` +
    `#   distribution_channels : imprint は adult だが publisher 欄が配信プラットフォーム\n` +
    `#                           (DLwolf18 等)。 publisher は信頼できないので捨てる。\n` +
    `#   ambiguous             : 同名 imprint × 異 publisher の collision 注意エントリ。\n` +
    `#                           DB に投入しない (false-positive 防止)。\n` +
    `\n` +
    `schema_version: 1\n` +
    `\n`;

  let body = "imprints:\n";
  for (const i of out.imprints) {
    body += `  - imprint: ${yamlString(i.imprint)}\n`;
    body += `    publisher: ${yamlString(i.publisher)}\n`;
    body += `    count: ${i.count}\n`;
  }
  body += "\ndistribution_channels:\n";
  if (out.distribution_channels.length === 0) {
    body += "  []\n";
  } else {
    for (const d of out.distribution_channels) {
      body += `  - imprint: ${yamlString(d.imprint)}\n`;
      body += `    notes: ${yamlString(d.notes)}\n`;
    }
  }
  body += "\nambiguous:\n";
  if (out.ambiguous.length === 0) {
    body += "  []\n";
  } else {
    for (const a of out.ambiguous) {
      body += `  - imprint: ${yamlString(a.imprint)}\n`;
      body += `    publishers:\n`;
      for (const p of a.publishers) {
        body += `      - ${yamlString(p)}\n`;
      }
      body += `    note: ${yamlString(a.note)}\n`;
    }
  }
  return header + body;
}

function yamlString(s: string): string {
  // YAML scalar の安全な quoting。 シングルクオート内のシングルクオートは ''
  // にエスケープする。 制御文字は無いと仮定。
  return `'${s.replace(/'/g, "''")}'`;
}

function main(): void {
  if (!fs.existsSync(RAW_PATH)) {
    console.error(`raw dump not found: ${RAW_PATH}`);
    process.exit(1);
  }
  const raw = fs.readFileSync(RAW_PATH, "utf8");
  const entries = parseRawDump(raw);
  console.log(`[clean] parsed ${entries.length} raw entries`);

  const out = classify(entries);
  console.log(
    `[clean] imprints=${out.imprints.length}, distribution_channels=${out.distribution_channels.length}, ambiguous=${out.ambiguous.length}`,
  );

  const yaml = emitYaml(out);
  fs.writeFileSync(OUT_PATH, yaml, "utf8");
  console.log(`[clean] wrote ${OUT_PATH}`);
}

main();
