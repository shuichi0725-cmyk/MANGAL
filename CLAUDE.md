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

### 大原則 (= 絶対遵守)

- **種1 / 種2 / 種3 は壊さない**。 差分追加 = **純粋追加 only**、 既存への上書き / 削除 / 編集 は禁止。
- 上書き / 削除 / 既存破壊が一件でも検出された時点で **即 abort + ユーザ通知**。

★**手順の正本 = skill `monthly-distill`** (`.claude/skills/monthly-distill/SKILL.md`)、 実体 = **`scripts/_monthly-distill.py`** (= 2026-09-02 一括化: `status` → `phase1` (読み取り専用) → Go サイン → `phase2 --go` → `run intake` …)。 ここは原則と abort 条件。 ★最初に `python scripts/_monthly-distill.py status` を打ち、 「新releaseなし」 なら**何も回さず終了**して報告する (= 最新 = 取込済 tag なら蒸留しても種2は不変)。

### Phase 0: 前提確認 (= 1 つでも欠ければ即 abort + ユーザ通知、 実行に進まない)

★実体 = `python scripts/_monthly-phase0.py` (= 2026-07-10 script化。 目視チェックリストで代替しない、 phase1 が先頭で自動実行)。 exit 1 なら 「**対象 X が無いので蒸留できない**」 とユーザに報告して終了。 自動 fallback / 自動作成 はしない。 検査内容:

- `.cache/madb-last-release.txt` (= 前回取込 MADB release tag) と `data/madb-intake-state.yml` (= git追跡バックアップ、 phase2 が両方書く) の**一致**
- `.cache/db-v2.sqlite` (= ★種2 現行 = 派生 DB。 旧 `db.sqlite` は前世代)
- `data/seeds/series-supplement-v2.yml` (= ★種3 現行 = AI fill 蓄積。 旧 `-v2`無しは前世代)
- 種1 raw = `.cache/madb/metadata101.json` (= MADB release zip 由来。 旧表記の cm101.csv は無い) + `metadata101-clean.json` (= raw より新しいこと) + `metadata104.json` / `metadata504.json`
- `data/seed/mangaka.csv` (= 漫画家マスター、 種1 とは別 input)
- `scripts/clean-madb-seed.ts` / `_build-series-v2.py` / `_populate-v2.py` / `_distill-incremental-merge.py` / `intake.py` / ★`_monthly-distill.py` (= 実パイプライン。 [[monthly_distill_real_pipeline]]。 旧 `_diff-madb.ts` 等の .ts 差分3種は**廃止済=存在しない**、 チェックするな)
- `git status` clean (= **tracked の変更**が在れば abort。 untracked は警告のみ・混ぜない= `git add -A` 禁止)

### Phase 1: 差分 report + Go サイン待ち (= ★読み取り専用)

★実体 = `python scripts/_monthly-distill.py phase1` (= db-v2 も正規パス `.cache/madb/metadata101*.json` も**一切書かない**。 成果物は `-<tag>` 名で旧を上書きしない → 何度でも再実行可)。 内容:

1. MADB latest release を GitHub API で取得 (= ★`mediaarts-db/dataset` が正。 旧記載の MADB-Lab-Bot-public は404 = 2026-08-21実踏)。 ★最新 = 取込済 tag なら 「新releaseなし」 で**終了** (= 回さない)
2. metadata101/504 zip DL → unzip → clean → temp build → **merge dry-run** で各層の差分件数を表示:
   - 種1: 新ID / 新ISBN / 上流消失 (= 取込には無関係、 情報のみ) / 新 C-id (= 作者)
   - 種2: 新 series M 件 / 既存 series 追記 / ★純増 volume 件数 (= **merge dry-run が正**。 旧 `_monthly-diff-report.py` / `_distill_delta.py` は生レコード級で過大 = 使わない)
   - 種3: AI fill = ★**v2 機構では不要** (= kana は頁化時 NDL 確定、 genre/synopsis は enrich 系) → 予想 cost 0
3. 削除予測 = 0 件 を明示 (= merge は INSERT only 設計。 0 でなければ Phase 2 に進まず別途協議)
4. script 出力の 「Phase1 差分report」 をそのまま引用して 「**進めて OK？**」 でユーザ確認、 Go サイン (= 「OK」 / 「進めて」 / 「ゴー」 等の明示的肯定) 受領まで Phase 2 に進まない。

### Phase 2: Go サイン後の実行

順序厳守:

1. **種1 + 種2 取込** = `python scripts/_monthly-distill.py phase2 --tag <tag> --go "<Go サイン発話の引用>"`
   (= dry-run 再計算 → Phase 1 と一致確認 → db-v2 backup → merge --apply (INSERT only) → 件数検証 (= 不一致は backup から**自動復元**) → 正規パス差替 (= 旧は `-<旧tag>` 温存・削除しない) → マーカー2本 + 台帳 `data/madb-distill-ledger.jsonl`。 ★`--go` 無しでは動かない。 終了後にマーカー/台帳を単独 commit + push)
2. **派生層 + matcher + 本番 再生成** = `python scripts/_monthly-distill.py run intake` (= `intake.py --run` を**デタッチ起動**。 seedlint→volnum→roles→merge→seed4→detect → **matcher v9→v13→v14** → adult_us → enrich → trailing → **foreigndrop** → **promote(adult_us付与)** → durability (edisup/special/volnumoverride/coverfill) → **isbnloss**。 ~2.5h。 ★Bash の timeout で殺さない・完了は `status` の `EXIT=0`。 終了後 git diff で派生 seed / 本番yml を確認 → commit/push)
3. **enrich** = `python scripts/_monthly-distill.py run anilist` (= AniList フルダンプ ~2.5h、 任意・並走可。 backup → 再取得 → enrich map → status map) / synopsis 和訳 delta = skill `wayaku-enrich`
4. **取りこぼし頁化** = `_torikoboshi-genpages.py --list` → `--run` (= 最新 merge-manifest 自動、 3ゲート保留は人が裁定) → `_monthly-distill.py promote-made` → preview 確認 → 後始末3点 (= skill 6b/6c)
5. **月次サニティ** = `python scripts/_monthly-distill.py run sanity` (= 検出器を順に回し前回比 Δ) → Δ>0 の型を裁定
6. **成功判定** = `python scripts/_monthly-postflight.py` exit 0 → **最終 summary** (= 全件数 + 削除 0 確認 + 次月予測)。 本番 R2 公開は別途 「週次蒸留して」

※ 旧手順の 「種3 diff 元生成 / AI fill batch loop (= 100 entry/batch、 `_apply-fills.ts`)」 は v2 機構で**不要** (= 種3 スキーマ変更時のみ復活)。 en-fill / anilist_id 結線 (= 種3 書込) は deliberate に別途。

### 保護策 (= 5 層)

1. 取込前 `.cache/db-v2.sqlite` を `.cache/db-v2.sqlite.bak-distill-<ts>` に backup (= phase2 が自動。 旧記載の `db.sqlite` は前世代)
2. 種2 取込 (merge) は manifest (= `merge-manifest-<tag>-<日付>.json`、 挿入 id 記録) で可逆、 マーカー/台帳は **単独 commit** (= 後 revert 可能)
3. merge は `新series N / 純増volume M / skip 内訳` を強制 log 出力し、 phase2 が DB 件数の増分と突合 (= 旧 `applied=N, missing=0, overwrites=0` 相当)
4. tsc / vitest が以前緑なのに赤転落で abort
5. 想定外 delete / overwrite 検出で abort (= intake 末尾 isbnloss + postflight)

### Abort 条件 (= 検出したら即停止 + ユーザ通知)

- 種2 series 数が **減った** (= 削除発生、 異常) / phase2 の件数検証 NG (= 自動復元して停止)
- 種3 既存 key の content が変わった (= 上書き発生、 異常)
- typecheck / test の green → red 転落
- ※ 種1 上流の消失/訂正 (= MADB が過去 ISBN を訂正したケース) は INSERT only 取込に影響しない = 件数を報告するのみ (abort しない)

### 報告形式

- Phase 1 = script の 「差分report」 を引用 → 「進めて OK？」
- Phase 2 以降 = 各段の script 出力 (= merge 件数検証行 / intake `EXIT=0` / postflight の数値) を引用。 散文の自己申告で代替しない
- 完了時に累計件数 + 削除 0 + 保留件数 + 次月予測

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
- ★デラックス・レーベル割れ層 = `scripts/_audit-deluxe-label-split.py` (= **バーテンダー型** 2026-07-19に4連発で型化: 「◯◯デラックス」(KCデラックス/ジャンプ・コミックスデラックス/ビーボーイ…)は**レーベル名**なのに版種deluxeとしてstandardと分裂。SPLIT=巻相補(統合候補)/DUP=ISBN重複(汚染)/PARALLEL=別ISBNフル並走(**旧版×新装の正当2版の可能性=自動統合禁止**、3×3 EYES型)。出力=`docs/production-diagnostics/deluxe-label-split.tsv`。初回2026-07-19: SPLIT245/DUP24/PARALLEL181。是正はedition-overrides統合(バーテンダー/red Eyes/スピカ/これから俺は=適用済の型見本))。
- ★頁内書影重複層 = `scripts/_audit-cover-dup.py` (= **関東平野型** 2026-07-13: 同一頁の複数版に同じcover_url。 ★別ISBN×同一画像=Kobo補完の誤配置[同巻数ゲートが汚染で巻数一致した版を通す型]→Kobo再照会で出版社×巻数構成から帰属判定・タイは新しい版に残す。 同一ISBN×複数版=ISBN構造ダブリ[isbn-dup-cleanup領域・書影は症状]。 出力=`docs/production-diagnostics/cover-dup.tsv`。 versionsミラー[edition.volumes==versions[0]]は既知偽陽性=検出器で除外済)。
- ★**著者誤混入層** = `scripts/_audit-author-not-in-volumes.py` (= **よろしくメカドック型** 2026-08-02 ユーザ発見: 次原隆二の単独作に**秋本治**が著者として入っていた。秋本治の紐付き先は他が全て「こち亀」関連で1作だけ浮いていた。★判定= 頁の著者が**その頁のどの巻の書誌にも現れない**か。突合元は**楽天のauthor**(種1 metadata101 は古い書籍を収録しておらず、メカドックのジャンプ・コミックス12巻は1件も無く判定不能だった)。★他のsignalが駄目だった実測: series_key の qid と著者 qid の不一致=8,625件・「両方 writer_artist」で絞っても4,784件で、大半が**正当な原作+作画**(武論尊×池上遼一/原哲夫、アンソロジー、原作小説家 阿刀田高/橋田壽賀子/デュマ・フィス)。役割データが粗い([[author_roles_state]])ので**巻の書誌に載っているか**という一次情報でしか切れない。初回実測 **8,680件/5,120頁**。★自動削除禁止= 原作クレジット(矢立肇/富野由悠季)・スタジオ(さいとうプロダクション/ダイナミックプロ)・企画・解説者は表紙に出ないので大量に混じる。出力=`docs/production-diagnostics/author-not-in-volumes.tsv`。是正は `author-role-corrections.yml` の **remove**(誤クレジット人物の完全除去)。月次=新規増加分を見る)
- ★**版混在層** = `scripts/_audit-edition-mix.py` (= **ベルサイユのばら型** 2026-08-01 ユーザ発見: 「愛蔵版の書影が通常版に出ている」を追うと**版の取り違え**だった。中公愛蔵版2巻(9784120015601)が通常版(中公コミックスーリ)の2巻スロットに座り、**本当の2巻(9784124104257)は同巻番号に押し出されてどの頁にも出ていなかった**。同版に集英社の13/14巻まで混在し、発売日は元祖マーガレットコミックスのもの、しかも**元祖MC版は頁に存在しなかった**。★2signalを独立に見る: ①ISBN出版者記号の混在(TAIL=移籍で正当/HEAD/SCATTERED) ②★**楽天 seriesName(叢書名)の混在**=本命(愛蔵版もスーリも出版者記号は同じ978412なので①では捕まらない)。叢書名は表記ゆらぎが激しく(ジャンプコミックス/ジャンプ・コミックス、NICHIBUN COMICS/ニチブンコミックス)、**多数派と包含関係なら SERIES低、非包含なら SERIES高**に分けて優先度を付ける。初回実測: SERIES高1,241 / TAIL1,138 / HEAD448 / SERIES低411 / SCATTERED119。出力=`docs/production-diagnostics/edition-mix.tsv`。是正は `edition-canonical/*.yml` で版を再構築(★`suppress_types` に既存typeを列挙しないと旧版が残って**ISBNが重複**する。null だけでは bunkobon 等が残る=実踏)。月次=SERIES高の新規増加を見る)
- ★**楽天副題だけに出る抜粋本層** = `scripts/_audit-excerpt-subtitle.py` (= **Papa told me型** 2026-08-01 ユーザ発見: promoteの`DROP_SUBTITLE_PATTERNS`は**頁自身(種2)のsubtitle**しか見ないが、抜粋本の決定的証拠が**楽天のsubTitleにしか無い**ことがある。実例=『Papa told me（春/夏/秋/冬）』副題「シーズンセレクション」= 既刊の季節別選集(1996-11に4冊同時刊行)なのに本編と別頁化し、春だけ本編へ統合されて**4冊が3か所に割れ冬は欠落**。初回実測: **本番250頁/324巻**が該当。★**自動dropは禁止**= 副題の「〜セレクション/傑作集」は**レーベル名/叢書名**のことがあり(叶精作セレクション/クマのプー太郎セレクション/カプコン・セレクション型)、その頁の題は実在作品=消すと本物が死ぬ([[konbini_reprint_sweep]]と同じ教訓)。出力=`docs/production-diagnostics/excerpt-subtitle.tsv`(著者・巻数・レーベル・同著者他頁数つき=人が裁ける形)。月次=**新規増加分だけ**を見る)。
- ★**種1→種2 脱落層** = `scripts/_audit-seed1-lost.py` (= MADB(metadata101)に在るのに **種2に入らなかった**巻。 ★孤児series監査は「種2→本番」しか見ないので**この層は構造的に検出できない**[2026-07-26 ユーザ指摘]。 実測 **9,797巻**、脱落理由は**全件 `no_creator`**(schema:creator が空)= `_build-series-v2.py` のクラスタキーが「著者+題」のため著者不明の本を捨てる[[series_fragmentation_rootcause]]。 ★内訳: 成年1,339 / 非成年8,458。 題×レーベルで**2巻以上に纏まるのは1,168シリーズ**だが、その多くは**アンソロジー213 / 雑誌・ムック254 / オムニバス誌28**(著者が巻ごとに違う=著者空は正しい挙動)。 救済候補は実質**673シリーズ前後**(サムライキッズ33巻/メイドイン星矢26巻/集英社版学習漫画 日本の歴史19巻 等)。 出力=`seed1-lost.tsv` + `seed1-lost-groups.tsv`。 ★救済は種2再ビルドを伴うので未着手)。
- ★**孤児series層** = `scripts/_audit-orphan-new-series.py` (= **種2に在るのにサイトに1巻も出ていない** series を検出。 ★根因: promote は**元頁駆動**(`SRC_DIR.glob('*.yml')` = data/manga + preorder-pages)で **DB駆動でない** → 蒸留で種2に足しただけでは新規シリーズは永久に出ない。 2026-07-25 実測: 1.2.18の新292 series中 **未頁化207**、全期間では **未掲載46,874**(単巻97%)。 遠因=著者マスター(`data/seed/mangaka.csv` 6,748名)起点の初期設計[掲載済みの著者master在籍率70% vs 孤児0%]。 ★成人/コンビニ本フィルタでの圧縮は**不可を実証済**(再判定で新規adult 0件)。 出力=`docs/production-diagnostics/orphan-new-series.tsv`。 **月次は「新規series中の未頁化件数」を見る**= 0でなければ蒸留が頁を作れていないsignal)。
- ★外国版層 = `scripts/_audit-foreign-editions.py` (= ★**複数証拠**で scope外の外国語版を検出: ①latin題 ②シリーズ全ISBN非9784[978-4=日本] ③複数巻[typo説明不可]。 intakeの`foreigndrop`stageで`--apply`=純粋追加。 ★単巻のみ非9784はtypo懸念で報告のみ。 旧filterの穴=クリーンlatin題[Akira/Naruto外国版]がEMPTYslug/credit文字列依存をすり抜けていた、 を ISBN国コードで恒久封鎖)。
- ★AniListリンク層 = `scripts/_anilist-verify-gate.py` (= enrich全リンクをmatcher非依存の証拠合議[T題完全一致/W=P8731ラベル/R骨格/著者/年/巻/読切format]で採点。 FAIL/SUSPECTは `_anilist-adjudicate-gate.py`(dump native完全一致+著者ゲートでrelink/drop機械裁定)→残りAIスライス→`_gen-gate-overrides.py` で `anilist-link-overrides.yml` へ畳込=enrich除外/付替。 ★確認済みkeepは `data/seeds/anilist-link-confirmed.json`(key→a_idペア)で再フラグ抑止。 2026-07-18初回: 51,505リンク→drop813/relink616/FAIL 0化)。
- ★publisher層 = 各版の出版社は **種2 ISBN→metadata101 schema:publisher** から promote が自動導出 (= edition.publisher=当時社名、 work.publishers[]=社キー集合。 [[publisher_model_edition_level]])。 ★月次=**新規の未キー社名**(norm未解決)を巻数順に flag → 主要なら `data/publishers.yml` にキー追加。 alias追加は **ISBN出版者記号(帯)一致で同一実体を確認した時のみ**(だろう運転禁止)。 families/企業グループ畳みは**不採用**(実体=ISBN帯=統廃合に不変)。 生成器 `scripts/_gen-publisher-keys.py`。 ★ISBN-10/13混在を `_to_isbn13` で正規化必須。
- ★**途中巻断片層** = `scripts/_audit-solo-truncated.py` (= **蒸留で新規頁を作った後に必ず走らせる**。「5巻だけの頁」等=vol1不在の孤立頁を検出。正体は大半が①**彼岸島型**=残巻が別cluster(本編/親作)に番号衝突で眠りdedup負け ②**分裂cluster**=誤題typo(ちちょっと型)/表記揺れ(第二部vs第2部型) ③コンビニ廉価断片(凍牌竜凰位戦=秋田トップコミックス型)。2026-07-27実測: ユーザ発見17頁→種4+53巻/page-dedup2頁/canonical2で全数是正。★入口側は `_torikoboshi-genpages.py` の**3ゲート**(ISBN既在skip/★vol1不在→保留/★近似題(既存頁と包含一致)→保留)が頁化前に堰き止める=**保留リストは人が裁定してから頁化**。頁化ゲートと事後監査の両輪)。
- ★**年サフィックス二重頁層** = `scripts/_audit-year-suffix-dup.py` (= **ハンター×ハンター型** 2026-07-28ユーザ発見: slug衝突解決の`-姓+西暦`suffixが「同名別作品」でなく**同一作品の別クラスタ**(MADB別ID再登録/表記揺れ/頁化やり直し残骸)にも機械適用され二重頁化。同著者229組中ISBN交差165=REDO_LEFTOVER145(同一_skey残骸)+CLUSTER_SPLIT20(HxH/弐十手/バキ道…)。★入口ゲート= `_torikoboshi-genpages.py` に 同_skey既出skip+**衝突×同著者=保留**(著者未確認も保留=検査してから登録)を実装済。月次=本監査の新規増加0を確認)。
- ★**巻×発売日の大逆行層** = `scripts/_audit-vol-date-regression.py` (= **ギャラ型** 2026-08-17 ユーザ発見「三巻以降別物」: 同一edition内で巻番号が進むのに発売日が**5年以上逆行**=同一クラスタに別作品/別時代の版が同居し番号衝突で接ぎ木された頁。ギャラ=リメイク1-2巻2019-20+原作3-8巻1980-81[原作1-2巻はdedup負けで不可視]。★ISBN有→無の境界が強シグナル。初回実測 **541頁/573版**(30年+86/20-29年116/10-19年199/5-9年172)、主流は「復刻・新装の先頭巻が旧初版の枠を占有」する逆ギャラ型[タンク・タンクロー/鉄腕アトム/ハレンチ学園]。出力=`docs/production-diagnostics/vol-date-regression.tsv`。是正2通り: 別作品=**ギャラ式頁分離**(同_skeyのstub×2+edition-overrides+★新設`anilist:false`でenrich混線遮断) / 同一作品の版違い=edition-canonical版再構築。月次=新規増加分を見る)。
- ★**canonical seed健全性層** = `scripts/_check-edition-canonical.py` (= **版canonical(693本)の番人**: ★壊れたseedはpromoteが`except: continue`で**無警告skip**しreflectは成功と表示する(実験人形ダミー・オスカーで実踏)ため専用検査が要る。見るもの= YAMLパース/slugとファイル名の一致/死にキー(manga.v2不在)/巻番号重複/release_dateが文字列か/種4取りこぼし(canonicalが裏取り済み巻を上書きして消す)/★**連載中の続巻取りこぼし**(検査7 2026-08-20新設=seed主版ISBNで種2を逆引きし同imprint・seed最終日以降の後続巻を検出。canonicalは巻を固定するので連載中は続巻が永久に頁へ出ない)。★reflectのcanonicalゲートに組込済(対象slugだけ`--slugs`で検査しNGなら反映中止)。月次=NG 0 を確認、鳴ったらseedへ種2の値で追記 or opt-in `open_tail: true`)。
- ★**数字表記揺れ分裂層** = `scripts/_audit-numeral-variant-split.py` (= **ロザリオとバンパイアseasonⅡ vs season2型** 2026-07-27ユーザ発見: ローマ数字/漢数字/カナ数詞(ツー)の揺れで同一作品のクラスタが割れ、後年の巻が別頁化する。正規化=共有 `scripts/_title_numnorm.py`(ゲート `_torikoboshi-genpages.py` と同一実装=直すなら両方に効く)。SPLIT=巻相補(統合候補・初回3件全適用済) / DUP=巻交差(二重頁疑い・初回16件=worklist) / SEQ?=題末尾数字の単巻(続編正当例[マンガ家さんと2]があるため**報告のみ・自動統合禁止**)。出力=`docs/production-diagnostics/numeral-variant-split.tsv`)。
- ★**廉価パック/BOX構成員層** = `scripts/_audit-price-pack.py` (= **猫と竜型** 2026-08-26型化: スペシャルプライスパック(2026-07宝島社)が正規巻と同題・同巻番号でMADBに入り、1.2.19で猫と竜1-3巻の主枠を2018原版から奪った。★署名はseries/edition層に無く **metadata101のschema:alternativeHeadline / description内ISBN(set)** にのみ在る=種1 raw直接走査。初回100件・本番掲載15件は全裁定済(是正2=サイコ幽霊愛蔵版[imprint'collection box'恒久drop]+白妖の娘セットISBN / 正当13)。出力=`docs/production-diagnostics/price-pack.tsv`。月次=本番掲載の新規増加を裁定)。
- ★**number=0の1巻不可視化層** = `scripts/_audit-vol0-hidden-first.py` (= **泣かせたくてどうしよう型** 2026-08-26型化: promoteの「同editionにnumbered巻があればnumber=0をskip」規則が、無番号登録の**真の1巻**を続巻到着の瞬間に本番から消す。★is_extraは99.95%が1で番外編と区別不能=唯一の機械信号は「0巻日付<全numbered巻」。初回877件→HIDDEN_FIX66を**楽天題ゲート**(副題/アンソロ/限定版=HOLD)で46巻適用[孤独のグルメ/リボンの騎士等44頁vol1復元]。sink=種4-auto(source:vol0-first)。出力=`docs/production-diagnostics/vol0-hidden-first.tsv`。月次=HIDDEN_FIXの新規増加→--apply)。
- ★**レーベル表記ゆれ版分裂層** = `scripts/_audit-canonical-imprint-split.py` (= **ARMS型** 2026-08-28ユーザ発見「21巻が同じ箇所に分裂」: MADBのレーベル誤記(少年サンデーコミ**ツ**クススペシャル / 正=コミ**ッ**クス)を種2が別edition行として持ち、2026-08-17の「ギャラ型是正」一括処理がその区切りをそのまま `edition-canonical` へ焼き込んだため、21巻だけが別版タブへ分裂し**主版は21巻抜け**になっていた(=巻抜け仮想にも現れる)。判定= imprintを正規化(小書きカナ→大書き/中黒・空白除去)して一致する版が同一頁に2つ以上。★**自動統合は禁止**(新装版/復刻版が正当に別版な場合がある。トラジマのミーめ=2025復刻版が実例)。**巻番号が相補**なら統合候補、**重複**なら別run濃厚。裏取りは楽天seriesName(キャッシュ1パス走査で足りる)+Wikipedia刊行リスト。出力=`docs/production-diagnostics/canonical-imprint-split.tsv`。初回13件[ARMS是正済]。月次=新規増加分を見る)。
- ★**刊行run分裂層(名前非依存)** = `scripts/_audit-edition-run-split.py` (= **ARMSワイド版型** 2026-08-28ユーザ発見: 上の表記ゆれ検出器は imprint 文字列の近さで探すため、**英字レーベル名vs和名**(SHONEN SUNDAY COMICS WIDE EDITION ⇔ 少年サンデーコミックスワイド版)や**略称vs正式名**(KCスペシャル ⇔ 講談社コミックススペシャル)を取り逃す。そこで名前を一切見ず、①出版社一致(orISBN出版者記号共通) ②巻番号が重複しない ③合わせると連番 ④巻順で発売日が単調増加 の4条件で「1本のrunが2版に割れている」を検出する。★新装版/復刻版は②か④で落ちるので混ざりにくい。tierA=imprint正規化で一致(ほぼ確実) / tierB=名前が違う(要外部裏取り)。初回 **65ペア/59頁**(A8/B57) → 2026-08-28に全数裁定し **57頁を統合適用済(残7)**。★裁定の型: merge56/keep_separate2/other_issue1、うち**反証で1件が覆った**(biba-usagi-kozou=ノーラコミックスdeluxe→無印は真のレーベル変更の可能性。決着にはNDL by-ISBNで5巻の奥付シリーズ表示が要る)。★真因は3層あった: ①レーベル表記ゆれ ②**種2のクラスタ分裂**(編集クレジット混入・著者名の大小文字) ③★**種4(volumes-supplement)の `edition_type` 既定値 standard**(2026-07-28の続巻ハーベストが既定値で投入し、種2側に該当typeが無いため promote が『通常版/imprint=出版社名』という**実在しない幻の版**を作る型。the-band/hata-manjirou/hi-ni-nagarete/ennead/sekai-no-hate で実踏 = **canonicalを起こすのではなく種4のedition_typeを直すのが根本**)。出力=`docs/production-diagnostics/edition-run-split.tsv`。★自動統合禁止=楽天seriesName(キャッシュ1パス)+MADB容器ID `schema:isPartOf` +ISBN連番+刊行ペース+外部刊行リストで1件ずつ裏取りし、**反証役を別に立てる**(容器IDは*作品*容器で版容器ではない=単独では同一run証明にならない。243容器中81本が複数brandを含む))。
- ★**楽天題が「親題+巻番号」を名乗る未掲載巻層** = `scripts/_audit-subtitle-orphan-volume.py` (= **Sugar&Spice型** 2026-09-03 ユーザ発見「完結してるが抜けているし足りない」: 各巻が固有の巻題を持つ作品で、MADBが17/19/20巻を巻題(Somethin' stupid等)を**題として**別IDで登録→種2の著者+題キーが別sid(0巻/extra)に落とし、本編頁は「17巻欠け+18巻で終わり」に見えた。★既存監査の死角= 孤児sidは単巻・未頁化なので solo-truncated(孤立**頁**)の対象外、巻抜け仮想は内側の穴しか見えず**末尾巻**は「無い」ことが分からない。唯一の機械信号は楽天側(subTitle「Suger ＆ Spice 17」/ title「Rose＆Beast Sugar＆Spice19」)。★実装= 楽天キャッシュ2本(delta 828MB+旧373MB)を1パスし、副題/題末尾/題中の「親題+番号」を抽出→正規化題で既存頁と完全/接尾/接頭一致→そのISBNが本番page-indexに無い巻を列挙。列= 巻状態(MISSING_TAIL/MISSING_GAP/OTHER_ISBN=同番号が別ISBNで既在) × 種2(SPLIT=別sidに眠る/SAME_SID=同sidなのに未表示/ABSENT=真の取込もれ) × tier(A=著者一致) × 一致(EXACT/SUFFIX/PREFIX) × **疑**(YEARLIKE/EDITION/SPINOFF/LABEL/SEQTITLE/DROPIMPRINT/PUBMISMATCH/PREVIEW=偽陽性の型を落とさず立てる)。★芯= MISSING×A×EXACT×疑なし。初回= 候補23,957/芯**1,365巻・809頁**(ABSENT 1,134 / SPLIT 172[69頁: トリニティセブン19-34/六道の悪女たち9-26/ドカベンDT編32-34/Papa told me cocohana6-14…] / SAME_SID 59[0巻規則で隠れた真の0巻=ドラえもん/ハヤテ等・page-dedup残骸・override固定])。★**自動適用禁止**(SEQTITLE=リング2/トイ・ストーリー2型の続編題と番号入り巻題は機械で割れない・LABEL=本宮ひろ志傑作集7型の叢書番号)。是正はSPLIT=種4結線 or merge / ABSENT=既存の`_register-seed4-ndl.py`ゲート経由 / SAME_SID=per-case。出力=`docs/production-diagnostics/subtitle-orphan-volume.tsv`。★**第2部(楽天非依存)= edition-overrides固定頁の続巻取りこぼし**: overridesは巻を固定するので連載中は種2に続巻が来ても永久に出ない(canonical側の検査7に当たる番人がoverrides側に無かった)。初回**25巻/10頁**(フェルマーの料理8巻 2026-06 / 聖女に嘘は通じない6巻 / 壁抜けバグ12巻 2026-07 = 現役連載3頁)。出力=`overrides-frozen-tail.tsv`。月次= 芯の新規増加+第2部の連載中頁を見る。先に `_exists.py --build`)。★**適用は `scripts/_apply-subtitle-orphan-volume.py`**(2026-09-03 正式化。芯を機械ゲート= レーベル整合[正規化一致/**経験別名表**=同一ISBNを種2 imprintと楽天seriesNameが別名で呼ぶペア sid≥3(検出器が `.cache/label-alias-pairs.json` に同時生成)/自頁の既存巻の楽天seriesName一致/包含はstandard版のみ4字以上] × 対象版[楽天seriesNameに合う版>standard最大巻版、文庫・完全版だけの頁は見送り] × 発売日順[「日付を持つ巻」基準・1か月許容] × 同番号無し × ISBN未在 × series_key bind × override(editions固定)・canonical外。SPLITは種2版種keep/番号整合/アニメ系除外/0巻除外+**同クラスタ掃引**(採択sidの兄弟巻=楽天キャッシュに無い巻も拾う)。通過分を `volumes-supplement-auto.yml` へ純粋追加(source: seed2-split-auto / rakuten-title-tail)→ `.cache/subtitle-orphan-apply-stems.txt` を reflect --only へ。見送りは理由列つきで `subtitle-orphan-volume-review.tsv`(人はここだけ見る。日付逆行=頁側が新装/後刷り=版の付け直し案件が主、canonical頁は run 再構築案件)。初回累計= override 8頁 / 別sid 195巻・62頁 / 取込もれ 643+371+7巻。★SAME_SIDは適用しない[真の0巻=表示方針マター(ドラえもん0巻はユーザ裁定でoverride直書き)/page-dedup残骸/MADB誤番号])。
- 既知の例外型: 再登録の別 ID 二重化 / MADB 形式変更 (= タグ消失・年→巻番号) / 成年誤 flag (= 新レーベル未カバー) / 雑誌漏れ (= cm105 凍結) / 巻番号水増し (= 下=3型)。

---

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
