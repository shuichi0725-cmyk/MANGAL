---
name: index_lightening_plan
description: 【計画・実装後】本番軽量化=索引2つ(59.7MB)の値スリム化+詳細66kから未使用3フィールドstrip。精密フィールド監査済
metadata: 
  node_type: memory
  type: project
  originSessionId: eead35c9-02b6-4f7c-9201-3923c98dedb6
---

本番配信を軽くする計画（2026-06-22調査・実装は後日GO待ち）。詳細は会話。

## 本番に配信される大物（詳細ページ群を除く）= 索引2つだけ
- `manga-list-index.json` 46.8MB(本番66k) — 一覧/トップ/フィルタ/カード
- `manga-search-index.json` 12.9MB — 検索専用(遅延fetch)
- ★`data/seeds/*`(kobo-harvest51M/series-supplement32M/captions23M等)は**ビルド素材・本番非配信**=数えない。

## ① 詳細66kページから消せる（精密grep監査済=本番UI未参照）
- **genres_rakuten / genres_provisional / note_origin** = 開発・監査用(genres導出の生入力＋AI品質フラグ＋来歴)。本番UIで0参照→**promote出力時にstrip**。ソース(種3/build)には残す([[genre_quality_improvement]]用)。
- ★保持(未使用だが将来必須): **adult_us**(geo成人・[[adult_judgment_architecture]])、**awards**(将来受賞・空はomit)。

## ② 索引の値スリム化（機能は一切落とさない）
カードの実表示=cover/title/status/subtitle/authors名/原作者名/年代/catch。フィルタ=genres/demographic/publisher(s)/magazine/status/anime_adapted/year/score/popularity。ソート=title_kana/year/latest_date/max_edition_volumes/popularity/score。→「詳細に逃がせる表示項目はほぼ無い(カードが意外と多く出す)」。効くのは**値**:
- **cover URL→ISBN化**(全部`thumbnail.image.rakuten…/{ISBN}.jpg?_ex=`定型→クライアント再構築) -4MB
- **authors の kana/role 削除**(カードは`.name`のみ・kanaは検索索引にある) -2〜3MB
- **明示null省略**(optionalキーは空なら出さない=awards等も将来温存) -4〜6MB
- **検索索引の title/title_kana 削除**(一覧索引と重複・slugでjoin) -3.5MB
→ 推定 59.7MB → **約40MB**。

## ★再生成タイミング
索引再生成・detail strip は **Kobo全作harvest完走後**(今やると書影が中途半端)。build script(_build-list-index.py / promote)修正は先行可。

## 未確認(実装前に精査)
genres_anilist(52%・detail page参照1=表示かfallbackか)/ synonyms(日本語ゴミ表示[[display_data_polish_tasks]])。


## 2026-07-02 本番R2向け再点検で発見した構造欠陥(修正済)
- ★**public/の索引=preview専用1400件subset**(next devとPages preview用)を next export が out/ に継承 → そのままR2同期すると**本番の一覧/検索が1400件**になる重大バグ(未然発見)。
- 恒久修正: `_r2-sync.py` が同期前に data/ の本番索引(list25MB/search9.7MB/catch5.8MB)を out/ に**自動上書き+5MB未満abort guard**。public/は触らない(preview壊れる)。
- 実効配信サイズ: list 25MB→gzip 6.0MB / search 9.7MB→gzip 3.6MB(Cloudflare edgeがCT=application/jsonで自動圧縮)。
- ★未実装候補(モバイル初回6MBが重い時): 一覧索引の分割ロード(shard)/初期表示分だけ先行。大工事なので必要になってから。
- 既知pending: worker.js=素通し(adult_us geo出し分け未実装・別タスク)。
