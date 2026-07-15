---
name: idle-run
description: アイドル運転して=手すき時間の常設柱(試し読みexpand消化+Gemini検品連鎖+ヨミ照合1パス)をbackground起動。「やめて」で成果を無駄にせず即停止、同じ一言で続きから再開。Sonnet運転前提
---

# アイドル運転 (= トリガー「アイドル運転して」/ 停止「やめて」。2026-07-14 ユーザ設計、07-15 柱を更新)

やることがない時間に回す常設ジョブのセット。**時間指定はしない**: 起動→(勝手に走る)→「やめて」で即停止→
別作業→また「アイドル運転して」で続きから。全ループが逐次保存なので停止の損失は最大でも走行中1バッチ(~5分)。

## 起動 (= 柱を同時にbackgroundへ)
```
bash scripts/_idle-tameshiyomi-expand-loop.sh   # ①試し読みexpand消化(無限・バッチごとcommit+push)
python scripts/_gemini-genre-probe.py && python scripts/_gemini-genre-verify.py   # ②Gemini連鎖(429で自然停止)
python scripts/_verify-kana-pending.py --limit 300   # ③ヨミ照合(★1パスのみ=ループ禁止、下記)
```
- それぞれ **run_in_background で別タスク**として起動し、**タスクIDを控えて報告**(=「やめて」で使う)。
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
現在: ①試し読みexpand消化 ②Gemini検品連鎖(probe→verify) ③NDLヨミ照合(1パス)。
退役: 旧①アンカー収集ループ(`_idle-tameshiyomi-loop.sh`)=2026-07-15対象枯れ(queue空なら即終了するので起動しても無害)。
候補: Kobo書影resume / 楽天キャッシュmiss(B系欠落)のlive照会 — 追加時は「逐次保存・自然停止・冪等再開」の3条件を満たすこと。

## 関連
- 各柱の正本: tameshiyomi-harvest / gemini-genre-audit / daily-distill(手順8=ヨミ照合) / enrich-catch-synopsis(Gemini同定)
