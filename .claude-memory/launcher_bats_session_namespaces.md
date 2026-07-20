---
name: launcher-bats-session-namespaces
description: 起動bat3本=モデル名(fable/sonnet/opus)。junctionでセッション名前空間分離(--continue横取り根絶)。旧名c.bat/d.batは廃止
metadata: 
  node_type: memory
  type: project
  originSessionId: ba4cb054-4e74-433e-9a1e-646b94515823
  modified: 2026-07-20T13:50:07.641Z
---

起動バッチ3本の役割とセッション分離 (2026-07-18確立 → 2026-07-19 モデル名リネーム+opus追加 → 2026-07-20 fableもjunction化):

- **fable.bat** (旧c.bat) = `claude --continue --model "fable[1m]"` — メイン作業用。★2026-07-20 junction `MANGAL-fable` で起動に変更(旧=MANGAL直下`%~dp0`)。理由: MANGAL直下で走る opus 等 別モデルのセッションが最新になると `--continue` がそれを掴んでエラー→ウィンドウ即閉じで「立ち上がらない」事故。初回`--continue`失敗時は `if errorlevel 1` で新規セッションにフォールバック(=必ず立ち上がる)。★junction化で fable の旧ログ(MANGAL直下名前空間)は`--continue`直では戻らない→必要なら `claude --resume` で一覧選択(jsonlは消えない)。
- **sonnet.bat** (旧d.bat) = `claude --remote-control --model sonnet` — モバイルアプリ操作用(アイドル運転など)。junction `MANGAL-remote` で起動。
- **opus.bat** (2026-07-19新設) = `claude --continue --model "opus[1m]"` — Opus 4.8/1M。junction `MANGAL-opus` で起動し fable と同時併用可。初回`--continue`失敗時は `if errorlevel 1` で新規セッションにフォールバック(初回セッションは検証時に種付け済)。
- ★3本とも専用junction(MANGAL-fable / MANGAL-opus / MANGAL-remote、いずれもMANGALへのjunction)= **1バッチ=1junction=1名前空間**。別モデルのセッションを`--continue`が掴む事故を根絶。実体は同一repo、memory/skills/CLAUDE.mdもjunctionで共有。
- ★モデル障害と起動障害の切り分け: `claude --model "fable[1m]" -p "OK"` が返れば**モデルは健全**=障害は起動(`--continue`)側。2026-07-20の「fableが立ち上がらない」は後者だった。
- 掴み間違えた時の復旧: `claude --resume`(引数なし)で一覧から選ぶ。旧セッションjsonlは消えない。
- 関連: [[feedback_mobile_permission_hang]] (旧記述のc.bat再開=現fable.bat)。アイドル運転=skill idle-run(Sonnet運転前提)。
