---
name: idle-run
description: アイドル運転して=手すき時間の常設柱(試し読みexpand消化+Gemini検品連鎖+ヨミ照合1パス)をbackground起動。「やめて」で成果を無駄にせず即停止、同じ一言で続きから再開。Sonnet運転前提
---

# アイドル運転 (= トリガー「アイドル運転して」/ 停止「やめて」。2026-07-14 ユーザ設計、07-15 柱を更新)

やることがない時間に回す常設ジョブのセット。**時間指定はしない**: 起動→(勝手に走る)→「やめて」で即停止→
別作業→また「アイドル運転して」で続きから。全ループが逐次保存なので停止の損失は最大でも走行中1バッチ(~5分)。

## 起動 (= ★柱①〜⑤を全部、同時にbackgroundへ。3本で止めない)
```
bash scripts/_idle-tameshiyomi-expand-loop.sh   # ①試し読みexpand消化(無限・バッチごとcommit+push)
python scripts/_gemini-genre-probe.py && python scripts/_gemini-genre-verify.py   # ②Gemini連鎖(429で自然停止)
python scripts/_verify-kana-pending.py --limit 300   # ③ヨミ照合(★1パスのみ=ループ禁止、下記)
python scripts/_completion-judge.py --backlog --limit 300   # ④完結判定backlog(→worksheet記入→--collect→commit、詳細=skill completion-judge)
python scripts/_material-harvest.py wiki-fetch --limit 500  # ⑤素材ハーベスト(在庫切れ後は fish-residue --limit 50、詳細=skill material-harvest)
```
- それぞれ **run_in_background で別タスク**として起動し、**タスクIDを控えて報告**(=「やめて」で使う)。
- ★④⑤は1バッチ終了ごとに**同じコマンドを再起動**して続きを回す(④はworksheet記入→--collectを挟む。⑤はwiki-fetch在庫が尽きたらfish-residueへ)。②③のように自然停止で終わりではない。
- ①は積み残し~1.2万シリーズ(アンカー13,949作は収集済=旧アンカーループは枯れて即終了する)。BookLive HEADのみ=高速。
- ②はquota(~500req/日・JST16時リセット)で~40分で止まるのが正常。
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
現在: ①試し読みexpand消化 ②Gemini検品連鎖(probe→verify) ③NDLヨミ照合(1パス)
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
候補: Kobo書影resume / 楽天キャッシュmiss(B系欠落)のlive照会 — 追加時は「逐次保存・自然停止・冪等再開」の3条件を満たすこと。

## 関連
- 各柱の正本: tameshiyomi-harvest / gemini-genre-audit / daily-distill(手順8=ヨミ照合) / enrich-catch-synopsis(Gemini同定) / material-harvest(素材収集)
