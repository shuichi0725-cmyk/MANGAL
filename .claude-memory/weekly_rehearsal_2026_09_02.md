---
name: weekly-rehearsal-2026-09-02
description: "週次蒸留の「アップ直前まで」リハーサル(2026-09-02)。実測=step1 1h50m/ビルド42分/PUT見込み180,880。見つけた穴=アイドル書影seed未反映337頁・dropの連鎖alias・ps1ログ文字化け。R2/KV/finalizeは未実行"
metadata: 
  node_type: memory
  type: project
  originSessionId: bfd1bf84-8e24-4963-87bc-f48e87455701
  modified: 2026-09-02T10:44:40.677Z
---

2026-09-02 ユーザ指示「週次蒸留をアップする直前までやって問題点の洗い出し。絶対アップはしない」で実施。
発動トリガーは「週次蒸留して」ではないので、**R2同期・KV同期・finalize・wrangler deploy は一切実行していない**([[feedback_weekly_distill_exact_trigger_only]])。
やったのは step1(19step)→生成物commit+push→preflight --fix→モード判定(CODE週)→フルビルド→sitemap→`_r2-sync.py --dry --prune`(計算のみ)まで。

## 実測(次回の見込みに使う)
- step1: 19step で **1h50m**(cover-refresh 58分=1,454巻照会/57頁差替/err0)。skillの「~1時間」は過小。
- フルビルド: **42分**(90,269ルート、out/manga=138,400枚=69,200頁×2)。skillの2.5〜3.5hは旧PC実測。初回300s超過120件は全て2回目で通過(warmup型)。
- r2-sync --dry: ハッシュ照合~10分。**PUT 180,880 / 削除136**(prune台帳40頁×2+著者頁5×2+旧chunk46)。索引overlay 22.0MB。
- R2予算: 今期(8/27〆)既に181,146。今回分を出すと約36.2万。preflightの着地見込み751,146/1,000,000。
- tsc緑・vitest 273/273緑。本番smoke(--no-post)PASS 13/0。

## 見つけた穴(是正状況)
1. **アイドル運転⑩(placeholder-cover-refresh)の seed 追記は頁に反映されない**: cover-override.jsonl を ISBN最終行勝ちで畳み、URLが yml に無い頁=**337頁**(当日239+8/22〜27の98)。一覧=`docs/production-diagnostics/cover-override-unreflected-2026-09-02.txt`。是正=週次前に `_promote-bulk-v2.py --only-file` で反映(未実施・ユーザ裁定待ち)。恒久策=step1にstage追加(未実装)。
2. **頁dropで連鎖alias(旧→統合先→drop頁)が残る**: 9/1のスゴ盛dropで plain kiwami 向け3本が残り preflight 8b FAIL。**削除して是正済**(commit 8de66d807)。[[drop_page_redirect_chain]] の「行き先側でも検索」を連鎖2段目まで見る必要がある。
3. **ps1ラッパの文字化け**: `.cache/_wkstep1.ps1`/`_wkbuild.ps1` に UTF-8 指定が無くログが二重変換で化けていた。両ps1を修正済(skillにも追記)。
4. アイドル書影ジョブ(`--all`)が step1 と並走し同じ seed に追記(排他なし)。行単位flushで実害は出なかったが、本番週次前は止めるのが安全。
5. prune台帳41件は全て本番200のまま(devilman-lady-2000 だけはR2実体なし=301のみ)。次の本物の週次で `--prune` 必須。
6. /shinkan 月別24月・this-week・next-month は本番でまだ404(CODE週の公開待ち)。今回の out/ には26頁とも在り、sitemap 90,021 URL に載る。

## 生成物の状態
- step1生成物は commit 8df81592f で push 済(preview は GitHub Actions 成功)。out/ と .cache/r2-manifest.json は**未同期の状態のまま**(本物の週次はstep1からやり直す前提。out/はビルド成果物として残置)。
