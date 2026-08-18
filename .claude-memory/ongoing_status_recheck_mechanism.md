---
name: ongoing-status-recheck-mechanism
description: "連載中→完結の外部権威降格層(2026-08-18適用済4,001頁)。promote恒久機構+BookLive照会seed"
metadata: 
  node_type: memory
  type: project
  originSessionId: cfda7af4-88ad-4470-82ac-6238868c9f0c
  modified: 2026-08-18T11:45:47.508Z
---

# 連載状態の外部権威層 (2026-08-18 ユーザGO・適用済)

発端 = ぎゅわんぶらあ自己中心派(1989完結が連載中表示)。根因 = promoteの非対称:
種3(AI推測)のongoingが一度も降格されなかった。ongoing 11,285→**7,233頁**に是正。

## 機構 (promoteメインループのenrich後、優先順)
1. status-corrections(per-case、最優先・不変)
2. AniList FINISHED/CANCELLED → completed(.cache/anilist-status-map.json、`_gen-anilist-status-map.py`でdumpから再生成)
3. BookLive最終巻証拠(タグ=完結 or 強文言「堂々の完結編」「全N巻」等)→ completed。seed=`data/seeds/status-booklive.jsonl`(git追跡、証拠文言つき)。harvester=`_harvest-booklive-status.py`(試し読みmapのtitle_id×最終巻頁、1.3秒/req)
4. AniList RELEASING → ongoing維持(HxH型長期休載の保護。★BookLive証拠はRELEASINGに勝つ)
5. 機械判定: 最新巻初版が24ヶ月無し → completed(証拠ゼロ層のみ)
- 一方向(降格のみ)・可逆(新刊が出ればbuilderのrecencyでongoingに戻る)
- year_ended = 最新巻初版の年(builderと同じ意味論)

## 実績 2026-08-18
降格4,001頁 = AniList 2,506 / BookLive 368 / stale24 1,127。公開は次の週次。
BookLive照会1,642件中 完結証拠1,243(タグ1,178+強文言65)。AniList×BookLive二重証拠=875件。

## 残
- 保留24件 = `docs/production-diagnostics/ongoing-recheck-hold.tsv`(弱文言「終幕へ」等=人裁定待ち)
- RELEASING保護で残る古参ongoing(2000年代3件=rampage等)= 意図的
- 月次: dump更新後に `_gen-anilist-status-map.py` 再実行。降格カウント急増=signal
- 調査台帳 = `docs/production-diagnostics/ongoing-recheck.tsv`(11,284行、[[intake-manifest-ledger-live]]系)

promote `--only-file <path>`(1行1slug)も今回新設(Windows 32k上限回避)。
