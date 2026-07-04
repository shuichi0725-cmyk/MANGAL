# MANGAL 更新系 呼びかけ早見表 (= skill一覧。2026-07-04 skill化完了)

ユーザ→Claude のトリガー語と、対応する skill / 内容 / 所要。
skill 実体 = `.claude/skills/<name>/SKILL.md`(git追跡。Opus 4.8 等でも同じ手順で運用可)。

| あなたの言い方 | skill | やること | 所要 |
|---|---|---|---|
| **「反映して」** | reflect-targeted | 直した頁だけ本番manga.v2+索引+テスト同期+push(検証ゲート内蔵)。フルpromote禁止 | 数分 |
| **「テスト環境に出して」** | test-deploy | 対象頁を .preview-data へ投入/入替+索引再構築+push(反映15-20分・追いpush禁止) | 数分+待ち |
| **「週次蒸留して」** | weekly-distill | 本番へのフルビルド+R2フルアップ(事前再生成→build~2.5h→差分PUT→疎通確認)。コード変更を本番に出す唯一のルート | ~3-4時間 |
| **「差分反映して」** | diff-deploy | 変更ページだけ部分ビルド→本番R2へ選択PUT+cache purge。**コードドリフト時は自動abort→週次へ** | 数分 |
| **「日次蒸留して」** | daily-distill | NDL当月live発見→差分plan→worksheet→preview新規頁(Layer1ジャンル+Layer2タグ込み) | 数分〜 |
| **「後退蒸留して 〈年〉」** | backward-distill | 過去年をNDL発見→仕分け→掲載ゲート→preview生成(被覆台帳更新) | 年次第 |
| **「月次蒸留して」** | monthly-distill | MADB取込→フルpromote→enrich→AI fill→月次サニティ監査(Phase0確認→**Goサイン必須**) | ~3時間+ |
| **作品名+リンク(Wiki/NDL)を貼る** | percase-fix | per-case是正(イアラ式): 汚染除去/版分離/巻補完/variants。型別seed早見表つき | 1作数分〜 |
| **「新規追加」「新刊入れて」** | new-manga-register | 新規マンガ登録(順番固定: 全巻回収→題→ヨミ→一括→enrich→欠落表)。テスト先行→GO→本番 | 件数次第 |
| **「巻抜け仮想」** | volgap-audit | 残巻抜け算出(~2分)。単巻切り詰め検出(solo-truncated)・巻出力監査も同居 | ~2分 |

## skill でない便利トリガー
| 言い方/操作 | 内容 |
|---|---|
| 本番URL末尾に **#debug** | 本番でも診断チップ(画像なし/巻抜け/コピー等)を表示(localStorage永続)。**#nodebug** で解除 |
| 「月次蒸留して」の Go サイン | 「OK」「進めて」「ゴー」等の明示的肯定のみ有効 |

## 厳守ルール(全skill共通)
- 本番R2への build/sync は「週次蒸留して」以外で自発実行しない
- 価格の静的表示は絶対禁止(動的取得のみ)
- NDL/楽天 live は 1.2-1.3秒/req・429=即中断
- 推測・捏造で埋めない。不明=報告して待つ
- push後のpreview反映は15-20分・追いpush禁止
