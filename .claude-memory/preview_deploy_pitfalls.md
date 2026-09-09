---
name: preview_deploy_pitfalls
description: 【事実】preview反映15-20分/追いpushでビルドcancel等の実測。運用のやり方は skill test-deploy / display-bug-triage が正
metadata:
  node_type: memory
  type: project
---

★やり方の正 = **skill test-deploy**(投入手順) / **skill display-bug-triage**(表示不具合の切り分け順)。

## 実測事実(skillの根拠)
- mangal-preview反映=push後15-20分。連投すると前ビルドがcancelされ「変わらない」ように見える。
- 確認はActions REST API。一覧=/browse(HomeClient)・ホーム=home-design-11。grid item は min-w-0 でヘッダーズレ封鎖済。
- previewの索引はsubset=カレンダー等の照合失敗は正常。

## ★規模差 = テスト環境は「速度」「キャッシュ挙動」の代理にならない (2026-09-09 実測)

| 索引(圧縮後) | テスト | 本番 | 倍率 |
|---|---|---|---|
| manga-list-index.json | 0.28MB | 5.78MB | 21倍 |
| manga-catch-index.json | 0.14MB | 2.77MB | 20倍 |
| manga-alt-index.json | 0.08MB | 1.29MB | 17倍 |
| **/browse の合計** | **0.50MB** | **9.85MB** | **約20倍** |

preview は3,000頁サブセット(`de6abfe7d`)なので索引が20分の1。**索引到着待ちの窓がほぼ0秒**になり、
「読み込み中に見える」「先に検索すると結果が揃わない」類は**原理的に再現しない**。
★だから「テストで問題なかった」と「本番で遅い」は**両立する**。テスト緑は機能の正しさの証拠であって、
速度・キャッシュ挙動の証拠ではない([[feedback_absence_needs_verification]])。
★実機の数字を採る診断表示は `app/HomeClient.tsx` にあるが **`isPreview` ガードで本番では出ない** =
本番の実測が採れない状態。本番で詰める必要が出たら `?diag=1` 等で出せるようにするのが先。


## ★容量の天井 = Cloudflare Pages のファイル数(2026-09-06 実測+公式)

preview は本番(Workers+R2)と違い **Cloudflare Pages**(`wrangler pages deploy out`)。
- **無料プラン 20,000ファイル/サイト**(有料 100,000。1ファイル25MiB)。
- ★「Pagesビルドは20分でタイムアウト」は**無関係**= うちは GitHub Actions で焼いて上げるだけ。
- 実測: **漫画1頁 = 2ファイル**(`.html` + `.txt`=RSCペイロード)。漫画0頁時の固定分が **約4,200〜5,000**。
- → 3,000頁≒11,000(枠の55%) / 5,000頁≒15,000 / **無料枠の天井は約7,000頁**。
- ★**本番69,242頁は約138,500ファイルで有料枠でも Pages に入らない**(= 本番が Workers+R2 な理由と整合)。
- ★頁を増やしても**ファセットは本番に届かない**: 無作為7,000頁でも出版社298社(本番793)。
  出版社リストの長さ等は preview では判断不能=本番で見るしかない。

## ★セット入替時に再生成する3点(2026-09-06。前回1つ忘れた)

1. `python scripts/_build-list-index.py .preview-data/manga .preview-data`
2. ★`python scripts/_gen-titles-pages.py`(引数なしで data と .preview-data の両方を作る)
   = 忘れると `/titles` が旧セット時代の題名を並べ、存在しない頁へリンクする(実際982頁時代の702頁分が残っていた)
3. `rm -rf public/calendar && python scripts/_build-calendar.py .preview-data/manga public/calendar <当月>`
   = ★**古い月を消してから**。ビルダーは上書きのみで消さないので、旧セットの月ファイルが死にリンクとして残る。
   本番は `_r2-sync.py` が `data/calendar` で out/calendar を丸ごと差し替えるので不影響。

## 2026-07-03 stale生成物クラスの教訓(カレンダー)
- public/calendar(6/26製)がslug改名後も残置→①launch表示が別作品に化ける(1968-08のK幽霊=実体はこんにちは先生) ②一覧が生slug表示 ③current月が古い。
- 恒久策: 生成物(public/calendar・public/data/*-stock.json等)は週次/月次蒸留で必ず再生成(`_build-calendar.py`+`_gen-corner-stocks.py`+`_gen-corner-auto.py`)。発売日カレンダーは全期間化済(release 832ヶ月・月戻り可)。カレンダーは title 埋め込み式に変更済(索引join非依存)。

## ★GitHub Actions が success でも、直後の fetch は旧HTMLを掴むことがある(2026-09-07 実踏)
workflow の `conclusion=success` を待ってすぐ curl したら、シェルの新クラスが 0 件・旧器が残って見えた。
数十秒後に取り直したら全部正しかった。**success = Pages のエッジ反映完了ではない**。
検証で「入っていないはず無いのに入っていない」時は、**まず取り直す**(コードを疑う前に)。

## ★人気順 上位200頁セットの作り方(2026-09-07 再現手順)
本番一覧索引 `data/manga-list-index.json` を popularity→score→year の降順(= `lib/filters.ts` の
`sortItems("popularity")` と同規則)で並べ上位200件。**公開slug→SRC stem の逆引き**
(`data/seeds/slug-overrides.yml` の `overrides:{SRC:{slug:公開}}` を反転)を必ず通す=改名頁を落とさない。
実測: 200/200・人気度 330,034〜28,425。
★抜き取り確認でURLを組む時は **ファイル名(SRC stem)でなく yml の `slug`**(例 danjonmeshi → /manga/dungeon-meshi)。

