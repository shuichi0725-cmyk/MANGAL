---
name: idle-run
description: アイドル運転して=手すき時間の常設柱(試し読みexpand+ヨミ照合+完結判定+素材ハーベスト+AniList鮮度+巻説明recheck)をbackground起動。Geminiジャンル検品は幻覚多で退役(2026-07-20)。「やめて」で即停止・同語で再開。Sonnet運転前提
---

# アイドル運転 (= トリガー「アイドル運転して」/ 停止「やめて」。2026-07-14 ユーザ設計、07-15 柱を更新)

やることがない時間に回す常設ジョブのセット。**時間指定はしない**: 起動→(勝手に走る)→「やめて」で即停止→
別作業→また「アイドル運転して」で続きから。全ループが逐次保存なので停止の損失は最大でも走行中1バッチ(~5分)。

## 起動 (= ★下記の柱を全部、同時にbackgroundへ。3本で止めない)
```
bash scripts/_idle-tameshiyomi-expand-loop.sh   # ①試し読みexpand消化(★2026-08-29改訂=有限。停止札があれば起動拒否)
# ②Geminiジャンル検品=退役(2026-07-20)。不一致の76%が幻覚テンプレ→常設から外す。下記「退役」参照
python scripts/_verify-kana-pending.py --limit 300   # ③ヨミ照合(★1パスのみ=ループ禁止、下記)
python scripts/_completion-judge.py --backlog --limit 300   # ④完結判定backlog(→worksheet記入→--collect→commit、詳細=skill completion-judge)
python scripts/_material-harvest.py wiki-fetch --limit 500  # ⑤素材ハーベスト(在庫切れ後は fish-residue --limit 50、詳細=skill material-harvest)
python scripts/_anilist-delta.py   # ⑥AniList鮮度維持(直近更新~5,000件回収・~5分で自然停止・★セッション1回のみ)
python scripts/_voldesc-material.py --recheck-nomaterial 300   # ⑦巻説明・材料なし台帳のlive再照会救済(偽陰性~10%回収・冪等・逐次保存・429はbackoff吸収。詳細=skill volume-desc)
python scripts/_kana-digit-harvest.py --limit 30   # ⑧数字kana素材(フリガナに数字が残る~528頁のwiki+楽天live読み収集)
python scripts/_check-recent-ongoing-volumes.py --limit 200   # ⑨続巻逆照合(連載中頁→楽天題検索。★2026-08-05巻抜け教訓4点移植済=剥き題/truncatedプローブ/帯救済/near記録)
python scripts/_placeholder-cover-refresh.py --all   # ⑩仮書影→実物の差し替え(★--all=queueが尽きるまで自走・再起動不要 2026-08-04。詳細=skill placeholder-cover-refresh)
python scripts/_kobo-color-harvest.py --delta   # ⑪カラー版差分(Kobo新着だけ追記・数分で自然停止・詳細=skill color-editions)
```

## ★★ 柱①(BookLive試し読み)は 2026-08-29 に規制事故を起こした = 触る前に必読

無限ループ+8並列で **231万リクエスト**を投げ、BookLive!からアクセス規制を受けた。
現在 **停止札**(`docs/production-diagnostics/BOOKLIVE-BLOCKED.md`)が置いてあり、
ループも本体scriptも**1リクエストも出さずに終了する**。

- **札を消してよいのはユーザが「BookLiveが復帰した」と言った時だけ。** 自分で試し打ちしない。
- 規約(直列2秒/件・1実行1500件・1日5000件・200/404以外は即中断・収穫ゼロ3回で停止)は
  skill **tameshiyomi-harvest** の「BookLiveアクセス規約」が正本。
- BookLive宛も `scripts/_rate_gate.py` の `wait("booklive", 2.0)` を通す
  = 柱を何本並走させても host単位で1本のストリームになる(楽天/NDL/wikiと同じ)。
- ★そもそも**このキューは枯れている**(掃引済み33,080シリーズ / 残36 = 41リクエスト)。
  復帰しても長時間回す仕事は無い。「何時間も回り続けている」のを見たら**それは異常**。

## ★429/冷却の共通ルール (= 2026-07-24 ユーザ指摘で機械化。運転者の判断ゼロ)
- ⑤⑧(wikiホスト)は **script自身が排他ロック+冷却タイマーを持つ**(`scripts/_wiki_host.py`):
  同時起動→後発が即exit(3) / 429→冷却60分をファイルに記録して中断 / 冷却中の再起動→即exit(3)。
  ★wiki 429で「冷却60分中」が出るのは**設計通りの正常動作**(待たずに他の柱へ・次の手すきで自動再開)=異常ではない。
- ★**楽天/NDL/wiki の3ホスト全てが `scripts/_rate_gate.py` でプロセス間グローバル直列化**(2026-07-24追加。 それ以前は
  ⑦voldescと⑧kana-digitが**同じ楽天app-idを並走**し、各1.3sを守っても合算~1.5req/sで即429だった)。
  ゲートは全live呼出の直前で予約制の間隔を掛ける=**何本並走してもhost単位で1本のストリーム**に統合:
  楽天1.3s(`_lookup.rakuten_live`・`_voldesc-material.live_item`)/ NDL1.3s(`_lookup.ndl_live`・③`_verify-kana-pending`)/
  wiki1.2s(⑤`_material-harvest`・⑧`_kana-digit-harvest`)。 運転者の判断は不要(全柱を並走起動してよい)。
  ※wikiは wiki_host(排他ロック+冷却) と _rate_gate(合算頻度の平滑化) の二段=429の発生を減らしつつ、出ても冷却で自然回復。
- 運転者(Sonnet)のルールは1つだけ: **柱が「冷却」「使用中」メッセージで止まったら、待たない・調べない・
  すぐ他の柱を回す**。⑤⑧は次の手すき(≥60分後)に同コマンド再起動するだけ(冷却中ならscriptが勝手に弾く=無害)。
  ★「429が明けるのをずっと待つ」は禁止(2026-07-24実害: 待機で他の柱まで全停止)。
- ★**偽429は恒久修正済**(2026-08-03 ユーザ報告=⑦⑩が偽429で停止): 旧検知が `"429" in str(e)` の
  文字列マッチで、**JSONDecodeErrorの位置表示(「line 1 column 429」等)や瞬断まで実429と誤検知**していた。
  以後は全live系が `HTTPError.code==429` の厳密判定に統一。楽天系柱(⑦⑩)は共通ヘルパ
  `_lookup.rakuten_live_retry` で **429をbackoff(2-45s)自動吸収**し、連続429(実スロットル)だけ中断。
  瞬断/JSON崩れは1件skip(⑦は台帳に残して次回再照会)=**柱は止まらない**。
  運転上の帰結: 「★楽天429が連続(実スロットル)→中断」が出た時だけ本物=次の手すきで再起動。
- それぞれ **run_in_background で別タスク**として起動し、**タスクIDを控えて報告**(=「やめて」で使う)。
- ★④⑤⑦は1バッチ終了ごとに**同じコマンドを再起動**して続きを回す(④はworksheet記入→--collectを挟む。⑤はwiki-fetch在庫が尽きたらfish-residueへ。⑦は台帳が尽きるまで)。③⑥のように自然停止で終わりではない。
- ①は積み残し~1.2万シリーズ(アンカー13,949作は収集済=旧アンカーループは枯れて即終了する)。BookLive HEADのみ=高速。
- ⑦は台帳(no-material.txt)~5,900件を300件/バッチでlive再照会(1.2s/req)。救済分は`.cache/voldesc/recovered.jsonl`に貯まる=**Opusが後で説明生成**(Sonnetは書かない)。全部.cache=commit不要。
- ③は**起動時に1回だけ**(NDL 1.2s/req・429=exit2で自然停止)。確定/不一致はjsonl/TSVへ逐次保存。
  ★ループさせない: 残pendingの大半は「NDL未収載(納本待ち)」でループすると同じISBNを再照会し続けるだけ。
  終了後 `git add data/seeds/rakuten-kana-pending.jsonl docs/production-diagnostics/kana-mismatch.tsv && commit && push`。
- ①③はBookLive/NDL、②はGoogle=**ホストが別なので並走が基本形**。ただし①と③は両方gitにcommitするので
  ③の終了commitは①のバッチcommitと重ならないタイミングで(pushが弾かれたら pull --rebase して再push)。

## 停止 (=「やめて」)
- 控えたタスクIDを **TaskStop で kill**(全部)。commit/jsonl済みの成果は全部残る。
- 停止後に現在地を1行報告: 試し読み=`--stats` / Gemini=`wc -l .cache/gemini-genre/*.jsonl` / ヨミ照合=script末尾の集計行。

## 再開
- また「アイドル運転して」。全ループとも冪等(done集合/dedup/pending状態)なので続きから。

## NEVER / 注意
- ★**Sonnet運転前提**(このskillの起動・停止・報告に判断は不要。上位モデルの長大セッションで回さない)
- 上位モデルが要る作業はここに混ぜない: 検品不一致の裁定(gemini-genre-audit)・試し読み保留の裁定
  (tameshiyomi-harvest)・**ヨミ不一致(kana-mismatch.tsv)の裁定**は**溜まってからまとめて別途依頼**
- ループscriptを同時に2重起動しない(git push競合)。起動前に既存タスクの有無を確認
- ③を無限ループ化しない(上記=NDL未収載の再照会浪費)

## セット構成 (= 将来増やせる)
現在: ①試し読みexpand消化 ③NDLヨミ照合(1パス) ④完結判定 ⑤素材ハーベスト ⑥AniList鮮度維持+アニメ化フラグ差分(後段) ⑦巻説明recheck ⑧数字kana素材 ⑨続巻逆照合 ⑩仮書影差し替え ⑪カラー版差分
(⑫JPROハーベスト=**同日退役** 2026-08-05 ユーザ裁定: 一括収穫→一括判定では偽穴・版取り違えを裁き切れず、
  成果は毎回Opusのper-case検死で出た。以後JPROは**Opusの検死道具**=skill jpro-harvest の per-case流を参照。
  収穫済み198slug分の素材=data/seeds/jpro-harvest.jsonl は温存・再収穫はしない)
⑪**カラー版差分**(=`_kobo-color-harvest.py --delta` 2026-08-03柱化。ユーザ裁定「全部取得+アイドルで差分」):
  Kobo{カラー版,フルカラー}の新着降順を既知(itemNumber)に2ページ連続で当たるまで歩き、新規だけ
  `.cache/kobo-color-raw.jsonl` へ追記(逐次保存・数分で自然停止・③⑥と同じ1パス型=ループ不要)。
  ★収集のみ。照合(build)は**表示復活を伴うのでユーザGO+Opus専権**(skill color-editions の停止注意を参照)。
  全量の引き直し(引数なし・~1-2時間)は月1目安のOpus作業。commit不要(.cache)。
⑩**仮書影→実物の差し替え**(=`_placeholder-cover-refresh.py` 2026-08-02柱化。ユーザ発見「発売前や発売直後に文字の書影が入る」):
  楽天は発売前の本に「著者名+書名を並べただけの画像」を返し、実物が出ると★URL自体が別物に変わる★ため
  引き直さない限り永久に仮のまま。判定は形だけで確実= 本物`{ISBN}_1_9.jpg` / 仮`{ISBN}.gif`。
  本番10,063巻が.gif、うち2025年以降=**1,752巻**が対象(旧作8,300巻は絶版で引いても.gifのまま=既定で除外)。
  ★`--all` で**queueが尽きるまで自走**(2026-08-04 ユーザ要望「途中で止まる」= 運転者のバッチ再起動忘れが原因だった型)。queue枯れ=一巡完了(自然停止)・実スロットル連続のみ中断(次の手すきで同コマンド再開)。
  試走12件で実物7件(約6割)。★**seed(cover-override.jsonl)へ1件ごと追記するだけ**=頁反映は上位モデルの
  「反映して」か週次。**`--build-queue`(索引から再算出)は週次蒸留に組込済(2026-08-12 ユーザ裁定=週1化。手動不要)**。
  ★一巡=終わりではない(2026-08-03周回設計): 実物の出現時期は不定なので、--build-queue が done を
  自動rotateし「まだ仮のまま」も次周回で全部再照会する(seed在籍分のみ除外)。
⑨**続巻逆照合**(=`_check-recent-ongoing-volumes.py` 2026-07-29柱化。ユーザ発見「日次蒸留の穴」の恒久対策):
  日次蒸留(前方=未来窓の増加分のみ)が構造的に拾えない続巻(初回baseline切り捨て/発売済み/表記揺れ)を、
  **逆方向**(連載中・休載の全~11k頁→その題で楽天を引く)で月次一巡して回収する後方安全網。
  初回実証(2026-07-28)= 日次73巻/窓 に対し逆照合1,335巻登録。ゲート4種(コミックsize/same_series/セット合本除外/著者一致)内蔵。
  ★2026-08-05 巻抜けハント教訓4点を移植: ①剥き題フォールバック(怪物(けもの)事変型=生題0件を「異常なし」と誤記帳する穴)
  ②truncated(30件枠)時の「題+巻数」末尾プローブ(SERVAMP分冊版ノイズ型) ③ISBN帯一致なら size=単行本/著者不一致も救済
  (B6判・作画交代型。queueに bands 必須=--build-queueで付与) ④弾いた候補を near として記録(fail-visible)。
  ★near は登録しない=Opusが `_zokkan-register.py` 運用時に眺めてゲート誤爆を検死する材料。
  `--limit 200`(~4.5分)を1バッチに再起動で続き=④⑤⑦と同型。queue枯れ=一巡完了(自然停止)。
  **月1で `--build-queue`**(queueを本番索引から再算出+前周回結果を .cache/zokkan-cycles/ へrotate)=これはOpus作業。
  ★収集のみ(trail/gapを.cacheに貯める)。**登録= `_zokkan-register.py` で上位モデル専権**(既登録/巻番号/日付ゲート
  →種4純粋追加→reflectチャンク反映。gapは登録せずper-case行き=under-merge型が混ざるため)。楽天レートは_lookupのgateが自衛。
⑧**数字kana素材ハーベスト**(=`_kana-digit-harvest.py` 2026-07-23新設。フリガナに数字/エンティティが残る残置頁の
  読み素材を wiki記事冒頭よみ+楽天titleKana live から収集。`--limit 30`を1バッチとして再起動で続き=④⑤⑦と同型。
  queueが古びたら `--build-queue` で索引から再算出(冪等)。★収集のみ=`found.jsonl`への貯めまで。
  **裁定・furigana-corrections.yml適用は上位モデル専権**(検証器v2+当て字手動裁定=2026-07-23の型)。
  全部.cache=commit不要。⑤との同ホスト排他・429冷却は script が自衛(上の共通ルール参照)=起動順を考えなくてよい。
⑦**巻説明・材料なし台帳の再照会救済**(=skill volume-desc 2026-07-20新設。`--recheck-nomaterial 300`):
  `--local-only`bulkがローカル harvest 履歴(全楽天でない)に無い巻を「材料なし」と恒久記録した偽陰性(実測10%)を
  live再照会で拾い直す。captionが在れば`captions-cache.jsonl`+`recovered.jsonl`に回収し台帳から除去。
  冪等(残る分だけ)・1件ごと保存・1.2s/req・429即中断。救済分の**説明生成はOpus**(Sonnetは材料回収まで)。全部.cache=commit不要。
⑥**AniList鮮度維持**(=`_anilist-delta.py` 2026-07-18新設。updatedAt降順でカーソルまで回収=ローリング再同期。
  ★収集のみ=deltaは.cacheに貯まるだけ。dumpへの`--merge`と enrichマップ再生成は蒸留時のOpus作業=アイドルでやらない。
  ③同様の自然停止型・セッション1回でよい[cap5,000/回])
  ★⑥後段=**アニメ化フラグ差分**(=`_anime-flag-delta.py` 2026-08-11新設。ユーザ指摘「anime_adaptedが初回から更新されていない」の恒久対策):
  ⑥完走後に `python scripts/_anime-flag-delta.py` → dump+deltaのrelations(ADAPTATION×ANIME)を再計算し
  enrichマップへ anime:true をパッチ+未フラグ頁を `.cache/anime-flag-worklist.txt` に列挙。
  worklistが出たら `_reflect-targeted.py --only <カンマ結合> --push -m "アニメ化フラグ差分適用N頁"` で適用
  (多い時は~400頁/バッチに分割=コマンド行長対策)。判定は機械的(検証済みリンク×明示ADAPTATION関係)=Sonnet適用可。
  ★false化はしない(頁true・dump無の逆方向は報告のみ=実写誤フラグ/AniList関係欠落の混在層)。初回2026-08-11: 821頁適用。
④**完結判定backlogスイープ**(=skill completion-judge。`--backlog --limit 300`→worksheet記入(明示文言のみtrue)→`--collect`→commit。
  ②③と違い記入判断があるが「captionに完結の引用があるか」だけ=Sonnet安全。適用(--apply)は絶対にやらない=Opus+専権)。
⑤**素材ハーベスト**(=skill material-harvest 2026-07-17新設。本番に書かず素材収集のみ):
  `python scripts/_material-harvest.py wiki-fetch --limit 500`(主食=wiki本文+infobox。在庫~3.5k)
  → 在庫が切れたら `fish-residue --limit 50`(★.envのTINYFISH_API_KEY必須。無ければskipして報告)。
  triage/dates-local/wiki-link/awards は素材が古くなった時だけ(週1目安)。全cmd冪等・逐次保存。
  ★wiki-fetchの停止メッセージで振る舞いを変える(2026-07-18改訂: 429/503は script が自動バックオフ60→120→240s):
  「冷却待ち」で止まった=1時間空けて同コマンド再起動 / 「連続エラー5」で止まった=そのまま再起動(壊れ記事skipで進む)/
  正常終了(今回N件)=即再起動で次バッチ。いずれも done集合で続きから=判断不要。
  ★wiki-fetch は ③(NDL)や①(BookLive)とホスト別=並走可。commitは素材がcache置きなので不要
  (date seedのみ `git add data/seeds/release-date-fill.jsonl` を終了時に1回)。
退役: 旧①アンカー収集ループ(`_idle-tameshiyomi-loop.sh`)=2026-07-15対象枯れ(queue空なら即終了するので起動しても無害)。
★**②Geminiジャンル検品=2026-07-20退役**(ユーザ裁定+Opus検証): 不一致514の**76%(391件)が幻覚テンプレート**
  (「近未来SFアクション」「女子高生×教師の学園ラブコメ」を無関係な題に量産)。使えたのは形式判定(essay/4コマ86件=構造的)だけで
  ストーリージャンルの判断は信用できない=常設柱から外す。scriptは残す(genre:other新バッチ等の**個別依頼時のみ**手動起動。
  採用は必ず3ゲート+Web裏取り=鵜呑み禁止 [[method_ai_generate_plus_webverify]] [[feedback_accuracy_is_the_goal]])。
  既裁定の適用86/回付37は週次で本番反映済み予定。保留391はGemini置換せず据置(現行の題名推測provisionalのまま)。
候補: Kobo書影resume / 楽天キャッシュmiss(B系欠落)のlive照会 — 追加時は「逐次保存・自然停止・冪等再開」の3条件を満たすこと。

## 関連
- 各柱の正本: tameshiyomi-harvest / gemini-genre-audit / daily-distill(手順8=ヨミ照合) / enrich-catch-synopsis(Gemini同定) / material-harvest(素材収集)
