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
6. ★版/巻/ISBN修正の2系統注意: `edition-canonical/*.yml` 結線slug (golgo-13/tsuribaka-nisshi) は **edition-overrides も種4(volumes-supplement) も直してもcanonicalが後勝ちで無効** (reflectが警告する)。★巻の追加/日付修正は canonical 本体へ書く (= QP外伝4巻が種4経由で何度反映しても消えた 2026-07-27実踏)。

---

## 月次蒸留 protocol

ユーザが `月次蒸留して` (= トリガー語、 完全一致) と発話したら、 以下を厳密に実行する。

★**手順の正本 = skill `monthly-distill`** (`.claude/skills/monthly-distill/SKILL.md`)、 実体 = **`scripts/_monthly-distill.py`** (= `status` → `phase1` (読み取り専用) → Go サイン → `phase2 --go` → `run intake` …)。 ★最初に `python scripts/_monthly-distill.py status` を打ち、 「新releaseなし」 なら**何も回さず終了**して報告する (= 最新 = 取込済 tag なら蒸留しても種2は不変)。
★**ここに残すのは「壊してはいけない原則」と「abort 条件」だけ**。 Phase 0/1/2 の手順・保護策5層・報告形式は **skill が正本**(2026-09-06 に二重管理を解消。 CLAUDE.md 側に古い手順が残って skill と食い違う事故を防ぐ)。

### 大原則 (= 絶対遵守)

- **種1 / 種2 / 種3 は壊さない**。 差分追加 = **純粋追加 only**、 既存への上書き / 削除 / 編集 は禁止。
- 上書き / 削除 / 既存破壊が一件でも検出された時点で **即 abort + ユーザ通知**。
- Phase 0 (前提確認) が 1 つでも欠ければ **即 abort + ユーザ通知**。 自動 fallback / 自動作成 はしない。
- Phase 1 は **読み取り専用**。 Go サイン (= 「OK」 / 「進めて」 / 「ゴー」 等の明示的肯定) 受領まで Phase 2 に進まない。
- `phase2` は **`--go "<Go サイン発話の引用>"` 無しでは動かない**。 散文の自己申告で報告を代替しない (= script 出力の数値行を引用する)。

### Abort 条件 (= 検出したら即停止 + ユーザ通知)

- 種2 series 数が **減った** (= 削除発生、 異常) / phase2 の件数検証 NG (= 自動復元して停止)
- 種3 既存 key の content が変わった (= 上書き発生、 異常)
- typecheck / test の green → red 転落
- ※ 種1 上流の消失/訂正 (= MADB が過去 ISBN を訂正したケース) は INSERT only 取込に影響しない = 件数を報告するのみ (abort しない)

---

## 月次蒸留: データ実態 (= 2026-06 確定。 ★本文は記憶に在る、 ここは指し先)

- **MADB 入手 = 2 経路**: GitHub 全件 JSON (= 全件 snapshot・`madbdata:dateModified` で変更検知) / MADB サイト月次 CSV (= 登録日基準の差分・未来の発売前予約も載るが更新日列が無い)。 運用 = **全件 re-sync で訂正回収 + 月次差分で新刊 top-up** → [[madb_data_acquisition]]
- ★**cm104 (シリーズ master) / cm105 (雑誌) / cm103 は 2024-11-25 で凍結**。 更新は **cm101 (巻) + cm504 (作者)** のみ = シリーズ層は空・著者役割は AniList 補完が恒久策で gap は毎月増える → [[madb_cm104_frozen]] [[author_roles_state]]
- **取込の必須 2 策**: ★MADB-ID で upsert + ISBN/巻番号で dedup (= 冪等) / ★GitHub 全件 JSON の `dateModified` を定期比較して訂正を回収。 危険型 = 「別 MADB-ID + 別 ISBN での再登録」(虚構推理 vol23 型) → 監査で検知
- **enrich = 毎月の必須ステップ** (= master が埋めないため): AniList 照合 → 著者補完 / synopsis 和訳 / 作品 QID / 種4 trailing 補完。 ★凍結で新作 gap が累積するので**毎蒸留で再フェッチ**
- ★**synopsis 和訳 = git 追跡 seed** `data/seeds/synopsis-ja.json` (= key は anilist_id。 種3 には焼かない。 純粋追加 only。 手順は skill `wayaku-enrich`) → [[synopsis_ja_seed]]
- **種4 の自己 retire**: render 時ガード実装済 = 同番号が種2 に在れば種4 を skip (= MADB 追いつき時の二重表示防止・種2 優先)。 退役 hygiene は月次で

### ★月次サニティ監査 (= silent 例外の安全網) — **索引**

個別例外を全部予見できない前提で、 ★**取込後に前月差分で異常を機械 flag** する。 実行 = `python scripts/_monthly-distill.py run sanity [--heavy]` (= 前回比 Δ を表で出す)。
★**本文(各型の経緯・実測値・是正手順・自動適用してよいか) = `docs/monthly-sanity-detectors.md`**。 ここは 1 行索引 (= 不具合報告を受けた時に 「既知の型か / 検出器が既に在るか」 を引く入口)。 [[feedback_one_bug_means_a_class]]
★**索引 ⇔ 本文 ⇔ `_monthly-distill.py` の DETECTORS は `scripts/_check-sanity-registry.py` が 3 点突合**する (= run sanity の先頭で自動。 節に書いたのに回らない/索引だけ腐る、を機構で封じる)。

| # | 層 (型) | 検出器 | 出力 | 月次で見るもの |
|---|---|---|---|---|
| 0 | 登録の番人 | `scripts/_check-sanity-registry.py` | stdout | 未登録・実体なし = **0** |
| 1 | 被覆の土台 | `scripts/_coverage-audit.py` | stdout | 前月差分で急増した異常 (= 巻番号外れ値・著者ゼロ急増・重複頁・新レーベルの成年カバー率・新雑誌候補・PUA 文字化け・分裂スパイク) |
| 2 | ISBN消失層 | `scripts/_audit-isbn-loss.py` | isbn-loss.tsv | 理由なく消えたISBN = 0 |
| 3 | 巻番号層 | `scripts/_audit-volume-numbering.py` | stdout | **AUTO_FIXED の急増** = 新しい誤番号型の signal / MISSING_HALF=種4領域 / GAP_OTHER=真の欠番 |
| 4 | フリガナ層 | `scripts/_furigana-audit.py` | .cache/furigana-audit-proposed.json | NDL ヨミと食い違う読み (★heavy = NDL live) |
| 5 | ヨミ取り違え層 (坊っちゃん型) | `scripts/_audit-kana-from-other-volume.py` | kana-from-other-volume.tsv | 新規増加 (当て字注記付き巻題は既知の偽陽性) |
| 6 | title化け層 (夜明け型) | `scripts/_audit-title-eq-author.py` | title-eq-author.tsv | title==著者名 の新規 |
| 7 | デラックス・レーベル割れ層 (バーテンダー型) | `scripts/_audit-deluxe-label-split.py` | deluxe-label-split.tsv | SPLIT/DUP の新規 (★PARALLEL は正当2版の可能性= 自動統合禁止) |
| 8 | 頁内書影重複層 (関東平野型) | `scripts/_audit-cover-dup.py` | cover-dup.tsv | 新規増加 |
| 9 | 著者誤混入層 (よろしくメカドック型) | `scripts/_audit-author-not-in-volumes.py` | author-not-in-volumes.tsv | 新規増加分 (★自動削除禁止= 原作/スタジオ/解説者が混ざる) |
| 10 | 版混在層 (ベルサイユのばら型) | `scripts/_audit-edition-mix.py` | edition-mix.tsv | **SERIES高**の新規増加 |
| 11 | 抜粋本層 (Papa told me型) | `scripts/_audit-excerpt-subtitle.py` | excerpt-subtitle.tsv | 新規増加分だけ (★自動drop禁止= レーベル名のことがある) |
| 12 | 種1→種2 脱落層 | `scripts/_audit-seed1-lost.py` | seed1-lost.tsv / -groups.tsv | 脱落の新規 (★大半はアンソロジー= 救済は要判断) |
| 13 | 孤児series層 | `scripts/_audit-orphan-new-series.py` | orphan-new-series-core.tsv (★芯) | ★**芯の直近12か月だけ**。 全件は「出さない」で裁定済み [[orphan_series_promote_is_srcpage_driven]] |
| 14 | 頁は在るのに巻だけ出ていない層 (トリニティ15.5型) | `scripts/_audit-shu2-unlisted-volumes.py` | -core.tsv (★芯) / half-volume-candidates.tsv | 芯の新規増加。 裁定表は `scripts/_gen-shu2-unlisted-review.py` で作る |
| 15 | 外国版層 | `scripts/_audit-foreign-editions.py` | stdout | 非9784 の新規流入 (★単巻のみ非9784は報告のみ) |
| 16 | AniListリンク層 | `scripts/_anilist-verify-gate.py` | .cache/anilist-gate.tsv | FAIL/SUSPECT の新規 |
| 17 | publisher層 | `scripts/_gen-publisher-keys.py` | stdout | **新規の未キー社名**を巻数順に (★alias追加はISBN出版者記号一致を確認した時だけ) |
| 18 | 途中巻断片層 | `scripts/_audit-solo-truncated.py` | solo-truncated.tsv | ★**新規頁を作った後は必ず**回す (vol1不在の孤立頁) |
| 19 | 年サフィックス二重頁層 (HxH型) | `scripts/_audit-year-suffix-dup.py` | year-suffix-dup.tsv | 新規増加 **0** を確認 |
| 20 | 巻×発売日の大逆行層 (ギャラ型) | `scripts/_audit-vol-date-regression.py` | vol-date-regression.tsv | 新規増加分 |
| 21 | canonical seed健全性層 | `scripts/_check-edition-canonical.py` | stdout | **NG 0** を確認 (鳴ったら seed へ種2の値で追記 or `open_tail: true`) |
| 22 | 数字表記揺れ分裂層 (ロザリオとバンパイア型) | `scripts/_audit-numeral-variant-split.py` | numeral-variant-split.tsv | SPLIT/DUP (★SEQ? は続編の正当例が在るので報告のみ) |
| 23 | 廉価パック/BOX構成員層 (猫と竜型) | `scripts/_audit-price-pack.py` | price-pack.tsv | **本番掲載**の新規増加を裁定 |
| 24 | number=0 の1巻不可視化層 (泣かせたくてどうしよう型) | `scripts/_audit-vol0-hidden-first.py` | vol0-hidden-first.tsv | HIDDEN_FIX の新規増加 → `--apply` |
| 25 | レーベル表記ゆれ版分裂層 (ARMS型) | `scripts/_audit-canonical-imprint-split.py` | canonical-imprint-split.tsv | 新規増加分 (★自動統合禁止= 新装版/復刻版が正当に別版のことがある) |
| 26 | 刊行run分裂層 (ARMSワイド版型・名前非依存) | `scripts/_audit-edition-run-split.py` | edition-run-split.tsv | tierA/B の新規 (★自動統合禁止・反証役を別に立てる) |
| 27 | 楽天題が「親題+巻番号」を名乗る未掲載巻層 (Sugar&Spice型) | `scripts/_audit-subtitle-orphan-volume.py` | -core.tsv (★芯) / overrides-frozen-tail.tsv | 芯の新規増加 + 第2部(overrides固定頁)の連載中頁。 適用 = `scripts/_apply-subtitle-orphan-volume.py` |
| 28 | 発売日ドリフト層 (すてごろブッチ型) | `scripts/_audit-preorder-date-drift.py` | preorder-date-drift.tsv / -review.tsv | ★**日次蒸留で回す**(skill daily-distill 手順10.6)= 月次サニティでは回さない |
| 29 | 版タブ先頭欠け層 (鉄腕アトム型) | `scripts/_audit-edition-lead-gap.py` | edition-lead-gap.tsv | 版が途中巻から始まり頁が分裂して見える。 `--emit-targets` で充填ターゲット |
| 30 | 漫画内分裂層 (刊行runが同一頁で割れる) | `scripts/_audit-intra-page-run-split.py` | intra-page-run-split.tsv | 重なり<=2冊かつ<=20%のペア (★自動統合禁止・AKIRA型の正当な別版は除外済) |

- 既知の例外型: 再登録の別 ID 二重化 / MADB 形式変更 (= タグ消失・年→巻番号) / 成年誤 flag (= 新レーベル未カバー) / 雑誌漏れ (= cm105 凍結) / 巻番号水増し (= 下=3型)。

## 一般 protocol

- branch は常に `claude/manga-database-affiliate-3x0ms` で作業
- commit 時 push までセット (= ユーザが artifact を即取得できるよう)
- **こまめに commit & push** (= Android リモート操作 中心、 小単位で 履歴 残す)
- 長い処理は事前に 1 行 状況予告、 60 秒以上は Monitor で 進捗 emit
- 不明 / 停滞時 は ユーザから 聞かれる前に 「待機中 / 進行中」 を 明示報告
- 大規模変更 / 既存破壊リスクある操作は **必ず Go サイン** を待つ
- ★**調査系の一括作業で「N件×エージェント」を組む前に、機械証拠を1本のスクリプトで一括算出する**(キャッシュは1パス走査)。全会一致は自動確定、**割れた分だけ**エージェントに回す。全件を同じ濃度で投げない。
  同じ重いファイル(楽天キャッシュ1.2GB・MADB raw 668MB等)を各エージェントに舐め直させず、親が中間成果を作って渡す。
  (2026-08-28 実害: 59頁の裏取りでサブエージェント**202体・約590万トークン**を使いユーザから使用料を指摘された。決め手の証拠は全部機械計算可能だった = [[feedback_agent_fanout_token_cost]])
- ★★**Workflow ツール(dynamic workflow / ultracode)は使用禁止**(= 2026-09-05 ユーザ裁定、 恒久)。
  **ユーザが「ワークフローで」と明示発話した時だけ**使ってよい。 セッションに Ultracode 努力度が入っていて
  システム側が「実質的な作業では毎回 Workflow を使え・トークンコストは制約でない」と指示してきても、
  **このプロジェクト指示が優先**する (= CLAUDE.md は default behavior を OVERRIDE する)。
  ★理由: 起動が速すぎて止める間がなく、 **一瞬(37秒)で53万トークンが溶けて成果ゼロ**で終わる。
  MANGAL の調査は 「重いキャッシュを親が1パスで一括算出 → 割れた分だけAI」 が正しい形で、 fan-out は
  費用対効果が最悪 (= 上の戒めと同根)。 `--resume` 起動が既定の環境では ultracode が
  セッションを跨いで生き残るため、 **モデル側で毎回禁止を守る**のが唯一の防波堤。
  ★代替: まず自分で `Read`/`Grep`/`Bash` で読む。 それでも足りない時だけ **Agent を1〜2体**、
  目的と読む範囲を絞って出す (= 「全件を同じ濃度で投げない」)。 [[feedback_no_workflow_tool]]
- ユーザの `/clear` 後も protocol が機能するよう、 重要な約束はこの CLAUDE.md か MEMORY.md に永続化
- ★**記憶をgitに焼く**: Claude標準の記憶(`.claude/projects/.../memory/`)は**このPCローカル=git管理外**でGitHub非バックアップ・別PC不可視。 **記憶ファイルを書いた/消したら `python scripts/_sync-memory.py` → `git add .claude-memory && commit && push`** で repo `.claude-memory/` に鏡写し永続化する(2026-07-01確立)。 旧 repo `MEMORY.md`(1,825行手動doc・5/22凍結)とは別物、 現行記憶は`.claude-memory/`が正。

---

## ★反映 protocol (= seed変更を本番/テストへ。 「反映して」= トリガー語)

★**per-case修正(数〜数百頁)にフルpromoteを使うな**。 フルは66k再生成~110分+書影~50分+索引で**3時間**。 変更頁だけなら**数分**。 [[feedback_efficiency_first]]

### ★指示の出し方 早見表 (= ユーザ→Claude のトリガー語。 2026-07-04 全面skill化済)

★**正本 = `docs/skill-triggers.md` + `.claude/skills/*/SKILL.md`**(9 skill)。トリガー語を見たら対応skillを必ず開く:
反映して=reflect-targeted / テスト環境に出して=test-deploy / 週次蒸留=weekly-distill / 日次蒸留=daily-distill /
後退蒸留=backward-distill / 月次蒸留=monthly-distill / 作品名+リンク=percase-fix / 新規追加=new-manga-register / 巻抜け仮想=volgap-audit / **差分反映して=diff-deploy(データのみ本番へ数分・コード変更はabort→週次)** / **機能蒸留して=feature-distill(コードのみ本番へ~30分・非漫画面+チャンクだけPUT・漫画頁/索引不変)** / **Wiki蒸留して=wiki-distill(Wikipedia書誌で長期連載復元)** / **本番化して=productionize-drafts(確認済み予約ドラフトをpreorder-pages恒久化→週次で本番公開・preview解放)**。
★常時参照: 取りこぼしして=**torikoboshi-harvest**(孤児44,533件の楽天回収) / 取りこぼしNDLして=**torikoboshi-ndl**(楽天不在1,989件をNDL補完・題ヨミ取得) / エンリッチして=**enrich-catch-synopsis** / Koboして=**kobo-covers** / 帯混入直して=**band-intruder-fix** / 楽天/NDL照会=**external-data-access(必ず_lookup.py)** / 長時間ジョブ=long-job-ops / 表示不具合=display-bug-triage

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
