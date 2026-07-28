---
name: launcher-bats-session-namespaces
description: 起動bat3本=モデル別resume方式+RC自動接続(2026-07-20全面改修)。junction名前空間分離はclaudeのrealpath化で廃止
metadata: 
  node_type: memory
  type: project
  originSessionId: e65fec7d-934a-44f5-8087-f90ac21cce9c
  modified: 2026-07-28T01:05:02.471Z
---

起動バッチ3本 (2026-07-18 junction方式確立 → **2026-07-20 モデル別resume方式に全面改修**):

- **共通の仕組み**: `scripts/_session-latest.py <fable|opus|sonnet>` が project dir の全セッションjsonl末尾を見て「最後のassistantメッセージが該当モデル系列」の最新セッションUUIDを返す → bat が `claude --resume <UUID> --remote-control <名前> --model X --dangerously-skip-permissions` で起動 = **前回ログ復元+起動時から/rc自動接続**。UUID無し/resume失敗(errorlevel 1)は新規セッションにフォールバック(=必ず立ち上がる)。
- **fable.bat** = メイン作業用 (fable[1m])。**opus.bat** = Opus 4.8/1M 併用。**sonnet.bat** = 別窓start(モバイルRC・アイドル運転用、sonnet)。
- ★**junction方式(MANGAL-fable/opus/remote)は廃止・削除済** (2026-07-20判明): 現行claudeは **cwdをrealpath解決**するため、junctionから起動しても project dir は実パス(`C--Users-chiba-shuichi-code-MANGAL`)になり名前空間が分離されない。旧`--continue`は別モデルの最新セッションを掴んでエラー→「立ち上がらない」事故の根因だった。
- ★モデル障害と起動障害の切り分け: `claude --model "fable[1m]" -p "OK"` が返れば**モデルは健全**=障害は起動側。
- ★検証済み事実: `--resume`+`--remote-control`は併用可 / resume対象無しは exit 1(フォールバック発火) / `-p`セッションもproject dirに永続化される(テスト時はゴミセッションを消すこと)。
- 掴み間違えた時の復旧: `claude --resume`(引数なし)で一覧から選ぶ。旧セッションjsonlは消えない。
- ★**2026-07-28 圧縮回避改修**(ユーザ要望「起動時の勝手な圧縮をやめて」): `_session-latest.py` が前回セッションの文脈使用率を末尾assistant行のusageから概算し、**75%超なら resume せず新規起動**(=resume直後のauto-compact 2連発を根絶)。閾値=env `CLAUDE_RESUME_MAX_PCT`(0=常に新規/100=常にresume)。文脈窓: fable/opus=[1m]で1M・sonnet=200k。★usage拾いはregexでなく**行単位json parse+sidechain除外**(regexは入れ子objectで二重加算・sidechainでモデル系列誤判定の2バグ=実踏)。
- ★**log.bat <fable|opus|sonnet> [N個前]** (2026-07-28新設): /clear で claude が画面ログごと消す問題(本体挙動=bat側で防げない)への対策。セッションjsonl→`scripts/_session-log.py`が会話テキストに起こし notepad で開く。**/clear直後に「消えた方」を見るのは `log fable 1`**(最新=clear後の新セッションのため)。
- ★**2026-07-28b 選定順の恒久修正**(「三つとも直近ログを読まなくなった」実害): 旧実装の**mtime順は「誤って開いただけ」でも最新化する**ため、一度旧セッションを掴むと以後ずっと旧を選び続ける自己強化バグ(07-28朝、3窓全部が一世代前のログに接続)。修正= `candidates()` が**「最後の本線assistant発言のtimestamp」(会話の実時刻)順**で選定。ほか2点: 末尾`<synthetic>`(APIエラー擬似応答)でもファイルを捨てず遡る(旧=セッション孤児化)/tail読みOSErrorは0.3s×3 retry(窓閉じ直後のロック)。`_session-log.py`の「N個前」も同じ`candidates()`順。
- 関連: [[feedback_mobile_permission_hang]]。アイドル運転=skill idle-run(Sonnet運転前提)。
