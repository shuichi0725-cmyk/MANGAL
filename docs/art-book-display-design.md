# 画集の掲載 設計（Phase 2-3）

作成 2026-06-04。 ★方針(確定): 漫画家の画集/原画集/イラスト集を**漫画とは別カテゴリ**で掲載。 ★**絶対に漫画の巻列に混ぜない**。 作画家(artist role)に紐付け、 **原作者には紐付けない**(ラノベ等)。 **アダルトは除外**。 網羅は目指さない。
データ基盤(Phase 1済): `data/seeds/art-books.yml`(203件) / `data/seeds/art-book-exclude-isbn.yml`(7件)。

---

## 0. 全体像

```
[種2] ──promote──┬─→ data/manga.v2/*.yml      (漫画。 画集seriesと画集ISBNを除外)
                 └─→ data/art-books.v2/*.yml   (画集。 ★別ストリーム=構造的に混ざらない)
                                                  ↓ build
                            DataBundle { manga[], artBooks[], ... }
                                                  ↓
       /manga/[slug]  …漫画ページ + 「この作家の画集」枠(Q2-1)
       /art-books     …画集カタログ(Q2-3、 独立カテゴリ)
```

★**漫画と画集を別ストリーム(別出力ディレクトリ・別型)に分ける**のが「絶対混ざらない」の構造保証。 同じ manga[] 配列に入れない。

---

## 1. Phase 2: promote 分離（"絶対混ぜない"の保証）

### 1-1. 画集seriesを漫画から除外し、画集として出力
- promote 主ループで `series_key ∈ art-books.yml` を判定:
  - 漫画(`data/manga/*.yml` ソース)からは **skip**(manga.v2 に出さない)
  - 代わりに **ArtBook entry** を build → `data/art-books.v2/<slug>.yml`
- ArtBook の slug = 画集専用 namespace(例 `art/<artist>-<title>` or 既存slugに `-gashu`)で**漫画slugと衝突させない**。

### 1-2. 漫画に混在した画集巻を除外
- `get_editions_with_volumes` で巻を組む時、 **`isbn13 ∈ art-book-exclude-isbn.yml` を skip**。
  - うる星やつら(165巻) → 画集1巻が抜けて漫画は正しい巻列に。
- ★抜いた巻は、 対応する ArtBook entry 側に拾う(画集として独立表示)。

### 1-3. ArtBook の中身(build_artbook)
```
ArtBook {
  slug, title, title_kana, title_romaji,
  artist: string,            # ★art-books.yml の artist(作画家)。 原作者は入れない
  adult: bool,               # true は表示除外(データは保持)
  linked_work_slugs: [],     # 紐付け漫画(下記 §3-2)
  publisher, year,
  volumes: [ {number, isbn13, release_date, cover_url, price, asin, label} ],
}
```
※ volumes は通常の Volume と同形(書影・アフィリンクが同じ仕組みで効く)。

---

## 2. Phase 3-a: データモデル（schema）

### 2-1. ArtBookSchema(新規・lib/schema.ts)
- Manga と別の軽量型。 `editions` は持たず `volumes` 直下(画集は版分岐が薄い)。
- `DataBundle` に **`artBooks: ArtBook[]`** を追加。 ★manga[] とは別配列(混在防止)。

### 2-2. adult の扱い
- `adult: true` の ArtBook は **build時に出力しない**(or 出力するが表示層で除外)。 → 既定は**build時に除外**(本番に成人画集を出さない=確実)。

---

## 3. Phase 3-b: 表示（catalog + 作品紐付け）

### 3-1. Q2-3 画集カタログ `/art-books`
- 非adultの全画集を一覧(独立カテゴリ。 漫画一覧とは別ページ)。
- 並び: 作画家50音 / 発売日 / 名前(漫画一覧と同sort軸を流用)。
- カード: 書影(なければプレースホルダ) + 画集名 + 作画家 + Amazonボタン。
- フィルタ: 作画家、 出版社(漫画一覧の FilterPanel を流用)。

### 3-2. Q2-1 作品ページの「この作家の画集」枠 `/manga/[slug]`
- 巻列(VolumeRow)とは**別セクション**で、 その作品の作画家の画集を表示。
- ★**紐付けロジック**(2段階):
  1. **作品名一致**(画集title が 作品名を含む) → その作品ページに優先表示(例「タッチ あだち充自選複製原画集」→ タッチ)
  2. **作画家一致**(作品名一致が無ければ) → 同一作画家の全作品ページに「この作家の画集」として表示(例 あだち充の画集 → H2 等にも)
- linked_work_slugs を build時に計算(作画家→その作画家の manga slug 群、 作品名一致は優先フラグ)。
- ★**原作者には出さない**: ラノベ原作者(鎌池和馬)の作品には画集を紐付けない(artist一致のみ)。

### 3-3. 「画集なのに小説/漫画が載っている」型
- 中身に小説/漫画が混じる画集(とあるVISUAL BOOK型/猫ファンブック型)も、 **主体が画集なら画集カテゴリ**で扱い、 **作画家に紐付け**(原作者を避ける)。 漫画の巻列には入れない。

---

## 4. adult 検出の強化（Phase 3前の必須）

現状の弱点: 艶夢(笠間しろう=成人劇画家)が未検出。 既存signal(adult_score≥2 / adult_imprints / has_adult_credit / title marker)では漏れる。

### 強化案(多層・確実側に倒す)
1. **作画家ベース拡張**: art-books.yml の 203作画家を、 ★**adult_mangaka_known + その作画家の他作品の adult_score 最大**で判定(成人作を1つでも描いてる作画家の画集は要警戒flag)。
2. **title marker拡張**: 艶/官能/エロ/成人/SM/緊縛/淫/熟女/痴漢/陵辱… (ただし誤爆注意=「艶」は一般題にもある→作画家signalと AND)。
3. **★手動確認(203件は少数)**: 自動flag + **人の最終確認**で確実に。 203件なら現実的。 adultリストを `art-books.yml` の `adult: true` に確定。
4. 既定 = **疑わしきは除外**(adult疑い→表示しない)。 ユーザの「アダルト不可」を厳守。

---

## 5. 実装順(Phase 2-3、 1つずつGo確認)

1. **schema**: ArtBookSchema + DataBundle.artBooks(型のみ・低risk)
2. **adult強化**: 作画家signal拡張 + 203件の自動flag → 人手確認 → art-books.yml 確定
3. **promote**: 画集除外+ArtBook出力+混在ISBN除外(core変更・要temp検証)
4. **build/loader**: art-books.v2 → DataBundle.artBooks
5. **frontend**: /art-books カタログ + /manga/[slug] の「この作家の画集」枠
6. **検証**: うる星に画集が出ない / タッチ画集がタッチに紐付く / 成人画集が出ない / 漫画一覧に画集が混じらない

★各stepで temp 出力を目視 → Go。 特に **step3(promote)後に「漫画一覧に画集が1件も無い」を機械検査**(混ざらない保証の最終確認)。

---

## 6. 未決(設計で詰める点)

- 画集slugの命名規則(漫画slugと衝突回避。 `art/` prefix? `-gashu` suffix?)
- カタログの入口(ヘッダにタブ「漫画 / 画集」? それとも作品ページからのみ?)
- 作画家ページ(画集+漫画をまとめた作家ページ)を作るか(将来)
- multi_artist画集(トリビュート10件)の紐付け(代表1人? 全員?)
