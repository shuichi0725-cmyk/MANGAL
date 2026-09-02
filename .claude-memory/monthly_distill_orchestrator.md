---
name: monthly_distill_orchestrator
description: 【正本】月次蒸留は scripts/_monthly-distill.py の1本道(status→phase1読取専用→Goサイン→phase2 --go→run intake→頁化→run sanity→postflight)。2026-09-02 見直しで罠6本を機械封鎖。新releaseなしは何も回さず終了
metadata: 
  node_type: memory
  type: project
  originSessionId: f2cce216-3e15-4659-8ab0-350d4f267a00
  modified: 2026-09-02T13:52:39.184Z
---

2026-09-02 ユーザ依頼「今月次蒸留を行っても前回と何も変わらないが、手順と Opus が回す時の事故防止を見直してほしい」で実施。
MADB 最新 = 1.2.19(2026-08-21 公開)= 取込済なので実蒸留はせず、**手順の一括化+罠つぶし+リハーサル(検算)**を行った。

## 正本
- 手順 = `.claude/skills/monthly-distill/SKILL.md`(全面改訂・1本道の runbook)。原則/abort = CLAUDE.md「月次蒸留 protocol」(Phase0/1/2 を script 実体に合わせて改訂・旧 AI fill batch/select-supplement-diff/db.sqlite の記述を除去)。
- 実体 = **`scripts/_monthly-distill.py`**: `status` / `phase1 [--tag] [--rehearsal] [--force]` / `phase2 --tag --go "<発話>"` / `run intake|anilist|sanity|custom -- …`(デタッチ起動・ログ末尾 `EXIT=n`・二重起動ガード) / `sanity [--heavy]`(read-only 検出器20本=heavy 3含む+前回比Δ) / `promote-made` / `seed1-diff` / `anilist-seq`。
- マーカー2本 = `.cache/madb-last-release.txt` と git 追跡 `data/madb-intake-state.yml`(phase2 が両方書く。1.2.16 のまま陳腐化していたのを 1.2.19+履歴に更新)。台帳 = `data/madb-distill-ledger.jsonl`(純追記)。

## 封鎖した罠(Opus 運転で踏みそうだった順)
1. `_populate-v2.py` を env 無しで打つと正規 db-v2 の series/volumes を DELETE→全再投入(cover/enrichment 喪失)→ `--wipe-real-db` 無しは abort。
2. `_torikoboshi-genpages.py` の manifest が `merge-manifest-1.2.18.json` 固定(1.2.19 はたまたま manifest 名ズレで一致していただけ)→ 既定=最新 mtime + `--manifest`。1行目に tag を表示。
3. merge の manifest 名が「1つ前の tag」・中身 `"tag": "1.2.18"` 固定リテラル → `--tag` 必須化(phase1/2 が付ける)。temp db 既定(db-v2-1217-temp)廃止。
4. promote 完了後の居座り(巨大 heap 解放)→ `os._exit(0)`。`--only kimetsu-no-yaiba` で 45 秒 exit 0・出力不変(popularity 差のみ=enrich map 更新由来)を確認。intake 経由の終了待ちも消える。
5. `_monthly-phase0.py`: 104/504/tsx/orchestrator/state.yml を必須化、`.cache` マーカー vs yml の整合 FAIL、**untracked は警告のみ**(ユーザの `fable - コピー.bat` 等で毎月 FAIL しないため。tracked 変更は従来どおり abort)。
6. `_build-series-v2.py` に `MADB_META504` env(Phase1 の temp build を正規パス非依存に=Go 前に正規パスを一切触らない)。
- ほか: merge/populate に utf-8 reconfigure(cp932 コンソールで `✗` が UnicodeEncodeError→exit 1 になっていた)。postflight にマーカー整合 FAIL と「源なし manga.v2 頁」INFO(2026-09-02 時点の既知 2 件: shikakenin-fujieda-baian-saitou / tales-of-the-abyss-rei)。

## 検算(2026-09-02)
- `seed1-diff` 1.2.18→1.2.19 = 新ID +1,541 / 新ISBN +1,479 / 上流消失 0・0(@id 基準でも同値)。記憶 [[distill_2026_08_1219]] の「+1,546/+1,481/消失7/2」は別算出(概算)= 以後は script 値を正とする。
- `phase1 --tag 1.2.19 --rehearsal`(デタッチ `run custom` 経由)= 取込済 tag で Phase1 全段を通した。**結果 = 新series 0 / 純増volume 0 / 新edition 0(期待どおり=merge の冪等性実証)**、種1 新ID 0・新ISBN 0、504 新C-id 0(総 75,628)。正規パス(.cache/madb/metadata101*.json / 504)と db-v2 の mtime は 8/21 のまま=不変を確認。
  **所要 4分16秒**(101 zip DL skip / 504 zip DL 3.3MB / unzip 668MB / clean 150s / 種1diff 14s / build-series 53s / populate 25s / dry-run 11s)。新PCでは Phase1 は「数十分」でなく **~5分**(次回は DL 50MB が乗る)。
  リハーサル成果物(`-1.2.19` 名の raw/clean/series/temp db)は確認後に削除済(phase1-1.2.19.json だけ記録として残置)。

## サニティ runner ベースライン(2026-09-02 実走・EXIT=0・計~15分)
- 17本の rows: isbn-loss 285(★理由なし4) / solo-truncated 83 / title-eq-author 14 / price-pack 100 / vol0-hidden-first 877 / orphan-new-series 47,631 / year-suffix-dup 67 / canonical-imprint-split 82 / edition-run-split 4 / numeral-variant-split 23 / vol-date-regression 6 / deluxe-label-split 402 / cover-dup 102 / kana-from-other-volume 5。AUTO_FIXED 1,696 / MISSING_HALF 55 / GAP_OTHER 6,332。edition-canonical 異常1(種4 9784834210347 巻4 がどの頁にも無い=canonical上書き疑い)。
- rc≠0 は3本とも「該当あり」の exit 1(isbn-loss / price-pack / edition-canonical)= 検出器の故障ではない。
- ★postflight は **ISBN消失(理由なし4件)で FAIL**: 9784046607188(orc-no-ki-no-shita) / 9784046607232(kono-kekkon-wa-douse-umaku-ikanai) / 9784065449455(arslan-senki) / 9784825101784(oomuroke)。`git log -S` で全4件が **2026-09-02 日次蒸留 commit f2607ed6b「種4-autoの特装版entry11件を退役」**に紐付く=裁定済み削除の記帳漏れ → 週次preflightの消し込みフロー(`isbn-loss-acknowledged.jsonl` に根拠コミット付き記帳)で消える。私の変更由来ではない(今日触った頁は kimetsu-no-yaiba の popularity のみ)。

## 次回(1.2.20、2026-09-17〜22頃公開見込み)の入口
`python scripts/_monthly-distill.py status` → phase1 → 差分report引用 → Go待ち。持ち越し = 1.2.19 頁化の保留54件(`docs/production-diagnostics/torikoboshi-1219-holds.tsv`)未消化。
関連: [[monthly_distill_real_pipeline]] [[distill_2026_08_1219]] [[seed4_auto_wipe_accident]] [[orphan_source_pages_restored]] [[promote_hangs_on_exit_windows]] [[intake_pipeline]]
