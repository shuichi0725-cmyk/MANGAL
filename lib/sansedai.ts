/** 「三世代、今日の一冊」の純粋層(server/client 両方から呼べる)。
 *
 *  ★2026-09-18 切り出しの理由: これらは `components/SansedaiDaily.tsx` に在ったが、
 *  あのファイルは先頭が `"use client"` なので **server component から関数として呼べない**
 *  (import しても client 参照になる)。/sansedai-archive をサーバー描画に変えるために、
 *  日付計算・抽選式・表示名だけをここへ移した。
 *  同じ作法の先例 = `lib/shinkanDates.ts`(shinkanData から分離)/ `lib/related.ts`。
 *  ★抽選式(picksForDay)は「ホーム」「過去ログ」「凍結ログ生成器」で一致していなければならない。
 *    ここが単一ソース。SansedaiDaily は再エクスポートするだけにしてある。
 */
export type SansedaiEntry = {
  persona: string;
  gen: number;
  slug: string;
  title: string;
  comment: string;
  cover?: string | null;
};

export function jstDayIndex(offset = 0): number {
  return Math.floor((Date.now() + 9 * 3600 * 1000) / 86400000) - offset;
}

export function jstDateStr(offset = 0): string {
  const d = new Date(Date.now() + 9 * 3600 * 1000 - offset * 86400000);
  return d.toISOString().slice(0, 10);
}

export function picksForDay(entries: SansedaiEntry[], dayIndex: number): SansedaiEntry[] {
  return [0, 1, 2]
    .map((g) => {
      const pool = entries.filter((e) => Number(e.gen) === g); // ★JSONのgenは文字列のことがある(2026-07-06型バグ修正)
      if (pool.length === 0) return null;
      return pool[((dayIndex % pool.length) + pool.length) % pool.length];
    })
    .filter(Boolean) as SansedaiEntry[];
}

/** 表示用ペルソナ名 = 括弧の属性表記を落とす(2026-07-06 ユーザ要望「(10-20代)はいらない」) */
export function personaName(p: string): string {
  return p.replace(/[（(].*$/, "");
}

/** 案内人プロフィール(過去ログ冒頭用)。 stockのpersona表記のヒントから起こした短文 */
export const PERSONA_BIOS: Record<string, string> = {
  "ミナト": "話題作から掘り出しまで、テンポ重視でどんどん読む。",
  "リコ": "美大生。絵と空気感で一冊を選ぶ。",
  "サオリ": "仕事の合間が読書時間。恋愛と人間ドラマに強い。",
  "タケル": "元書店員。棚づくりの目線でおすすめを組む。",
  "圭三": "古書店主。古典と劇画の生き字引。",
  "静江": "喫茶店のママ。カウンター越しに一冊すすめてくる。",
};
