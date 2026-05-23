# CLAUDE.md

このファイルは Claude Code が毎セッション自動読み込みする protocol。
`/clear` / session 再起動 / 別 PC / 別日 でも保持される。

---

## 月次蒸留 protocol

ユーザが `月次蒸留して` (= トリガー語、 完全一致) と発話したら、 以下を厳密に実行する。

### 大原則 (= 絶対遵守)

- **種1 / 種2 / 種3 は壊さない**。 差分追加 = **純粋追加 only**、 既存への上書き / 削除 / 編集 は禁止。
- 上書き / 削除 / 既存破壊が一件でも検出された時点で **即 abort + ユーザ通知**。

### Phase 0: 前提確認 (= 1 つでも欠ければ即 abort + ユーザ通知、 実行に進まない)

以下のいずれかが存在しない場合、 「**対象 X が無いので蒸留できない**」 とユーザに報告して終了。 自動 fallback / 自動作成 はしない。

- `.cache/madb-last-release.txt` (= 前回取込 MADB release tag)
- `.cache/db.sqlite` (= 種2 = 派生 DB)
- `data/seeds/series-supplement.yml` (= 種3 = AI fill 蓄積)
- 種1 raw (= MADB release zip 由来の `cm101.csv` / `metadata101.json`、 `.cache/` 配下に unzip される想定)
- `data/seed/mangaka.csv` (= 漫画家マスター = 6,751 名、 種1 とは別 input)
- `scripts/_diff-madb.ts` (= 種1 差分抽出)
- `scripts/_diff-series.ts` (= 種2 差分抽出)
- `scripts/_select-supplement-diff.ts` (= 種3 fill 候補生成)
- `git status` clean (= dirty なら abort)

### Phase 1: 差分 report + Go サイン待ち

1. MADB latest release を GitHub API で取得 (= `MangaDataBaseLab/MADB-Lab-Bot-public` 等の確定 repo)
2. 前回取込 tag と比較し、 各層の差分件数を表示:
   - 種1: 新 ISBN N 件 / 新 mangaka 推定 件数
   - 種2: 新 series M 件 (= 4 層 adult filter 後)
   - 種3: 未 fill K 件 (= series-supplement.yml に未存在の key)
3. AI fill 予想 cost: K/100 batch、 J セッション分、 概算金額
4. 削除予測 = 0 件 を明示 (= 0 でなければ Phase 2 に進まず別途協議)
5. 「**進めて OK？**」 でユーザ確認、 Go サイン (= 「OK」 / 「進めて」 / 「ゴー」 等の明示的肯定) 受領まで Phase 2 に進まない。

### Phase 2: Go サイン後の実行

順序厳守:

1. **種1 取込** (= cm101.csv 取得 → 新 ISBN のみ追記、 既存行不変)
2. **種2 差分反映** (= fetch-madb incremental、 INSERT only、 削除禁止)
3. **種3 diff 元生成** (= select-supplement-diff で未 fill key list 出力)
4. **AI fill batch loop** = `MEMORY.md` 末尾 「種3 fill 作り方 (= 再利用 guide)」 セクションの protocol を厳密に踏襲 (= dict 形式 JSON、 100 entry/batch、 `_apply-fills.ts` 適用、 PUA 文字混入時は Python 経由で生キー書き出し、 JST 時刻付き block 単位報告、 commit + push)
5. **最終 summary** (= 全件数 + 削除 0 確認 + 次月予測)

### 保護策 (= 5 層)

1. 取込前 `.cache/db.sqlite` を `.cache/db.sqlite.bak-YYYYMMDD-HHMMSS` に backup
2. 種1 / 種2 / 種3 の各取込は **単独 commit で分離** (= 後 revert 可能)
3. 各 batch 後に `applied=N, missing=0, overwrites=0` を強制 log 出力
4. tsc / vitest が以前緑なのに赤転落で abort
5. 想定外 delete / overwrite 検出で abort

### Abort 条件 (= 検出したら即停止 + ユーザ通知)

- 種1 既存行が変更された (= MADB が過去 ISBN を訂正したケース)
- 種2 series 数が **減った** (= 削除発生、 異常)
- 種3 既存 key の content が変わった (= 上書き発生、 異常)
- typecheck / test の green → red 転落

### 報告形式

- 100 batch ごとに `🎉 Batch NNN/MMM 完了 (= X/Y = Z%) [JST YYYY-MM-DD HH:MM:SS]` 形式
- 完了時に累計件数 + 残件数 + 次月予測

---

## 一般 protocol

- branch は常に `claude/manga-database-affiliate-3x0ms` で作業
- commit 時 push までセット (= ユーザが artifact を即取得できるよう)
- 大規模変更 / 既存破壊リスクある操作は **必ず Go サイン** を待つ
- ユーザの `/clear` 後も protocol が機能するよう、 重要な約束はこの CLAUDE.md か MEMORY.md に永続化

---

## MANGAL データ形式 protocol (= 必須遵守)

### slug 命名規則

- ローマ字 (= 訓令式 or ヘボン式) で hyphen 区切り

#### 優先順 (= scripts/_extract-top-completed.py で 自動判定)

1. **種3 の slug field** (= 手動 override)
2. **DB の 英語名** (= alternative_titles.en / title_official_en) → 外来語 で slug 化
   - 例: ONE PIECE alt_en=`One Piece` → `one-piece` (○)
   - 例: ジョジョの奇妙な冒険 alt_en=`JoJo's Bizarre Adventure` → `jojos-bizarre-adventure` (○)
   - 例: 進撃の巨人 alt_en=`Attack on Titan` → `attack-on-titan` (○)
3. **title が 純 ASCII** (= 'W3', 'MAJOR', 'AMAKUSA 1637') → 直接 lowercase + 数字境界 split
   - 例: W3 → `w-3`、 H2 → `h-2`、 MAJOR → `major`
4. **数字 含む title で 普通読み** (= alignment 検証 通過) → 数字 keep
5. **kana → ローマ字** (= fallback)

#### アラビア数字 ルール (= 優先順 #4 適用時のみ)

**前提**: 優先順 #1-#3 (= 種3 slug field / alt_en / 純 ASCII title) が当たらず、 数字を含む title で **純和語 / 漢語 ベース** の場合に適用。 外来語 title (= 「アイシールド21」 「ペルソナ4」 「ワイルド7」 等) は #2 で先に当たる ため、 ここではなく `eyeshield-21` / `persona-4` / `wild-7` のような **英語 slug** になる。

- **ふりがな で 判断**:
  - **普通の 数字読み** (= 日本語 イチ/ニ/ジュウ/ニジュウイチ + 英語 ワン/ツー/スリー/フォー/セブン 等) なら **数字 keep**
    - 例: 15歳の地図 = `ジュウゴサイノチズ` → `15-sai-no-chizu`
    - 例: 連ちゃんパパ第1巻 → `renchan-papa-1` (= 巻数)
    - 例: 不滅のあなたへ第3部 → `fumetsu-no-anatae-3`
  - **特殊読み** (= 分数 / 当て字 / 略号) なら **ローマ字化** (= 数字 を kana に 戻して 表記)
    - 例: らんま1/2 = `ランマニブンノイチ` (= 分数読み) → `ranma-nibun-no-ichi`
    - 例: 3×3 EYES = `サザンアイズ` (= 当て字) → `sazan-aizu` (= ン+ア の境界を hyphen で明示)
    - 例: 7つの黄金郷 = `ナナツノエルドラド` (= 特殊読み) → `nanatsu-no-erudorado`
- **漢字数字** (= 七、 三、 etc.) は ふりがな の カナ表記を ローマ字化
  - 例: 七つの大罪 = `ナナツノタイザイ` → `nanatsu-no-taizai`

**注意**: 助詞 (= ノ / ヲ / ニ / ト 等) を含む title は hyphen で区切る (= `nanatsu-no-taizai`、 `ranma-nibun-no-ichi`)。 連結すると 「nanatsunotaizai」 のように読みづらく、 ン+母音 の境界も曖昧になる。

#### 種3 fill protocol (= AI fill)

- **外来語 (= 英語起源) title** は `alternative_titles.en` を **必ず fill する** (= 漏らすと slug が ローマ字読みで生成され、 後から rename 困難)
  - 例: 「ワンピース」 → en: 'One Piece' → slug: `one-piece`
  - 例: 「ドラゴンボール」 → en: 'Dragon Ball' → slug: `dragon-ball`
  - 例: 「ベルセルク」 → en: 'Berserk' → slug: `berserk`
  - 例: 「ブリーチ」 → en: 'Bleach' → slug: `bleach`
  - 例: 「アイシールド21」 → en: 'Eyeshield 21' → slug: `eyeshield-21`
  - 例: 「デスノート」 → en: 'Death Note' → slug: `death-note`
  - 例: 「ハンター×ハンター」 → en: 'Hunter x Hunter' → slug: `hunter-x-hunter`
- **判定基準**: title が カタカナ含む 外来語起源 (= 英語 / 独語 / 仏語 / 西語 など からの音写) なら en を必ず fill
  - 注意: 「ジョジョの奇妙な冒険」 のような 和語混在型も、 英語版が確立している作品は en を fill (= 'JoJo's Bizarre Adventure')
- これにより slug 生成 で 外来語 を 優先採用 (= ローマ字読み 'wanpiisu' でなく 'one-piece')

#### ⚠️ フォルダ名 (= slug) は後から rename が困難

- URL 互換性 / backup / 外部参照 に影響
- en fill 漏れで `wanpiisu.yml` のような slug が生成されると、 後の修正コストが高い
- **既存 entry の en fill 状況は定期チェックすべき**
- 確定済み slug の rename は必ず user 確認 + 旧 slug の alias / redirect mapping を残す

### title_kana / subtitle_kana

- **スペース は 入れない** (= 半角空白 / 全角空白 とも 全削除)
- 例: `ランマニブンノイチ` (○) / `ランマ ニブンノイチ` (×)
- `_promote-bulk-v2.py` で 出力時 自動 strip (= 防御策)

### title_romaji

- 全小文字 + space 区切り (= 例: `ranma 1 2`、 `shingeki no kyojin`)

### genres 規約

#### タグ運用ルール

- master keys は `data/genres.yml` で管理 (= 25 種類前後)
- 1 entry に 1-4 tag 付与
- 包括タグ + サブタグの **併用方式** (= 階層検索可能化)

#### スポーツ系の例外的サブタグ

- 包括タグ: `sports` (= スポーツ漫画 全般)
- **独立サブタグ**: `baseball` (= 野球漫画)、 `soccer` (= サッカー漫画)
  - **理由**: 件数が突出 (= 各 数百〜千タイトル)、 ジャンル境界が明確
  - **併用ルール**: 野球漫画 → `sports` + `baseball` の 2タグ付与 (= 階層検索のため sports は必ず併記)
- **マイナースポーツは独立化しない**: バスケ / ボクシング / テニス / 麻雀 / ゴルフ / 格闘技 / 自転車 / 水泳 等は `sports` のみ
  - 理由: ジャンル境界が曖昧 (= 「タッチ」 にボクシング描写、 「ドカベン」 に柔道編 等)、 線引き議論を避ける

#### サブタグ追加の判定軸

新規サブタグ独立化は 以下 3軸 **全て** を満たす場合のみ:

1. **件数が突出している** (= 数百以上)
2. **境界判定が容易** (= 「メジャー」 = baseball で迷わない、 等)
3. **検索ニーズが高い** (= 書店の特集コーナーで定番)

baseball / soccer が現状唯一の例外。 他ジャンル (= romance、 fantasy 等) も同原則で **サブ分類しない**。

---

## MANGAL 掲載対象 (= 漫画 only protocol)

MANGAL は **漫画作品** の database。 以下は **掲載対象外** (= 弾く):

### series-level (= scripts/_promote-bulk-v2.py の DROP_TITLE_PREFIX_PATTERNS)

- 「テレビアニメ版」「TVアニメ版」「アニメコミック」 = アニメコミカライズ
- 「劇場版」「映画」「OVA」 = 映像作品 + その コミカライズ
- 「ノベライズ」「ノベル」 = 小説版

### edition-level (= scripts/_promote-bulk-v2.py の KEEP_EDITION_TYPES)

keep: standard / bunkobon / wideban / kanzenban / shinsoban / aizoban
drop: anime / other / renewal

drop imprint patterns:
  - 'My first big' / 'コンビニ' / '増刊' / '同人' / 'ジャンプremix' / 'bilingual'

### 関連書 patterns (= scripts/_promote-bulk-v2.py の DROP_TITLE_CONTAINS_PATTERNS)

title 内 包含 で 弾く (= 漫画 ではない 副次出版物):

- ガイドブック / ファンブック / 設定資料集 / 公式図録 / 公式読本 / 公式ファン
- アンソロジー / 公式コミックガイド
- キャラクター名鑑 / 人物名鑑
- 心理分析 / 心理解析 / 完全解析 / 完全攻略 / 攻略本 / 解析書 / 解体新書
- 大研究 / 最終研究 / 超研究 / 大事典 / 大百科 / 大解剖
- パーフェクトガイド / 完全読本 / 完全ガイド / 必勝法
- 「○○の秘密」「○○の謎」 / コミック大全 / コミックスペシャル / ナビゲーション / 考察

注意: 「大全集」 (= 「水木しげる漫画大全集」 等) は **主作品 compilation** で 漫画扱い、 keep 対象。
