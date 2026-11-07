---
name: self_backup_weekly
description: 【★】C:が壊れてもClaude(私の作業環境)を戻せるよう週1回 D:\claude-backup へ写す(_backup-self.py・日曜4:00タスク・枠A/B交互・share1から見えないACL)。戻し方=docs/restore-claude.md
metadata:
  type: project
---

2026-11-07 ユーザ「このPCはあなたを動かすのとDドライブを共有して使用するために使っている。Cドライブがアクセス不能になったさいにバックアップから復元できるようにしたい」「週一でよい。復元できるようにしたいのはあなただ。あなたの指示でダウンロードし直せるような物は基本必要ない」。

**仕組み** = `scripts/_backup-self.py`(run / status / install)
- 写し先 `D:\claude-backup\A|B`(古い方・失敗した方を上書き = 直近の成功が常に残る)。 ★D: 全体が共有(Authenticated Users=変更可)なので **claude-backup だけ継承を切り 私・SYSTEM・Administrators に絞る**(.env の API キーが入るため)。 これは [[feedback_no_d_drive]] の例外 = ユーザが求めた「バックアップ倉庫」用途。
- 中身: ~/.claude(記憶・会話履歴・skill・設定。 .credentials.json と一時物は除く)・~/.claude.json・~/.gitconfig・リポジトリ(.git/node_modules/ビルド物/MADB・Wikipedia・楽天・AniList のダウンロード物/*.bak を除く = manga.v2・SRC・.env・起動bat・.cache の種2 db-v2.sqlite 等)・env-snapshot(pip freeze 等)。
- タスクスケジューラ `\MANGAL\ClaudeBackup` = 毎週日曜 4:00・StartWhenAvailable。 D: が外れていたら書かずに失敗を `.cache/backup-status.json` に残す(ほかのドライブは探さない = [[d_drive_external_flaky]])。
- 鮮度確認 = 日次蒸留の手順0b `python scripts/_backup-self.py status`(8日より古い/失敗で ★)。
- 戻し方 = `docs/restore-claude.md`(写し先にも README-restore.md)。 ユーザ名を同じ chiba shuichi にする(記憶の置き場名に入る)→ ~/.claude を戻す → GitHub から clone → 写しを重ねて `git reset --hard origin/…` → pip/npm → claude にログイン。
- 写していない = ログイン鍵・.git・ダウンロード物(Claude に頼んで取り直す)。 楽天キャッシュ(1.2GB)は「取り直せる」扱いで外した(取り直しは数日)。
