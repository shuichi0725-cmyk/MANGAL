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
- `data/seed/mangaka.csv` (= 種1 = mangaka master)
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

### 関連書 patterns (= 別途検討、 現状一部漏れ)

- ガイドブック / ファンブック / 設定資料集 / 公式図録 / アンソロジー
- キャラクター名鑑 / 心理分析書 / 攻略本

これらは MEMORY.md の 「path B' 未解決課題」 で 個別 fix 中。
