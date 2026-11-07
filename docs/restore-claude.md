# C: が壊れた時に Claude(MANGAL の作業環境)を戻す手順

週1回(日曜 4:00)、 `scripts/_backup-self.py run` が **D:\claude-backup** に写している。 枠が2つ(A / B)あり、 交互に上書きする。
新しい方 = `A\backup-meta.json` と `B\backup-meta.json` の `at` が新しい方(`ok: true` のもの)。

## 写してあるもの / 無いもの

| 写してある | 中身 |
|---|---|
| `home\.claude` | 記憶(projects\…\memory)・会話履歴・skill・設定・plugins |
| `home\.claude.json` `home\.gitconfig` | Claude Code の全体設定 / git の名前 |
| `MANGAL` | リポジトリから .git・node_modules・ビルド物・落とし直せる物を除いた全部(manga.v2・SRC 頁・.env 類・起動 bat・.cache の種2 等) |
| `env-snapshot` | pip freeze / 各ツールの版 / タスクスケジューラ一覧 |

| 写していない(戻した後に入れ直す・落とし直す) | 戻し方 |
|---|---|
| Claude Code のログイン鍵(.credentials.json) | `claude` を起動してログインし直す |
| git の中身(.git) | GitHub から clone(下の手順) |
| node_modules / .next / out | `npm ci` / ビルドで作り直す |
| MADB・Wikipedia ダンプ・楽天・AniList のキャッシュ | Claude に頼む(月次蒸留の取込 / `python scripts/_wiki_local.py update` / 各ハーベスト) |
| gh CLI のログイン | `gh auth login` |

## 手順

1. 新しい C: に Windows を入れ、 ユーザ名を前と同じ **chiba shuichi** にする(パス `C:\Users\chiba shuichi\…` が記憶の置き場名に入っているため)。
2. 入れる: Git / Python 3.12 / Node.js 22 / Claude Code(版は `env-snapshot\versions.txt`)。
3. D: を挿して、 新しい方の枠を確かめる(例 `D:\claude-backup\A`)。
4. 私の一式を戻す(PowerShell):
   ```
   robocopy D:\claude-backup\A\home\.claude "$env:USERPROFILE\.claude" /E
   copy D:\claude-backup\A\home\.claude.json $env:USERPROFILE\
   copy D:\claude-backup\A\home\.gitconfig $env:USERPROFILE\
   ```
5. リポジトリを戻す:
   ```
   mkdir "$env:USERPROFILE\code"; cd "$env:USERPROFILE\code"
   git clone https://github.com/shuichi0725-cmyk/MANGAL.git
   cd MANGAL; git checkout claude/manga-database-affiliate-3x0ms
   robocopy D:\claude-backup\A\MANGAL . /E
   git reset --hard origin/claude/manga-database-affiliate-3x0ms   # git の管理物は GitHub の最新に戻す(写しの古い版を消す)。 管理外(manga.v2・.env・.cache)は残る
   ```
6. 部品を入れる: `python -m pip install -r D:\claude-backup\A\env-snapshot\pip-freeze.txt` / `npm ci`
7. `claude` を起動してログイン → MANGAL フォルダで `fable.bat` 等。 記憶・skill はそのまま効く。
8. Claude に「復元の続き」と頼む = 落とし直す物(Wikipedia ダンプ・MADB 等)を Claude が取り直す。

## 確かめ方
- `python scripts/_backup-self.py status` = 最後に写せた日時(8日より古い・失敗なら ★)。 日次蒸留の手順0でも見る。
- D:\claude-backup は**継承を切って 私・SYSTEM・Administrators だけ**(D: 共有の share1 からは開けない)。 APIキー(.env 類)が入っているため。
