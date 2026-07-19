# MANGAL 更新系 呼びかけ早見表 (= skill一覧。2026-07-04 skill化完了)

ユーザ→Claude のトリガー語と、対応する skill / 内容 / 所要。
skill 実体 = `.claude/skills/<name>/SKILL.md`(git追跡。Opus 4.8 等でも同じ手順で運用可)。

| あなたの言い方 | skill | やること | 所要 |
|---|---|---|---|
| **「反映して」** | reflect-targeted | 直した頁だけ本番manga.v2+索引+テスト同期+push(検証ゲート内蔵)。フルpromote禁止 | 数分 |
| **「テスト環境に出して」** | test-deploy | 対象頁を .preview-data へ投入/入替+索引再構築+push(反映15-20分・追いpush禁止) | 数分+待ち |
| **「本番待ちテストに出して」** | prodwait-preview | 前回週次以降の全変更を一括preview投入=次の週次の事前レビュー(`_prodwait-to-preview.py --push`・ドラフト温存・mtime汚染ガード) | 数分+待ち |
| **「本番化して」** | productionize-drafts | 確認済み予約ドラフトをpreorder-pages(恒久)へ昇格+preview解放。週次蒸留で本番公開。R2配信はしない(=週次/差分反映が担う) | 数分 |
| **「週次蒸留して」** | weekly-distill | 本番へのフルビルド+R2フルアップ(事前再生成→build~2.5h→差分PUT→疎通確認)。コード変更を本番に出す唯一のルート | ~3-4時間 |
| **「差分反映して」** | diff-deploy | 変更ページだけ部分ビルド→本番R2へ選択PUT+cache purge。**コードドリフト時は自動abort→週次へ** | 数分 |
| **「日次蒸留して」** | daily-distill | 2本立て=楽天予約ハーベスト(未来・カレンダー供給)+NDL新着回収+ヨミ照合キュー+カレンダー更新 | 数分〜 |
| **「後退蒸留して 〈年〉」** | backward-distill | 過去年をNDL発見→仕分け→掲載ゲート→preview生成(被覆台帳更新) | 年次第 |
| **「月次蒸留して」** | monthly-distill | MADB取込→フルpromote→enrich→AI fill→月次サニティ監査(Phase0確認→**Goサイン必須**) | ~3時間+ |
| **作品名+リンク(Wiki/NDL)を貼る** | percase-fix | per-case是正(イアラ式): 汚染除去/版分離/巻補完/variants。型別seed早見表つき | 1作数分〜 |
| **「新規追加」「新刊入れて」** | new-manga-register | 新規マンガ登録(順番固定: 全巻回収→題→ヨミ→一括→enrich→欠落表)。テスト先行→GO→本番 | 件数次第 |
| **「Koboして/書影補完して/Kobo続けて」** | kobo-covers | Kobo電子版の書影で紙の欠け巻を補完(装丁目視ゲート必須) | 10-20作/回 |
| **「帯混入直して/激マン型見て」** | band-intruder-fix | 少数帯×日付逆行の混入巻をNDL×楽天でスワップ是正 | 数分〜 |
| **「エンリッチして」** | enrich-catch-synopsis | キャッチ(一覧惹句20-40字)と詳細(頁あらすじ60-120字)を全巻紹介文から役割分担生成+ジャンル要素付与 | 100件/batch |
| **「巻説明つくって」「単行本説明つくって」** | volume-desc | 単行本(巻)単位の説明文を楽天itemCaptionから生成→seed純粋追加(表示結線は未定)。**Opus 4.8運転前提** | 100巻/batch |
| **「Wiki蒸留して」** | wiki-distill | Wikipedia書誌(巻別ISBN+日付)で壊れた長期連載をcanonical復元(釣りキチ65巻等で実証・fail-closedゲート) | 10作/回 数分 |
| **「巻抜け仮想」** | volgap-audit | 残巻抜け算出(~2分)。単巻切り詰め検出(solo-truncated)・巻出力監査も同居 | ~2分 |
| **「試し読み拾って」** | tameshiyomi-harvest | BookLiveのtitle_idを魚で収集→tameshiyomi-booklive.jsonl(判断はscript・AIは保留裁定のみ・Sonnet運転前提・--limit100まで) | 100作/回 ~5分 |
| **「ジャンル検品して/Gemini検品」** | gemini-genre-audit | 本番provisionalジャンル・要素(~25k頁)をGeminiブラインド検品→不一致だけ裁定。429まで回す常設アイドルジョブ・試し読みと並走可 | ~500件/日 |
| **「アイドル運転して」/「やめて」** | idle-run | 常設柱(試し読み+Gemini検品連鎖+ヨミ照合+完結判定+素材ハーベスト)を無限ループbackground起動。やめて=成果無駄なく即停止・同語で再開。Sonnet運転前提 | 無期限 |
| **「素材ハーベストして」** | material-harvest | 本番に書かず素材だけ収集(発売日精密化/wiki本文+infobox/賞P166/魚残差)。生成・反映は各既存protocol。Sonnet運転前提 | フェーズ次第 |

## 常時参照系skill(トリガー語でなく状況で発動)
| 状況 | skill | 内容 |
|---|---|---|
| 楽天/NDL/キャッシュを引きたい | external-data-access | **必ず `_lookup.py` から**(レート1.3s内蔵・キャッシュ資産マップ・NDL不在≠不存在) |
| 60秒超のジョブを走らせる | long-job-ops | 生存確認・監視の絞り方・ハング判定・wrangler/シェルの罠 |
| 「表示がおかしい」と言われた | display-bug-triage | 環境特定→キャッシュ→stale生成物→データ実体の順で1往復診断 |
| APIが無い+WebFetchが弾かれるサイト /「TinyFishで」 | tinyfish | `_tinyfish.py fetch/search`(無料枠のみ・search=GET・Agent/Browserは有料=ユーザ承認)。序列=_lookup.py→WebFetch→TinyFish |
| **「魚で調べて」** | tinyfish | **TinyFishだけ**で調査(他ソース使わない) |
| **「魚などで調べて」** | tinyfish | **全ソース調査**(_lookup.py→WebFetch→TinyFishのエスカレーション込み) |
| **「アクセス解析して」** | cf-analytics | `_cf-analytics.py web`(訪問者/人気ページ/国=主役)+`report`(Worker総req/エラー率=クロール込み) |

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

- **ISBNダブリの続き/ISBNダブリ潰して** = skill `isbn-dup-cleanup`(検出→層別→判定→適用→検証。進行状態=memory isbn-dup-cleanup-state)
