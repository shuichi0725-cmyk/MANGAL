---
name: idle-run
description: アイドル運転して=手すき時間の常設柱(試し読みexpand+ヨミ照合+完結判定+素材ハーベスト+AniList鮮度+巻説明recheck)をbackground起動。Geminiジャンル検品は幻覚多で退役(2026-07-20)。「やめて」で即停止・同語で再開。Sonnet運転前提
---

# アイドル運転 (= トリガー「アイドル運転して」/ 停止「やめて」。2026-07-14 ユーザ設計、07-15 柱を更新)

やることがない時間に回す常設ジョブのセット。**時間指定はしない**: 起動→(勝手に走る)→「やめて」で即停止→
別作業→また「アイドル運転して」で続きから。全ループが逐次保存なので停止の損失は最大でも走行中1バッチ(~5分)。

## 起動 (= ★下記の柱を全部、同時にbackgroundへ。3本で止めない)
```
bash scripts/_idle-tameshiyomi-expand-loop.sh   # ①試し読みexpand消化(無限・バッチごとcommit+push)
# ②Geminiジャンル検品=退役(2026-07-20)。不一致の76%が幻覚テンプレ→常設から外す。下記「退役」参照
python scripts/_verify-kana-pending.py --limit 300   # ③ヨミ照合(★1パスのみ=ループ禁止、下記)
python scripts/_completion-judge.py --backlog --limit 300   # ④完結判定backlog(→worksheet記入→--collect→commit、詳細=skill completion-judge)
python scripts/_material-harvest.py wiki-fetch --limit 500  # ⑤素材ハーベスト(在庫切れ後は fish-residue --limit 50、詳細=skill material-harvest)
python scripts/_anilist-delta.py   # ⑥AniList鮮度維持(直近更新~5,000件回収・~5分で自然停止・★セッション1回のみ)
python scripts/_voldesc-material.py --recheck-nomaterial 300   # ⑦巻説明・材料なし台帳のlive再照会救済(偽陰性~10%回収・冪等・逐次保存・429中断。詳細=skill volume-desc)
python scripts/_kana-digit-harvest.py --limit 30   # ⑧数字kana素材(フリガナに数字が残る~528頁のwiki+楽天live読み収集)
```

## ★429/冷却の共通ルール (= 2026-07-24 ユーザ指摘で機械化。運転者の判断ゼロ)
- ⑤⑧(wikiホスト)は **script自身が排他ロック+冷却タイマーを持つ**(`scripts/_wiki_host.py`):
  同時起動→後発が即exit(3) / 429→冷却60分をファイルに記録して中断 / 冷却中の再起動→即exit(3)。
- ★**楽天/NDLホストは `scripts/_rate_gate.py` でプロセス間グローバル直列化**(2026-07-24追加。 それ以前は
  ⑦voldescと⑧kana-digitが**同じ楽天app-idを並走**し、各1.3sを守っても合算~1.5req/sで即429だった)。
  ゲートは全楽天/NDL呼出(`_lookup.rakuten_live`/`ndl_live`・`_voldesc-material.live_item`)の直前で予約制の
  1.3s間隔を掛ける=**何本並走してもhost単位で1本の1.3sストリーム**に統合。 運転者の判断は不要(並走起動してよい)。
- 運転者(Sonnet)のルールは1つだけ: **柱が「冷却」「使用中」メッセージで止まったら、待たない・調べない・
  すぐ他の柱を回す**。⑤⑧は次の手すき(≥60分後)に同コマンド再起動するだけ(冷却中ならscriptが勝手に弾く=無害)。
  ★「429が明けるのをずっと待つ」は禁止(2026-07-24実害: 待機で他の柱まで全停止)。
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
現在: ①試し読みexpand消化 ③NDLヨミ照合(1パス) ④完結判定 ⑤素材ハーベスト ⑥AniList鮮度維持 ⑦巻説明recheck ⑧数字kana素材
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
