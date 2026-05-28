/**
 * AniList 由来 値 の 日本語 翻訳辞書 (= overlay 表示用)。
 *
 * - genres: 19 種類 全網羅
 * - categories: 25 種類 全網羅
 * - tagNames: 必要に応じて 追加 (= 未翻訳は 英語 fallback)
 */

export const anilistGenreJa: Record<string, string> = {
  Action: "アクション",
  Adventure: "冒険",
  Comedy: "コメディ",
  Drama: "ドラマ",
  Ecchi: "エッチ",
  Fantasy: "ファンタジー",
  Hentai: "18禁",
  Horror: "ホラー",
  "Mahou Shoujo": "魔法少女",
  Mecha: "メカ",
  Music: "音楽",
  Mystery: "ミステリー",
  Psychological: "心理",
  Romance: "恋愛",
  "Sci-Fi": "SF",
  "Slice of Life": "日常",
  Sports: "スポーツ",
  Supernatural: "超常",
  Thriller: "スリラー",
};

export const anilistCategoryJa: Record<string, string> = {
  Demographic: "読者層",
  "Cast-Main Cast": "キャラ：主役",
  "Cast-Traits": "キャラ：特性",
  "Theme-Romance": "テーマ：恋愛",
  "Theme-Action": "テーマ：アクション",
  "Theme-Arts": "テーマ：芸術",
  "Theme-Arts-Music": "テーマ：音楽",
  "Theme-Comedy": "テーマ：コメディ",
  "Theme-Drama": "テーマ：ドラマ",
  "Theme-Fantasy": "テーマ：ファンタジー",
  "Theme-Game": "テーマ：ゲーム",
  "Theme-Game-Card & Board Game": "テーマ：カード・ボードゲーム",
  "Theme-Game-Sport": "テーマ：スポーツ",
  "Theme-Other": "テーマ：その他",
  "Theme-Other-Organisations": "テーマ：組織",
  "Theme-Other-Vehicle": "テーマ：乗り物",
  "Theme-Sci-Fi": "テーマ：SF",
  "Theme-Sci-Fi-Mecha": "テーマ：メカ",
  "Theme-Slice of Life": "テーマ：日常",
  "Setting-Scene": "設定：場面",
  "Setting-Time": "設定：時代",
  "Setting-Universe": "設定：世界観",
  Setting: "設定",
  "Sexual Content": "性的描写",
  Technical: "技法",
};

/**
 * tag 名 の 日本語 訳 (= 追加分は 必要に応じて 拡充。
 * 未翻訳の tag は 英語 fallback)
 */
export const anilistTagJa: Record<string, string> = {
  // うる星やつら の 7 tags
  "Surreal Comedy": "シュールコメディ",
  Slapstick: "スラップスティック",
  Heterosexual: "異性愛",
  "Female Harem": "女子ハーレム",
  Youkai: "妖怪",
  Aliens: "宇宙人",
  Shounen: "少年",
  // ついでに よく出る tag を 数個 (= 後で 充実化)
  Shoujo: "少女",
  Seinen: "青年",
  Josei: "女性",
  Kodomo: "児童",
  School: "学園",
  "School Club": "学園クラブ",
  Magic: "魔法",
  Military: "軍事",
  Police: "警察",
  Yakuza: "ヤクザ",
  Tsundere: "ツンデレ",
  Yandere: "ヤンデレ",
  Kuudere: "クーデレ",
  Dandere: "ダンデレ",
  "Male Protagonist": "男性主人公",
  "Female Protagonist": "女性主人公",
  "Anti-Hero": "アンチヒーロー",
  "Love Triangle": "三角関係",
  Animals: "動物",
  Shapeshifting: "変身",
  Episodic: "エピソード形式",
  Nudity: "ヌード",
  Isekai: "異世界",
  Reincarnation: "転生",
  "Time Travel": "タイムトラベル",
  Vampire: "吸血鬼",
  Zombie: "ゾンビ",
  Ghost: "幽霊",
  Demon: "悪魔",
  Cyborg: "サイボーグ",
  Robot: "ロボット",
  Samurai: "侍",
  Ninja: "忍者",
};

export function jaGenre(g: string): string {
  return anilistGenreJa[g] ?? g;
}

export function jaCategory(c: string): string {
  return anilistCategoryJa[c] ?? c;
}

export function jaTag(t: string): string {
  return anilistTagJa[t] ?? t;
}
