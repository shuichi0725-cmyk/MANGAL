---
name: idle-run
description: アイドル運転して=手すき時間の常設2本柱(Gemini検品連鎖+試し読みharvest)を無限ループでbackground起動。「やめて」で成果を無駄にせず即停止、同じ一言で続きから再開。Sonnet運転前提
---

# アイドル運転 (= トリガー「アイドル運転して」/ 停止「やめて」。2026-07-14 ユーザ設計)

やることがない時間に回す常設ジョブのセット。**時間指定はしない**: 起動→(勝手に走る)→「やめて」で即停止→
別作業→また「アイドル運転して」で続きから。全ループが逐次保存なので停止の損失は最大でも走行中1バッチ(~5分)。

## 起動 (= 2本を同時にbackgroundへ)
```
bash scripts/_idle-tameshiyomi-loop.sh          # ①試し読み(無限・バッチごとcommit+push)
python scripts/_gemini-genre-probe.py && python scripts/_gemini-genre-verify.py   # ②Gemini連鎖(429で自然停止)
```
- それぞれ **run_in_background で別タスク**として起動し、**タスクIDを控えて報告**(=「やめて」で使う)。
- ②はquota(~500req/日・JST16時リセット)で~40分で止まるのが正常。①は対象枯れ/連続エラーまで走る。
- 2本は別ホスト(Google API / BookLive+TinyFish)なので**干渉ゼロ・並走が基本形**。
- ★起動時に直近の Deploy Preview run(GitHub Actions API・無認証)のconclusionを1回見て、
  failureならユーザに一言報告(デプロイ失敗の見逃し防止=2026-07-13の実害から)。

## 停止 (=「やめて」)
- 控えたタスクIDを **TaskStop で kill**(2本とも)。commit/jsonl済みの成果は全部残る。
- 停止後に現在地を1行報告: 試し読み=`--stats` / Gemini=`wc -l .cache/gemini-genre/*.jsonl`。

## 再開
- また「アイドル運転して」。両ループとも冪等(done集合/dedup)なので続きから。

## NEVER / 注意
- ★**Sonnet運転前提**(このskillの起動・停止・報告に判断は不要。上位モデルの長大セッションで回さない)
- 上位モデルが要る作業はここに混ぜない: 検品不一致の裁定(gemini-genre-audit)・試し読み保留の裁定
  (tameshiyomi-harvest)は**溜まってからまとめて別途依頼**
- ループscriptを同時に2重起動しない(git push競合)。起動前に既存タスクの有無を確認

## セット構成 (= 将来増やせる)
現在: ①試し読みharvest ②Gemini検品連鎖(probe→verify)。
候補: Kobo書影resume / NDL照合キュー消化 — 追加時は「逐次保存・自然停止・冪等再開」の3条件を満たすこと。

## 関連
- 各柱の正本: tameshiyomi-harvest / gemini-genre-audit / enrich-catch-synopsis(Gemini同定)
