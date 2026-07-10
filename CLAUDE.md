# CLAUDE.md

このファイルは Claude Code が毎セッション自動読み込みする protocol。
`/clear` / session 再起動 / 別 PC / 別日 でも保持される。

---

## 統合台帳 (intake-manifest) = 全操作の記憶 (= 必ず使う、 忘れない)

場所 = **`data/seeds/intake-manifest/`** (= 設計 `docs/intake-manifest-gate-design.md` の Phase0 実体)。
散在していた18個の `*-changelog.jsonl` を1本に束ね、 全ページの「穴(holes)」を簿記する**単一の台帳**。
★過去、 簿記監査は走ったのに出力が `.cache`(gitignore)に落ちて消え「あるはずなのに無い」事故が起きた。
以後は**ここを一次ソースとして必ず使う**。

### 厳守ルール (= 2026-07-02 自動化で形骸化対策済)

1. **本番ページ (`data/manga.v2` / `.preview-data`) を触る cleanup/intake 操作は、 操作専用 `*-changelog.jsonl` に1行記録** (= 既存慣習。 slug / 操作 / before→after / at / 可逆backup 必須)。
2. `operations.jsonl` への集約は ★**`_reflect-targeted.py --push` が自動実行**(2026-07-02〜)。 反映フローに乗れば手動不要。 反映を通らない大作業だけ手動 `python scripts/_manifest-consolidate-ops.py`。 鮮度確認= `python scripts/_ledger.py --stale`。
3. **大きめ作業後 `python scripts/_intake-manifest-audit.py`** → holes 取り直し、 `holes-snapshot.jsonl.gz` + `holes-summary.json` を git に**永続化** (= .cache 置きっぱで消さない)。
4. **新しい cleanup を始める前に ★`python scripts/_ledger.py <slug>`** (= このslugの操作履歴[op_source別]+holes を一発表示。 9千行の目grepは形骸化するためツールで引く)。
4b. ★**本番存在チェックは `python scripts/_exists.py`** (--title/--slug=一覧索引で即答 / --isbn=ISBN索引.cache/isbn-page-index.json、大量照合前に--build)。 **生ファイル66k走査は禁止**(遅い・索引→台帳→ファイルの順)。
5. 全操作は**可逆** (= `.cache/*-bak-*` に before 退避) かつ **種2 sqlite 不変**。 人手可読サマリ (例 `docs/isbn-unmerge-ledger.md`) は台帳の**ビュー**、 一次ソースは台帳。
6. ★版/巻/ISBN修正の2系統注意: `edition-canonical/*.yml` 結線slug (golgo-13/tsuribaka-nisshi) は edition-overrides を直しても**canonicalが後勝ちで無効** (reflectが警告する)。

---

## 月次蒸留 protocol

ユーザが `月次蒸留して` (= トリガー語、 完全一致) と発話したら、 以下を厳密に実行する。

### 大原則 (= 絶対遵守)

- **種1 / 種2 / 種3 は壊さない**。 差分追加 = **純粋追加 only**、 既存への上書き / 削除 / 編集 は禁止。
- 上書き / 削除 / 既存破壊が一件でも検出された時点で **即 abort + ユーザ通知**。

### Phase 0: 前提確認 (= 1 つでも欠ければ即 abort + ユーザ通知、 実行に進まない)

以下のいずれかが存在しない場合、 「**対象 X が無いので蒸留できない**」 とユーザに報告して終了。 自動 fallback / 自動作成 はしない。

- `.cache/madb-last-release.txt` (= 前回取込 MADB release tag)
- `.cache/db-v2.sqlite` (= ★種2 現行 = 派生 DB。 旧 `db.sqlite` は前世代)
- `data/seeds/series-supplement-v2.yml` (= ★種3 現行 = AI fill 蓄積。 旧 `-v2`無しは前世代)
- 種1 raw (= MADB release zip 由来の `cm101.csv` / `metadata101.json`、 `.cache/` 配下に unzip される想定)
- `data/seed/mangaka.csv` (= 漫画家マスター = 6,751 名、 種1 とは別 input)
- `scripts/clean-madb-seed.ts` / `scripts/_build-series-v2.py` / `scripts/_populate-v2.py` / `scripts/_distill-incremental-merge.py` (= ★実パイプライン。 [[monthly_distill_real_pipeline]]。 旧 `_diff-madb.ts` 等の .ts 差分3種は**廃止済=存在しない**、 チェックするな)
- `scripts/intake.py` (= 派生層+matcher+promote の一括 runner)
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
3. **派生層 + matcher + 本番 再生成** = `python scripts/intake.py --run`
   (= roles→merge→seed4→detect → **matcher v9→v13→v14** → **adult_us map** →
    trailing → **foreigndrop(外国版自動drop)** → **promote(adult_us付与)**。 種2/種a 更新で全派生が古くならないよう一括再生成。
    ※matcher は ~20分。 終了後 git diff で本番yml確認 → commit/push)
4. **種a productionization の種3書込** (= deliberate、 match-v14 確定後):
   - **en-fill** = `_apply-en-fills-surgical.py`(S180×種3_en空 の AniList英題を `alternative_titles.en` に純粋追加。 `.new`検証→置換)
   - (将来) **anilist_id 結線** = 同手法で id/synonyms/genres_anilist を純粋追加
5. **種3 diff 元生成** (= select-supplement-diff で未 fill key list 出力)
6. **AI fill batch loop** = `MEMORY.md` 末尾 「種3 fill 作り方 (= 再利用 guide)」 セクションの protocol を厳密に踏襲 (= dict 形式 JSON、 100 entry/batch、 `_apply-fills.ts` 適用、 PUA 文字混入時は Python 経由で生キー書き出し、 JST 時刻付き block 単位報告、 commit + push)
7. **最終 summary** (= 全件数 + 削除 0 確認 + 次月予測)

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

## 月次蒸留: データ実態と運用補強 (= 2026-06 確定。 詳細は MEMORY.md 各項)

### MADB データ入手 = 2 経路

- **GitHub 全件 JSON** (`github.com/mediaarts-db/dataset`) = その日までの **全件 snapshot** (= baseline)。 重い・MADB 認知用。 ★`madbdata:dateModified` を持つので **変更検知に使える**。
- **MADB サイト** (`s-db.artmuseums.go.jp` 詳細検索) = **項目 (cm101/104 等) × 月単位** の CSV (= **登録日基準の差分**)。 軽い・新鮮・★**未来の発売前予約も載る** (= STEP4 末尾検出に直結)。 ただし ★**更新日列が無い** = 修正に気付けない。 列 52・複数著者は `＼＼` 区切り。
- ★運用: **GitHub 全件を定期 re-sync して訂正を回収 + 月次サイト差分で新刊 top-up**。

### master 凍結の実態 (= [[madb-cm104-frozen]])

- ★**cm104 (シリーズ master) / cm105 (雑誌) / cm103 は 2024-11-25 で凍結**。 最新リリースでも同じ = **再 DL 無駄**。 更新は **cm101 (巻) + cm504 (作者)** のみ。
- 帰結: 新刊は「マンガ単行本シリーズ」链 **0%** = シリーズ層は空。 ★著者役割 ([原作]/[漫画]) は cm104 にしか無く、 新作は AniList 補完が **恒久策**。 gap は毎月増える。

### 取込の必須 2 策

- ★**重複**: **MADB-ID で upsert** + **ISBN/巻番号で dedup** (= 冪等、 経路が重なっても安全)。 ★危険型 = 「別 MADB-ID + 別 ISBN での再登録」(= 虚構推理 vol23 型) → 別 cluster に落ちると二重ページ。 監査で検知。
- ★**変更検知**: 月次 CSV は更新日列が無く修正を見逃す → **GitHub 全件 JSON の `madbdata:dateModified` を定期比較**して訂正を回収。

### enrich = 毎月の必須ステップ (= master が埋めないため)

- AniList 照合 → ★**著者補完** (原作/作画分離。 [[author-roles-state]]) / synopsis 和訳 / 作品 QID / 種4 trailing 補完。
- ★凍結で新作 gap が累積 → **毎蒸留で再フェッチ** (= 一度きりでない)。

#### ★synopsis 和訳 = git 追跡 seed (= 2026-06-02 確定、 永続化の正規ルート)

- **何**: AniList の英語 description を **AI が 60-120字の日本語あらすじに要約**したもの (= 逐語訳でなく要約・言い換え。 著作権配慮)。 key = **anilist_id**(作品単位。 series_key でない)。
- **どこ**: ★**`data/seeds/synopsis-ja.json`** (= git追跡 seed、 {anilist_id(str): ja} の単純 map)。 旧 `.cache/synopsis-ja-map.json` から移行済 (= .cache は gitignore で消える)。 `_apply-synopsis.py`(純粋追加) と promote(L1280 付近で join) の両方がこの seed を読む。
- **なぜ seed 化**: ★**synopsis だけが「高価な AI 生成物」**なので種3と同格で git 永続化。 他の enrich (= synonyms/genres/tags/anilist_id/QID) は **dump + match から毎 promote タダで再 join** できるので **git に焼かない**(= 再生成可能なものは永続化しない原則)。 種3 本体には**焼き込まない**(key が series_key で match 変更時に別作品へ貼り付くため + 33MB 巨大編集の freeze 回避 + 種3不変原則)。
- **蒸留での扱い** (= 純粋追加 only):
  1. enrich (= match-v14) で新規 anilist_id が増える → `_build-anilist-enrich-map.py`
  2. ★未訳 delta 抽出: enrich の aid のうち synopsis-ja.json に**未存在 かつ AniList desc 有**を todo 化 (= `.cache/syn-batches/batch-NNN.json` に 100件/batch 分割)
  3. ★**分散 workflow** で各 batch を AI 要約 → `.cache/syn-out/batch-NNN.json` に書出 (= 中断耐性)
  4. 全 syn-out を merge → `_apply-synopsis.py` で `data/seeds/synopsis-ja.json` へ**純粋追加**(新規 N / 上書き 0 を確認)
  5. ★**commit + push**(= git 永続化。 これで別PC・モバイルでも消えない)
  6. 本番反映は **全DB promote 時**に manga.v2 へ焼かれて確定 (= seed commit だけでは本番に出ない)
- **成人 (isAdult)**: 露骨な性描写は要約に含めない/中立化。 成人作の synopsis も同じ seed に入れる (= 表示は adult_us/geo で出し分け)。 当初 deferred 分は別途追加。

### 種4 の自己 retire + 退役

- ★render 時ガード (実装済): 同番号が種2 に在れば種4 を skip = MADB 追いつき時の **二重表示防止**・種2 優先。
- 退役 hygiene: MADB が追いついた種4 entry を月次で除去 = lean 維持。

### ★月次サニティ監査 (= silent 例外の安全網)

個別例外を全部予見できない前提で、 ★**取込後に前月差分で異常を機械 flag** する:
- 巻番号の外れ値 (= 年誤 parse「2022巻」型) / 著者ゼロ急増 / 重複ページ / **新レーベルの成年カバー率** / 新雑誌候補 / 文字化け PUA / 分裂スパイク / **外国版流入 (= ISBN国コード非9784)**。
- 土台 = `scripts/_coverage-audit.py` (= 真の公開数・被覆・品質 flag)。 ★**前月との差分**で「今月だけ急増した異常」を浮かせる。
- ★巻番号層 = `scripts/_audit-volume-numbering.py` (= merge解決後 page×edition で巻番号異常を3分類): **AUTO_FIXED**(上下完全揃い+gap=下=3型水増し、 promoteの`_fix_complete_sequence_numbers`が自動是正済=件数監視。 ~1,677件) / **MISSING_HALF**(片側欠落=取りこぼし=種4領域) / **GAP_OTHER**(真の欠番・外れ値1000等)。 ★AUTO_FIXEDが急増したら新たな誤番号型のsignal。
- ★フリガナ層 = `scripts/_furigana-audit.py` (= NDL公式読みground-truthで誤フリガナ検出。 [[furigana-ndl-audit]])。
- ★ヨミ取り違え層 = `scripts/_audit-kana-from-other-volume.py` (= **坊っちゃん型**: 部題・テーマ題シリーズで頁ヨミが「自頁の別巻題の読み」に化ける[『坊っちゃん』の時代のヨミ=アキノマイヒメ=第2部題で発見 2026-07-10]。 ★当て字情報に非依存=比較を「自頁の巻真題集合の機械読み」に閉じ、頁題読みと犯人読みの類似度<0.5の別物のみflag。 出力=`docs/production-diagnostics/kana-from-other-volume.tsv`。 当て字読み注記付き巻題[T・Pぼん/EYES金銀妖瞳型]は既知の許容偽陽性)。
- ★title化け層 = `scripts/_audit-title-eq-author.py` (= **title==著者名** の壊れレコード検出。 MADBクラスタリングで実タイトル/副題が脱落し series.title が著者名に化けた「夜明け」型。 kana も著者読みになり誤る。 出力=`docs/production-diagnostics/title-eq-author.tsv`。 該当は NDL by-ISBN で実題確認 → title/kana是正 or 抜粋本drop)。
- ★外国版層 = `scripts/_audit-foreign-editions.py` (= ★**複数証拠**で scope外の外国語版を検出: ①latin題 ②シリーズ全ISBN非9784[978-4=日本] ③複数巻[typo説明不可]。 intakeの`foreigndrop`stageで`--apply`=純粋追加。 ★単巻のみ非9784はtypo懸念で報告のみ。 旧filterの穴=クリーンlatin題[Akira/Naruto外国版]がEMPTYslug/credit文字列依存をすり抜けていた、 を ISBN国コードで恒久封鎖)。
- ★publisher層 = 各版の出版社は **種2 ISBN→metadata101 schema:publisher** から promote が自動導出 (= edition.publisher=当時社名、 work.publishers[]=社キー集合。 [[publisher_model_edition_level]])。 ★月次=**新規の未キー社名**(norm未解決)を巻数順に flag → 主要なら `data/publishers.yml` にキー追加。 alias追加は **ISBN出版者記号(帯)一致で同一実体を確認した時のみ**(だろう運転禁止)。 families/企業グループ畳みは**不採用**(実体=ISBN帯=統廃合に不変)。 生成器 `scripts/_gen-publisher-keys.py`。 ★ISBN-10/13混在を `_to_isbn13` で正規化必須。
- 既知の例外型: 再登録の別 ID 二重化 / MADB 形式変更 (= タグ消失・年→巻番号) / 成年誤 flag (= 新レーベル未カバー) / 雑誌漏れ (= cm105 凍結) / 巻番号水増し (= 下=3型)。

---

## 一般 protocol

- branch は常に `claude/manga-database-affiliate-3x0ms` で作業
- commit 時 push までセット (= ユーザが artifact を即取得できるよう)
- **こまめに commit & push** (= Android リモート操作 中心、 小単位で 履歴 残す)
- 長い処理は事前に 1 行 状況予告、 60 秒以上は Monitor で 進捗 emit
- 不明 / 停滞時 は ユーザから 聞かれる前に 「待機中 / 進行中」 を 明示報告
- 大規模変更 / 既存破壊リスクある操作は **必ず Go サイン** を待つ
- ユーザの `/clear` 後も protocol が機能するよう、 重要な約束はこの CLAUDE.md か MEMORY.md に永続化
- ★**記憶をgitに焼く**: Claude標準の記憶(`.claude/projects/.../memory/`)は**このPCローカル=git管理外**でGitHub非バックアップ・別PC不可視。 **記憶ファイルを書いた/消したら `python scripts/_sync-memory.py` → `git add .claude-memory && commit && push`** で repo `.claude-memory/` に鏡写し永続化する(2026-07-01確立)。 旧 repo `MEMORY.md`(1,825行手動doc・5/22凍結)とは別物、 現行記憶は`.claude-memory/`が正。

---

## ★反映 protocol (= seed変更を本番/テストへ。 「反映して」= トリガー語)

★**per-case修正(数〜数百頁)にフルpromoteを使うな**。 フルは66k再生成~110分+書影~50分+索引で**3時間**。 変更頁だけなら**数分**。 [[feedback_efficiency_first]]

### ★指示の出し方 早見表 (= ユーザ→Claude のトリガー語。 2026-07-04 全面skill化済)

★**正本 = `docs/skill-triggers.md` + `.claude/skills/*/SKILL.md`**(9 skill)。トリガー語を見たら対応skillを必ず開く:
反映して=reflect-targeted / テスト環境に出して=test-deploy / 週次蒸留=weekly-distill / 日次蒸留=daily-distill /
後退蒸留=backward-distill / 月次蒸留=monthly-distill / 作品名+リンク=percase-fix / 新規追加=new-manga-register / 巻抜け仮想=volgap-audit / **差分反映して=diff-deploy(データのみ本番へ数分・コード変更はabort→週次)** / **Wiki蒸留して=wiki-distill(Wikipedia書誌で長期連載復元)** / **本番化して=productionize-drafts(確認済み予約ドラフトをpreorder-pages恒久化→週次で本番公開・preview解放)**。
★常時参照: エンリッチして=**enrich-catch-synopsis** / Koboして=**kobo-covers** / 帯混入直して=**band-intruder-fix** / 楽天/NDL照会=**external-data-access(必ず_lookup.py)** / 長時間ジョブ=long-job-ops / 表示不具合=display-bug-triage

| ユーザの言い方 | Claudeがやること | 所要 |
|---|---|---|
| **「反映して」** | targeted反映(`_reflect-targeted.py`)= 直した頁だけ 本番manga.v2+索引+テスト同期+push。**検証ゲート内蔵**(slug/kana/date/isbn不正はpush前に停止) | 数分 |
| **「巻抜け仮想」** | `_volgap-virtual.py --list` = 残巻抜けを算出(promote不要) | ~2分 |
| **「新規追加/新刊入れて」** | distillパイプライン(`_distill_preview`系)= **テスト先行**で新規頁生成→ユーザ確認→GOで本番化 | 件数次第 |
| **「月次蒸留して」** | フルパイプライン(Phase0→Go待ち→取込→フルpromote) | ~3時間+ |
| **「日次蒸留して」** | skill `daily-distill`= `_distill_daily.py --discover`(NDL当月live・429即中断)→`--plan`(差分レポート=新規掲載可/新規欠落・カーソル自動更新)→worksheet記入→`--emit`。カーソル=distill-cursor.json | 数分 |
| **「後退蒸留して <年>」** | `_distill_backward.py <年> --discover(NDL live)→--plan(仕分け/ゲート)→AI worksheet記入→--emit(preview生成)`。掲載ゲート=必須メタ完備+楽天書影v1。不足=欠落表。被覆台帳=distill-coverage.json | 年次第 |
| 作品名+リンク(Wiki/NDL) | per-case版再構築(イアラ式)→即「反映して」相当まで実施 | 1作数分 |

- ★流れは**一方向**: seed修正 → 本番manga.v2 → テスト(.preview-data=subset同期) → push → 確認。**例外=新規マンガだけテスト先行**(preview生成→確認→本番化)。双方向に流さない(ズレの元)。
- ★Claudeは反映時に**変更slugを自分で列挙**する(ユーザに聞かない)。preview反映はpush後15-20分・追いpush禁止([[preview_deploy_pitfalls]])。

### ★新規登録 protocol (= NDL過去発見型。 2026-07-02 ユーザ裁定 = 順番を固定)

★背景: 索引ガードが authors/genres/year/kana 非空を要求 → 「チェックを通すために適当に埋める」圧力が構造的に在る。
**答え = 埋めるな、順番を守れ。検証が先、登録が後。埋められない作品は登録保留リストへ**(空欄で載せる/捏造して載せる、の両方を禁止)。

1. **全巻回収が先** — 巻N を発見したら、title+creator で NDL 全巻 + 楽天全巻を回収 (1..N と続巻)。**単巻先行登録は禁止**(7巻だけ登録→後から1-6巻追加、は事故の元)。
2. **題の確定** — NDL題 × 楽天題を突合。一致=採用 / 不一致=調査(不明ならユーザ報告)。**勝手命名は絶対禁止**。slug はこの確定題+確定ヨミから**一度だけ**生成 (= フォルダ付け直しの根絶。 rename はURL/alias/索引に波及する高コスト作業)。
3. **ヨミの確定** — 題ヨミ = NDL タイトルヨミ (ground truth)。著者名+著者ヨミ = NDL典拠/楽天。**調べて不明ならユーザに報告**して待つ(適当に付けない)。役割(原作/作画)不明も同様=デフォルトで埋めない。
4. **一括登録** — 全巻+検証済み必須メタ(title/kana/romaji/authors/year/status/demographic/genre≥1)が揃ってから登録。
5. **enrich は登録後** — 楽天の各巻情報を読み、**1巻の内容を基点**にネタバレ無しのキャッチ/あらすじを生成。genre は closed vocabulary(trusted無ければ provisional マーク)。**最終巻・途中巻のあらすじ丸写しは禁止**(ネタバレ+低品質)。
6. **作れないものは作らない** — 情報不足の項目(catch/synopsis/要素等)は**空のまま**、欠落表にしてユーザ報告。必須項目(genre等)すら確定できない作品は**登録保留リスト**で報告(=載せない)。[[feedback_complete_data_before_ship]] [[feedback_accuracy_is_the_goal]]

### 既定 = targeted反映 (= `scripts/_reflect-targeted.py`)
ユーザが「**反映して**」と言ったら、 per-case変更は これを使う:
```
python scripts/_reflect-targeted.py --only <変更stem,...> [--drop <削除stem,...>] [--push -m "msg"]
```
- `--only` = 再生成する **manga.v2ファイル名(=SRC slug)**。 slug-override頁もSRC名(例 夜明け=`yoshida-akimi`, 内部slug=yoake-yoshida2012)。
- `--drop` = non-manga-drop等で消す頁のファイル名(manga.v2/preview から削除 + 索引remove)。
- 処理 = drop削除 → `promote --only` → 索引 `--update/--remove`(本番data+preview両方) → preview同期 → push。 **書影はpromoteに統合済**(下記)なので別工程不要。
- 変更したslugを忘れず列挙する(edition-overrides.json / seed の触ったkey → 対応slug)。

### ★書影は promote に統合済 (= 2026-07-01。 旧 `_apply-covers-stage.py` は不要)
- `_promote-bulk-v2.py` が **書込直前の最終passで `covers.jsonl.gz`(isbn13→url) から null cover を充填**(`_cover_for`)。 edition-canonical/override/exclude/version の**後**に走るので全経路をカバー。
- 帰結: promote単独で書影付き。 別cover stageの66k再走(~50分)を廃止。 covers seedの(再)生成が要る時だけ `_apply-covers-stage.py --build`。

### フルpromote = 月次蒸留の時だけ
- `python scripts/_promote-bulk-v2.py`(引数無=全66k)。 ~110分+索引フル。 dropを一括除外する時や広範変更時のみ。
- ★**Windows注意**: 完了後もプロセスが居座る(ハング)。 ログ最終「art-books (別ストリーム)」到達 or manga.v2ファイル数で完了判定し**kill**。 実行中は manga.v2 を覗かない(ロック競合)。 [[promote_hangs_on_exit_windows]]

### 本番R2配信 (= 重い別工程)
- 本番(mangal.shuichi0725.workers.dev)= `next export`→`out/`→`python scripts/_r2-sync.py --bucket mangal-site`(差分PUT、要R2認証env)。 Next buildが重い。 テスト(mangal-preview)は `.preview-data` push で自動デプロイ(preview反映は targeted反映が済ませる)。
- ★**public/ の索引は preview専用(1400件subset)** = next export が out/ に継承する構造欠陥があった。 `_r2-sync.py` が同期前に **data/ の本番索引(25MB)で自動上書き+5MB未満guard**(2026-07-02恒久修正)。 public/ 側を本番索引に差し替えるな(previewが66k化して壊れる)。
- ★**Defender除外=実施済(2026-07-04)**: リポジトリと D:\mangal-cache を除外済み(ユーザ実行、管理者PS)。全I/O短縮。戻す時は `Remove-MpPreference -ExclusionPath`。

---

## 種4 = MADB 取込もれ巻 補完 yml (= data/seeds/volumes-supplement.yml)

### 目的

MADB に **取込もれた巻** (= 公式販売されているが MADB record にない) を 別 source
(= Amazon / NDL Search / 出版社公式) で 確認後、 種4 yml に 登録 → audit + 本番 yml
生成時に **補完反映**。 種2 sqlite は不変。

例: シャングリラフロンティア 20 巻 = MADB 取込もれ、 公式発売中 (ISBN 9784065377437)。
ONE PIECE 110 巻 等 多数 同種ケース。

### 形式 (= 各 entry)

```yaml
volumes:
  - series_keys: list  ← 紐付ける series_key (= 表記揺れ / 別著者で 種2 内 複数 sid に
                         分散している場合 全部 列挙)
    qid: optional      ← Wikidata Q-id (= qid 紐付き 種2 sid を 一括 cover 用)
    number: int        ← 巻番号
    isbn13: string     ← 確定 ISBN
    release_date: string
    pages: int (optional)
    publisher: string
    edition_type: standard/bunkobon/wideban/...
    title_display: string
    source: amazon/ndl/publisher-official
    added_at: YYYY-MM-DD
    note: |
      補完根拠 / 確認内容
```

### 命名理由

- 種3 = `series-supplement` = **シリーズマスター** (= 作品単位 metadata 補完)
- 種4 = `volumes-supplement` = **巻単位 補完** (= MADB 取込もれ巻の 個別データ)
- 両者は独立、 種4 は 種3 entry に 紐付き

### 月次蒸留 protocol との関係

- 種4 は 月次蒸留 で 触らない (= 手動 add only)
- audit + 本番 yml 生成 時に load される
- 種2 sqlite は不変 = 保護策 layer 1 (= backup) と 同レベルの安全性

---

## MANGAL データ形式 protocol (= 必須遵守)

### slug 命名規則 (= 2026-05-29 全面改訂)

slug = ローマ字 hyphen 区切り。 **公式英題 (= Demon Slayer 等の 意訳英題) は slug に使わない**。
読み (= title_kana) と 元綴り を 基点に 機械生成する。 旧 「英語名優先」 ルールは 廃止。

#### 判定フロー (= build script、 上から順に適用)

1. **種3 の slug field** (= 手動 override) があれば それを使う
2. **漢字 / ひらがな主体 + 通常読み** → **ヘボン式** (= 読みをローマ字化)
   - 鬼滅の刃 → `kimetsu-no-yaiba` (= 公式英題 Demon Slayer は 使わない)
   - 進撃の巨人 → `shingeki-no-kyojin`
3. **数字を含む** → 読み (title_kana) で **4 分岐**:
   - 音読み数詞 (= イチ / ニ / ジュウゴ) → **算用数字 keep**: ×一→`batsu-1`, ×2→`kakeru-2`, 15歳の地図→`15-sai-no-chizu`
   - 訓読み助数詞 (= ナナ**ツ** / ミッ**ツ**) → **ヘボン式**: 七つの大罪→`nanatsu-no-taizai`
   - 特殊読み (= 分数 ニブンノイチ / 当て字) → **ヘボン式**: らんま1/2→`ranma-nibunnoichi`
   - 英語読み (= ナインティーン / ワン) → **英語**: 19(ナインティーン)→`nineteen`
4. **カタカナ主体 (= 外来語)** → 元の外国語綴り。 判定は **種a (AniList) english の 音写フィルタ**:
   - 種a english を カタカナに戻して 元タイトルと一致 (= 音写) → その綴りを採用: ベルセルク→`berserk`, ワンピース→`one-piece`
   - 種a english が 意訳 (= 音が合わない) → 採用せず ヘボン fallback (= 鬼滅は Demon Slayer が意訳なので 弾かれ #2 へ)
   - 英語以外 (= 独 / 西語) も 種a / Wikipedia の綴り採用 (= エルドラド→`el-dorado`)
   - 造語 / 人名 (= 元綴りなし) は ヘボン式 (= ナルト→`naruto`)
5. **字面に 外国語が併記** → その外国語を 英語化:
   - 東京喰種トーキョーグール → `tokyo-ghoul` (= カタカナ側採用)
   - 鋼の錬金術師 (= FULLMETAL は字面外) → `hagane-no-renkinjutsushi` (= 字面に英題ないので ヘボン)
6. **1 文字英字 / 記号** → 英語読みは英字のまま、 特殊読みは読みヘボン:
   - X (= エックス、 英語読み) → `x` / × (= ペケ、 特殊読み) → `peke`
7. **当て字 (= カタカナ特殊読み)** → 読みを基点に、 英語起源なら英語綴り:
   - ザ・超女 (= スーパーギャル) → `super-girl` / GS美神 (= ゴーストスイーパーミカミ) → `ghost-sweeper-mikami`

#### 当て字 / 特殊読みの判定 (= 3ソース突合)

漢字の素直な読みと違う「当て字」は機械では判別しにくい。 3ソースで裁定:
- **MADB ja-hrkt** = 複数読み (= 普通読み + 当て字) を持つ作品 (= 約 19,000) → 当て字候補の一次ソース
- **種a (AniList) english / romaji** = 公式読みの裏取り
- **Wikipedia 記事冒頭よみがな** = 最終裁定 (= 記事ある作品で 高精度)
- どちらが当て字かは順序不定 (= GS美神は後ろ、 妖精標本は前) なので 種a/Wiki で確定する

#### ★ローマ字化 4規則 (= 2026-06-10 ユーザ裁定、 生成器はこれに従う)

1. **長音 = 保持** (= おう→ou / うう→uu 逐字): 魔法科高校→`mahouka-koukou`。
   AniList/MAL 等 海外アニメ圏の慣行に合わせ 検索流入を取る + 可逆 + 同名衝突減。
   例外: 英語圏で定着した固有名詞 (= Tokyo 等) は 定着綴り。
2. **助詞「を」= o** (= ヘボン標準): 〜を持つ男→`o-motsu-otoko`。 wo は使わない。
3. **敬称 (さん/くん/ちゃん) = ハイフン分離**: 高木さん→`takagi-san` (= `takagisan` 不可)。
4. **カタカナ外来語 (種a 裏取り不可時) = 明白な辞書英単語のみ英語綴り採用**
   (= モンスター→`monster`)、 グレーは AI Web検証 (= method 実証済、 誤り8%是正)、
   創作語・不明はヘボンカナ転写 fallback。

#### 助詞は hyphen 区切り

ノ / ヲ / ニ / ト 等の助詞を含む title は hyphen で区切る (= `nanatsu-no-taizai`)。 連結すると読みづらく ン+母音の境界も曖昧。 ただし `ranma-nibunnoichi` の 「ニブンノイチ」 内の 「ノ」 は 分数読みの一部なので **分離しない** (= title-level 助詞「の」 とは区別)。

#### 同名 slug 衝突

同名異作品 (= 中華一番 真鍋版 / 小川版) で slug 衝突する場合:
- **主版 (= 巻数多い / 有名 / 古い) を 無印**、 従版に **`-姓+発売年`** suffix
  - 小川版 → `chuka-ichiban` / 真鍋版 → `chuka-ichiban-manabe1993`
- 作者姓ローマ字 = 種a staff.full (= 「名 姓」順、 姓は最後の語) → mangaka.qid (= 作者QID) を Wikidata で引く → ヘボン式 の順
- 姓+年 の 2 要素で 同年・同姓の 二重衝突も ほぼ回避

#### 検索性 (= 公式英題は slug でなく メタに持つ)

公式英題 (= Demon Slayer 等) は slug に使わないが、 `alternative_titles.en` として **保持**し、 **HP 表示・検索・リダイレクト** に使う (= 海外ユーザが demon-slayer で 辿り着けるように)。

#### ⚠️ フォルダ名 (= slug) は後から rename が困難

- URL 互換性 / backup / 外部参照 に影響
- 確定済み slug の rename は 必ず user 確認 + 旧 slug の alias / redirect mapping を残す

### title_kana / title_kana_segmented (= フリガナ 2 形式)

種3 は フリガナを **2 形式** 持つ (= 意図的並存):
- **title_kana** (= スペースなし 連結) = **HP 表示用** + 50音ソート / 検索キー。 半角 / 全角空白 とも 全削除 (= `ランマニブンノイチ` ○ / `ランマ ニブンノイチ` ×)。 `_promote-bulk-v2.py` 出力時に 自動 strip (= 防御策)。
- **title_kana_segmented** (= スペースあり 分かち書き) = **slug 生成用** (= 語境界・助詞を 半角スペースで区切り、 ローマ字化の手がかり)。 例: 「機動戦士Zガンダム」 → `キドウ センシ Z ガンダム`。 表示には使わない。

#### MADB が 複数 ja-hrkt を持つ場合 (= 普通読み + 当て字読み)

- **当て字読み を 優先採用** (= 作者意図 / 通称 / 公式呼称 を 尊重)。 HP 表示フリガナも slug 生成も この当て字読みを基点。
- 例: 「GS美神極楽大作戦!!」 → 普通読み `ジーエスビシン…` でなく 当て字 **`ゴーストスイーパーミカミ…`** ★ 採用 (= slug `ghost-sweeper-mikami`)
- 「ザ・超女」 → 当て字 **`スーパーギャル`** ★ 採用 (= slug `super-girl`)
- どちらが当て字かの確定は slug 規則の **3ソース突合** (= MADB / 種a / Wikipedia) を使う
- 注: MADB が 1 読みのみ の作品も多い、 その場合は そのまま採用

### title_romaji

- 全小文字 + space 区切り (= 例: `ranma 1 2`、 `shingeki no kyojin`)

### genres 規約

#### タグ運用ルール

- master keys は `data/genres.yml` で管理 (= 32 種類、 下の closed vocabulary を参照)
- 1 entry に 1-4 tag 付与
- 包括タグ + サブタグの **併用方式** (= 階層検索可能化)

#### ★AIジャンル付与の closed vocabulary (= 2026-06-13 ユーザ裁定、 厳守)

蒸留で **AI がジャンルを付与する時は、 下の master 32 キーの中から「文言を持ってくる」だけ**。
新語の創作・英語混入・表記揺れは禁止 (= 例「バトル」「日常系」等の独自語を作らない。
近いのは `action`/`slice-of-life`)。 該当が無ければ無理に付けず空でよい (= `other` 行きより未付与)。

- **低信頼マーク必須**: AI 由来ジャンルは `genres_provisional: true` を立て、 後から
  「これは AI 推定」と判別できるようにする (= trusted = AniList genres+themes ∪ Wikipedia ∪ 手動。
  trusted が空の時だけ AI fallback、 その時 provisional=true)。 [[genre_quality_improvement]]
- **backstop**: `lib/loadData.ts` が master 外 genre キーを reject (= 万一の混入は build で弾く)。

★master 32 キー (= `data/genres.yml` が正本。 変更時はこちらも更新):

| key | 表示名 | key | 表示名 | key | 表示名 | key | 表示名 |
|---|---|---|---|---|---|---|---|
| action | アクション | adventure | 冒険 | fantasy | ファンタジー | sci-fi | SF |
| mystery | ミステリー | horror | ホラー | gag | ギャグ | comedy | コメディ |
| romcom | ラブコメ | romance | 恋愛 | drama | ドラマ | slice-of-life | 日常 |
| school | 学園 | sports | スポーツ | baseball | 野球 | soccer | サッカー |
| historical | 歴史 | samurai | 時代劇 | mecha | メカ | yokai | 妖怪 |
| gourmet | グルメ | 4-koma | 4コマ漫画 | essay | エッセイ漫画 | isekai | 異世界 |
| bl | ボーイズラブ | suspense | サスペンス | music | 音楽 | supernatural | 超常 |
| ecchi | お色気 | mind-game | 頭脳戦 | mahou-shoujo | 魔法少女 | war | 戦争 |

- ★**スポーツは増やさない** (= 野球/サッカー以外の競技は `sports` のみ。 ユーザ方針)。
- ★**タクソノミー自体は増やさない** (= 新ジャンルキー追加はユーザ裁定マター。 AI は既存から選ぶだけ)。

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

### ★掲載「対象」の scope (= 2026-06-02 確定)

- ★**日本で出版された漫画** が対象 (= 日本原産に限らない)。 ★**韓国 manhwa / 中華 manhua の日本語版(正規出版)も掲載対象に含める** (= 例: 復讐の毒鼓[全6巻本編]+ 復讐の毒鼓REWIND[全8巻前日譚]、 KADOKAWA刊、 Meen X Baekdoo)。 manhwa を一律 drop しない。
- ★**除外するのは「外国語版の書誌が紛れ込んだ記録」** (= translator credit 行が title になった orphan、 例: スウェーデン語版 ONE PIECE / タンタン / 仏BD。 `data/seeds/non-manga-drop.yml`)。 = 「日本で売られている manhwa(日本語)」と「日本作品の外国語版(非日本語)」は別物。
- ★EMPTY slug は junk と即断しない: 真の作品でも title_kana 欠落(orphan101)で EMPTY になる (= 「上全」じょうぜん[黄助BL]/「Page 1」ぺーじわん[スタジオ・バトル] は実在)。 kana 補完で救済。

### series-level (= scripts/_promote-bulk-v2.py の DROP_TITLE_PREFIX_PATTERNS)

- 「テレビアニメ版」「TVアニメ版」「アニメコミック」 = アニメコミカライズ
- 「劇場版」「映画」「OVA」 = 映像作品 + その コミカライズ
- 「ノベライズ」「ノベル」 = 小説版
- 「英訳・」「英訳」 = 翻訳版 (= 元 ja 版 別 entry で keep される、 翻訳 別 product 扱い)

### edition-level (= scripts/_promote-bulk-v2.py の KEEP_EDITION_TYPES)

keep: standard / bunkobon / wideban / kanzenban / shinsoban / aizoban
drop: anime / other / renewal

drop imprint patterns:
  - 'My first big' / 'コンビニ' / '増刊' / '同人' / 'ジャンプremix' / 'bilingual'
  - 'novel' / 'novels' (= 「Shonen sunday novels」 等 = ライトノベルレーベル / 小説版)

### 関連書 patterns (= scripts/_promote-bulk-v2.py の DROP_TITLE_CONTAINS_PATTERNS)

### 表示 sort 仕様 (= 2026-05-26 確定)

全ページ共通 sort 軸 = 3 種:

1. **発売日 昇順** (= 古い順、 default 想定)
2. 発売日 降順 (= 新しい順)
3. 名前 昇順 (= フリガナ 50音順)

各 series の sort key = **`first_volume_date`** (= standard edition の number=1 最小
datePublished、 種2 から計算)。

### saga / シリーズ統括ページ = 不要 (= 2026-05-26 確定)

各漫画 = 個別ページ (= 別作品扱い)。 ジョジョ第1-9部 + スピンオフ 等 同シリーズ
でも 全部 別ページ、 1 巻発売日 sort で 結果的に シリーズ順に並ぶ。

- うる星やつら本編 = 通常版/ワイド/文庫 (= 既存 multi-edition 統合)
- うる星パーフェクト★カラーエディション = 別ページ (= merge_sids で上下統合)
- ジョジョ第1-5部 / 第6部 / 第7部 / 等 = 各別ページ
- 岸辺露伴 / クレイジー・D 等スピンオフ = 別ページ

これにより 「edition 親子関係」 schema 不要、 saga_id schema 不要 = 設計大幅
シンプル化。

### 階層的排除 (= 2026-05-26 追加)

派生本 vs 独立シリーズ vs 本編 の 自動区別 logic:

1. **階層 1 = 強 drop** = DROP_TITLE_CONTAINS_PATTERNS hit → 無条件 drop (= 抜粋本/関連書)
2. **階層 2 = 派生判定** = 同 qid 内 主軸 (= title prefix 親) の **1% 未満** 巻数 sid = 派生候補 drop
3. **階層 3 = keep override** = 派生候補のうち title + subtitle に下記 word 含む = keep 救済
   - カラー系: フルカラー / 総カラー / オールカラー / カラー版 / カラーエディション
   - 全集 / 復刻: 大全集 / 復刻版 / 復刊
4. **偽 keep > 偽 drop** 原則: 復活困難なので drop 側 保守的、 残った偽 keep は 種3 mark で 個別drop (= 将来)

---

title 内 包含 で 弾く (= 漫画 ではない 副次出版物 / 本編ではない 抜粋本):

- ガイドブック / ファンブック / 設定資料集 / 公式図録 / 公式読本 / 公式ファン
- アンソロジー / 公式コミックガイド
- キャラクター名鑑 / 人物名鑑 / キャラクターブック
- 心理分析 / 心理解析 / 完全解析 / 完全攻略 / 攻略本 / 解析書 / 解体新書
- 大研究 / 最終研究 / 超研究 / 大事典 / 大百科 / 大解剖
- パーフェクトガイド / 完全読本 / 完全ガイド / 必勝法
- 「○○の秘密」「○○の謎」 / コミック大全 / コミックスペシャル / ナビゲーション / 考察
- 抜粋本 / 編集本 (= 本編ではない、 既刊の再編。 2026-05-29 拡充):
  - 傑作選 / 傑作集 / ベストセレクション / 特集号 / 特別総集編 / 名作集 / 名作選 / 自選 / 総集編
  - 上記は title だけでなく subtitle にもあれば drop (= 「本編名|sub:○○傑作集」、 = DROP_SUBTITLE_PATTERNS)
  - ★ 「短編集 / 作品集 / 初期作品集」 は **描き下ろし漫画** が多く keep (= drop しない。
    既刊の寄せ集め= drop、 新作短編の本= keep の 線引き)
- 画集 / 関連書 (= 漫画コンテンツでない):
  - 原画集 / 画集 / ポケット画廊 / うちあけ話

注意: 「大全集」 (= 「水木しげる漫画大全集」 等) は **主作品 compilation** で 漫画扱い、 keep 対象。
