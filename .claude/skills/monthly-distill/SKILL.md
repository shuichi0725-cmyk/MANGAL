---
name: monthly-distill
description: 月次蒸留して=MADB取込→intake(フルpromote)→enrich→頁化→サニティ→postflight。status→phase1(読み取り専用)→Goサイン→phase2(--go引用)→run intake の1本道(~3時間+)。新releaseなしなら何も回さず終了
---

# 月次蒸留して

トリガー語: **「月次蒸留して」**(完全一致)。原則(純粋追加・abort条件)は CLAUDE.md「月次蒸留 protocol」、
**手順の正本はこの skill**。実体 = **`scripts/_monthly-distill.py`**(2026-09-02 一括化。それまでの env override 手打ち列は廃止)。

## 大原則
種1/種2/種3は壊さない。純粋追加only。上書き/削除検出=即abort+報告。**Phase1の差分報告→ユーザGoサイン受領までPhase2に進まない**。
★db-v2 を書くのは `phase2` の merge --apply だけ。それ以外の全コマンドは読み取り専用(何度打ち直しても壊れない)。

## NEVER
- `status` が「新releaseなし」なのに何かを回す(種2は不変・~5時間の無駄。「差分なし」と報告して終了)
- Goサインの引用なしに `phase2` を打つ(`--go` 無しでは動かない設計。「いいね/なるほど」は肯定ではない)
- `intake.py --run` / フルpromote を **Bash の timeout 付きで直接回す・途中で kill する**(フルpromoteは開始時に manga.v2 を全消し→再生成。途中killは半端状態=2026-07-06型)。必ず `run intake`(デタッチ)
- `_populate-v2.py` / `_build-series-v2.py` を env 無しで手打ちする(populate は正規db-v2への全再投入ガードで止まるが、手打ち自体をしない)
- 種4-auto(`volumes-supplement-auto.yml`)を全消し/再生成する(蓄積台帳。2026-08-21実害883巻消失)
- 頁化ゲートの保留を手書きの源頁で迂回する
- 本番R2へ出す(=「週次蒸留して」の領分)

## 手順(1本道)

### 0. 最初に必ず(30秒)
```
python scripts/_monthly-distill.py status
```
- 「★新releaseなし(X = 取込済)」→ **ここで終了**。ユーザに「取込済 X = GitHub最新 X。今回は差分なし。次リリースは毎月17〜22日頃」と報告。
- マーカー不一致/Phase0 FAIL は**直さず報告**(自動fallback禁止の思想)。job 行に RUNNING があれば前回の続き=そちらを先に見る。
- `/clear` 後の再開もこのコマンド(成果物の有無から次の一手を出す)。

### 1. Phase1 = 差分report(★読み取り専用・~5分)
```
python scripts/_monthly-distill.py run custom -- python scripts/_monthly-distill.py phase1
python scripts/_monthly-distill.py status        # job custom … EXIT=0 まで待つ(ログ末尾)
```
- 中身: Phase0 → zip DL(101+504) → unzip → clean(~5分) → 種1diff(15秒) → temp build(build-series/populate) → merge dry-run。
  成果物は全部 `-<tag>` 名(`.cache/madb/metadata101-<tag>.json` 等)= 正規パスも db-v2 も**一切変わらない**。再実行は済んだ段をskip。
- ログ末尾の「**月次蒸留 Phase1 差分report**」ブロックを**そのまま引用**してユーザに提示し、「進めて OK？」で止まる。
  (種1=新ID/新ISBN/上流消失、504=新C-id、種2=新series/純増volume(★これが正)、種3=AI fill不要、削除予測0)
- ★旧 `_monthly-diff-report.py` / `_distill_delta.py` は使わない(生レコード級で過大: 11,732 vs 真値1,124の実績)。

### 2. Goサイン → Phase2(数分)
```
python scripts/_monthly-distill.py phase2 --tag <tag> --go "<ユーザの発話をそのまま>"
```
- 中身: dry-run再計算→phase1と一致確認(不一致=abort) → db-v2 backup → merge --apply(INSERT only) → **件数検証**(series/editions/volumesの増分がmerge出力と一致・quick_check。NGは backup から自動復元して停止) → 正規パス差替(`.cache/madb/metadata101.json`/`-clean`/`metadata504.json` ← 新tag、旧は `-<旧tag>` 温存) → `.cache/madb-last-release.txt` + `data/madb-intake-state.yml` + 台帳 `data/madb-distill-ledger.jsonl`。
- 終了メッセージの `git add … && git commit … && git push` を実行(マーカー/台帳の単独commit)。
- 出力の「検証 ✓ series +N / editions +E / volumes +M」行を報告に引用(=削除0・上書き0の根拠)。

### 3. intake(~2.5h・デタッチ)
```
python scripts/_monthly-distill.py run intake
python scripts/_monthly-distill.py status        # job intake … RUNNING → EXIT=0
```
- 実体= `intake.py --run`: seedlint→volnum→roles→merge→seed4→detect→match v9→v13→v14→adultus→enrich→trailing→foreigndrop→**promote**→edisup/special/volnumoverride/coverfill→**isbnloss**。ログ= `.cache/madb-distill/run-intake-<ts>.log`。
- 60秒超は Monitor で節目だけ(1万頁ごと/ABORT/EXIT)。promote の完了後居座りは **os._exit で解消済(2026-09-02)**=待てば終わる。killしない。
- EXIT≠0 はログ末尾の `✗ ABORT: stage [名]` で判断: seedlint=seed壊れ(yaml.safe_load検証) / clean鮮度=phase2の差替漏れ / isbnloss=理由なし消失(`docs/production-diagnostics/isbn-loss.tsv` を1件ずつ裁定・台帳記帳) / それ以外=当該scriptの traceback を読む(1.2.18で trailing の merge_keys / foreigndrop の2スペ追記を直した型)。
- 終了後: `git status` → 派生seed(`series-merge-auto.json` / `non-manga-drop.yml` 等)の diff を確認 → commit/push。manga.v2 は gitignore(ディスク上で再生成済)。

### 4. enrich(任意・並走可)
```
python scripts/_monthly-distill.py run anilist   # ~2.5h: dump backup→progress消去→フル再取得→enrich map→status map(縮小なら自動復元+abort)
```
- deltaは5,000capで月次には不足=フルダンプが正(2026-08-21確立)。synopsis和訳delta= skill wayaku-enrich。
- ★種3 AI fill(旧v1の100件batch)は **v2機構では不要**(kana=頁化時NDL確定 / genre・synopsis=enrich系。新seriesは種3未登録のままpromote無依存=1.2.19確認)。種3スキーマ変更時のみ復活。

### 5. 頁化(新規seriesの源頁生成)
```
python scripts/_torikoboshi-genpages.py --list          # 1行目 "manifest: … tag=<tag>" が取込先と一致するか確認
python scripts/_torikoboshi-genpages.py --run           # 源頁 → data/seeds/source-pages(git追跡)。NDL照会あり(1.2秒/req)
python scripts/_monthly-distill.py promote-made         # 作った頁だけ promote --only-file
```
- manifest既定=最新mtime(旧=1.2.18固定で翌月以降は前月分を掴む罠→2026-09-02是正)。
- **3ゲート保留は自動頁化しない**(ISBN既在skip / vol1不在→保留 / 近似題→保留)。種2横断(`_ledger` / `_exists --isbn`)で彼岸島型・分裂・コンビニ断片を裁定しユーザ報告してから。前回1.2.19の保留54件= `docs/production-diagnostics/torikoboshi-1219-holds.tsv`(未消化=持ち越し)。
- ★後始末3点(2026-08-22確立): ①**書影live補充**(新規ISBNはcovers seed未収録が普通。楽天live by ISBN→cover-override.jsonl→再promote) ②**slugレビュー→公開前rename**(ヘボンfallbackの外来語英綴り化/促音バグ。未公開ならalias不要) ③**コンビニ/再録の目視**(レーベル名題・故人作家の新刊=再録→non-manga-drop)。
- preview投入= skill test-deploy(セット入替→索引→push→15-20分待ち)。★源頁は `data/seeds/source-pages/` にあることを確認(data/mangaはgitignore=消えると次のフルpromoteで頁が黙って消える。2026-08-26に源なし258頁復元)。

### 6. 月次サニティ
```
python scripts/_monthly-distill.py run sanity            # 検出器17本を順に回し前回比Δ(~15分。結果= docs/production-diagnostics/sanity-runs/sanity-<ts>.json=git追跡)
python scripts/_monthly-distill.py sanity --heavy        # 楽天キャッシュ走査3本(excerpt-subtitle/edition-mix/author-not-in-volumes)も
```
- Δ>0 の検出器 = 今月増えた型 → CLAUDE.md「月次サニティ監査」節の該当型で裁定。結果JSONと更新されたTSVは commit(次回のΔ基準)。
- rc≠0 の読み分け: ①検出器自体の故障(traceback=直してから) / ②「該当あり」を exit 1 で表す検出器= **isbn-loss(理由なし消失あり=裁定・消し込み台帳へ) / price-pack(本番掲載あり=新規増分を裁定) / edition-canonical(異常あり=seedへ追記)**。tail で区別。
- 2026-09-02 ベースライン実走: 17本 計~15分(title-eq-author 252s・kana-from-other-volume 228s、他は70s以下)。
- 必ず見る: solo-truncated(頁化した月は新規頁ヒット0) / AUTO_FIXED急増(新誤番号型) / price-pack・vol0-hidden-first の本番掲載増 / edition-canonical NG=0 / isbn-loss 理由なし0 / 表示カタログslug集合diff(git HEAD索引 vs 新索引。消失は全件説明可能)。
- 対象外(手動): `_furigana-audit`(NDL照会) / `_gen-publisher-keys`(publishers.yml を書く=読み取り専用でない) / `_coverage-audit`(旧 .cache 依存)。

### 7. 成功判定
```
python scripts/_monthly-postflight.py     # exit 0 が完了条件(seed lint/manga.v2≥66k/ISBN消失0/種4-auto不減/publisher unknown不増/マーカー整合/頁化月のsolo-truncated 0)
```
- 併せて言うこと: **Goサイン受領の発話引用** / phase2 の「検証 ✓」行 / intake の `EXIT=0` / 頁化件数+ゲート保留の裁定結果 / サニティΔ / tsc・vitest green。どれかが言えない=完了していない。
- 最終summary= 累計件数+削除0+保留件数+次月予測。本番R2公開は別途「週次蒸留して」(ここでは出さない)。

## 所要の目安(新PC実測)
Phase1: **~5分**(2026-09-02 リハーサル実測 4分16秒 = clean 150s / build-series 53s / populate 25s / dry-run 11s / 種1diff 14s。次回は DL 50MB が乗る) / phase2: 数分 / intake: ~2.5h(matcher~20分・promote~40-110分) / AniList: ~2.5h / 頁化: 件数×NDL1.2秒+レビュー / サニティ: 数十分。

## 罠(型)= 機械封鎖済みでも知っておく
- **cleanの正規パス**= `.cache/madb/metadata101-clean.json`(promoteの出版社導出が読む)。旧手順で別ディレクトリに置いて**新刊全部が出版社(unknown)**(1.2.19実害1,182頁)。→ phase2 が差替・Phase0/intake の鮮度ガードが二重封鎖。
- **manifest名のtagズレ**: merge の manifest 名/中身が「1つ前のtag」だった(中身 "1.2.18" 固定リテラルも)→ `--tag` 必須化(phase1/2が付ける)。genpages はこの manifest を掴むので**ズレると別月を頁化**する。
- **populate の正規DB誤爆**: `MADB_DB` 無しで打つと series/volumes を DELETE→全再投入(cover/enrichment喪失)→ `--wipe-real-db` 無しは abort に封鎖。
- **種4-auto全消し**(2026-08-21): `_register-seed4-ndl.py --apply` が既存を読まず全上書き→merge書込化+intake末尾isbnloss+preflight減少FAIL+clean鮮度ガードの4層。retireは「ISBNが種2に実在する巻だけ」個別除去。
- **promote完了後の居座り**: 巨大heap解放でプロセスが残る→ `os._exit(0)`(2026-09-02)。intake経由の終了待ちも消えた。
- **数値ペンネーム**(「296」/「359」型)= YAML/DBのintが re.sub でクラッシュ・Zodでビルドskip→promote/監査は str() 防御済。新規scriptでも `str(name)`+quote。
- **seed機械追記後は必ず yaml.safe_load 検証**(種4はlist itemが**カラム0**。2スペで書くとparse死=silent不着。「: 」を含む値は必ずquote)。
- **canonical結線頁**(edition-canonical/*.yml)は overrides も種4も後負けで無効=巻修正はcanonical本体へ。
- **コンビニ廉価再録レーベルは頁化しない**(秋田トップコミックス=DROP_IMPRINT封鎖済。「◯◯スペシャル」型はtitle単位)。
- **頁のdropは必ず `_reflect-targeted.py --drop` 経由**(手でyml消すと索引・ストックに残骸=検索404)。源頁ミラー `data/seeds/source-pages/` も消す。
- **再登録の別MADB-ID二重化**(虚構推理vol23型)→ merge の ISBN/madb_book dedup guard + 監査。
- **Bashツールの heredoc は `'` と `\` が化ける**→ 複数行scriptは Write で scratchpad に書いて実行。ログ読みは utf-8 で(cp932混在)。
- **Windowsの os.kill(pid, 0) はプロセスを殺す**→ 生死判定は ctypes OpenProcess(status が実装済)。CommandLine正規表現で殺すと自分のシェルも死ぬ。

## 検算(リハーサル)= 取込済tagで手順だけ通す
```
python scripts/_monthly-distill.py phase1 --tag <取込済tag> --rehearsal     # 期待: 新series 0 / 純増volume 0(phase2は不要)
python scripts/_monthly-distill.py seed1-diff --old .cache/madb/metadata101-<旧tag>.json --new .cache/madb/metadata101.json
```
- 2026-09-02 実測(1.2.19で検算): seed1-diff 1.2.18→1.2.19 = 新ID+1,541/新ISBN+1,479/上流消失0(記憶の+1,546/+1,481/消失7は算出法差)。Phase1リハーサル = **新series 0/純増volume 0(冪等性実証)・正規パスとdb-v2不変・4分16秒**。詳細= 記憶 [[monthly_distill_orchestrator]]。
