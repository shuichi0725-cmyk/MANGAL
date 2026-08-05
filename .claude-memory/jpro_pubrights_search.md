---
name: jpro-pubrights-search
description: JPRO出版権検索(jpro2.jpo.or.jp)=ログイン不要で叩ける出版社登録の書誌源。題名→紙/電子の全巻ISBN+発行元が一発
metadata: 
  node_type: memory
  type: reference
  originSessionId: ca601f45-de8a-4eda-b8ed-ed44ecdd9447
  modified: 2026-08-05T01:12:48.492Z
---

# JPRO出版権検索 (= 2026-08-05 ユーザ提示で開通。巻抜けの新しい一次級ソース)

**URL**: https://jpro2.jpo.or.jp/limit/pubrights/Index (JPO出版情報登録センター=日本出版インフラセンター)

**何が取れる**: 出版物名(部分一致)or著者名で検索→ **キーコード(ISBN)/出版物名/発行元出版社/出版権** の一覧。媒体=紙(media=0)/電子(media=1)。★出版社が自分で登録する権利DBなので**シリーズの全巻ISBNが揃って出る**(実証=「10年間友達だと思ってた男の子に告白されるお話」で紙1-10全ISBN一発→頁欠落の7巻を即特定・適用)。NDL納本ラグ・楽天在庫切れ非表示の影響を受けない。

**アクセス方法**(ログイン不要・Laravel型):
1. GET Index → cookie + `_token`(hidden)を取得
2. POST 同URL: `_token, media=0, product_id=, title_text=<題>, contributorName=, submit_pubrights_search=検索, torikyo-flag=0`
3. 結果は`<tr>`テーブル(媒体/ebookflag/キーコード/出版物名/発行元出版社/出版権)
- ★このPCのPython urllibは素の証明書検証が通らない(certifi無し)→ 調査時は `ssl.CERT_NONE` で回避した(認証情報を送らない読み取りのみ)。恒久化するならcertifi導入が筋。
- WebFetchはフォーム外形まで・TinyFish無料fetchも初期画面まで(POST不可)。**直POSTが正解**。

**Why:** 巻抜けハントの外部ソース序列に加える価値がある: NDL(納本ラグ/欠落あり)・楽天(在庫切れ非表示)で出ない巻もJPROには出版社登録で載る。著者区分(原著/企画・原案/イラスト等コードA01,B20…)もあり著者役割の突合源候補。

**How to apply:** 巻抜けper-caseで NDL/楽天が空振りしたら JPRO title_text 検索。ISBNが取れたら日付/書影は楽天ISBN直引きで補完([[cover-source-affiliate-only]])。レート配慮=手動per-case規模で使う(大量sweepに使う前にユーザ相談)。

**柱化済(2026-08-05)**: skill jpro-harvest = アイドル運転の柱⑫(Sonnet)。`scripts/_jpro-harvest.py` が巻抜け未解決slug(queue~198)を無判断で全量収集→`data/seeds/jpro-harvest.jsonl`。ONE PIECE=355行が1POSTで返る(ページネーション無し)。適用=「JPRO判定して」(Opus専権・版取り違え判別つき)。
