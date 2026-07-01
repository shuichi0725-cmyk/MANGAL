---
name: phase2-fill-workflow
description: phase2 = 種3 (series-supplement-v2.yml) の title_kana fill batch loop の運用手順 (= 1 batch あたり 107 entries / read 1400 行 / raw → process → apply → commit)
metadata: 
  node_type: memory
  type: project
  originSessionId: 6146d01a-d071-41e5-9ffa-4568e252bbb1
---

**★状態 (2026-05-30): phase2 = 事実上完了。** 当初 19,658 の null title_kana は前セッションの batch 001-010+ でほぼ消化。 残 title_kana 空 = **18件のみ、 全て外国語版**(仏BD タンタン/Astérix/Franquin・フィンランド語 Puupää・スウェーデン訳 Oda/Akamatsu)で **キーが PUA 文字化けした非掲載残渣**(qid 無し=Wikidata非連結、 本番非掲載)。 日本語フリガナ対象外なので空のまま正当。 genuine な欠落は **バツ＆テリー(qid:Q4022589)1件のみ**で demographic/genres/synopsis/status を直接 Edit で純粋追加 (commit 66c6b02)。 → **batch loop は再 MADB 取込で新規 null が増えた時のみ再起動**。 以下は再起動時の手順。

phase2 = `data/seeds/series-supplement-v2.yml` の null/MISSING title_kana を AI 推定で fill する大量バッチ処理。

**Why:** 19,658 件 (= null + MISSING) を 一度の AI 推論で処理しきれない。 batch (= 107 entries/回) に分割して shell ループで回す。 user binding directive: 「シェルだといくらでもいけるみたいなので500件毎に報告、 日本時間となにかあったら。 2000件は忘れて」 = 完了まで シェル ループ で連続実行 + 500 件毎に commit + push + JST 報告。

**How to apply:**

### 1 batch の手順 (= 107 entries)
1. `data/seeds/_fills/phase2-todo.json` の **上から 1400 行 read** (= ちょうど 107 entries 程度)
2. 107 entries の kana を推定 (= [[phase2-fill-protocol]] = CLAUDE.md の 種3 fill protocol に従う)
3. `.cache/phase2-batch-NNN-raw.json` に dict 形式で書き出し:
   ```json
   { "qid:QXXXX|name:XXX": "カナ ヨミ", ... }
   ```
4. process + apply pipeline:
   ```
   /c/Users/shuic/AppData/Local/Programs/Python/Python312/python.exe scripts/_phase2-process-batch.py --batch NNN --raw .cache/phase2-batch-NNN-raw.json && npx tsx scripts/_apply-fills.ts data/seeds/_fills/phase2-batch-NNN.json
   ```
5. 結果確認: `applied=N, missing=0, overwrites=0, todo: X → Y` で `missing=0 / overwrites=0` 必須 (= 既存 fill 上書き禁止 = 保護策)
6. 500 件 milestone (= 累計 17,500 / 18,000 等) 達成時に commit + push (= JST 時刻入りメッセージ)

### JST 時刻取得
```
/c/Users/shuic/AppData/Local/Programs/Python/Python312/python.exe -c "from datetime import datetime, timezone, timedelta; jst=timezone(timedelta(hours=9)); print('JST', datetime.now(jst).strftime('%Y-%m-%d %H:%M:%S'))"
```
TZ='Asia/Tokyo' date は Windows で不安定なので Python 経由が確実。

### commit pattern
- branch 固定 = `claude/manga-database-affiliate-3x0ms` (= CLAUDE.md 一般 protocol)
- commit 時 push までセット
- メッセージ最後に `[JST YYYY-MM-DD HH:MM:SS]` 入れる

### 再開時のチェック
- `git status` clean 確認
- `phase2-todo.json` の先頭 entry を読んで次の batch を組む (= 上から順次)
- 直近 commit message から累計件数 + batch 番号を取得 (= `git log -1 --oneline`)

文字化け key (= [[phase2-corrupted-keys]]) は raw に含めても apply 時 skip されるので 無害。

関連:
- CLAUDE.md = 種3 fill 表記 protocol (= 数字読み / 外来語 / 当て字 等)
- [[phase2-corrupted-keys]] = todo に残る 2 件の文字化け entry
