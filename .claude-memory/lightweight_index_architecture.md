---
name: lightweight_index_architecture
description: 一覧/検索を軽量索引2分割+クライアント遅延ロード化(2026-06-21実装)。SSRで65k送らない。生成=_build-list-index.py、プレビューはpushで自動デプロイ
metadata: 
  node_type: memory
  type: project
  originSessionId: eead35c9-02b6-4f7c-9201-3923c98dedb6
---

★トップ/一覧が全DBをpropsで送る問題([[hosting_worker_r2_architecture]])を、**軽量索引2分割+クライアント遅延ロード**で解消(2026-06-21実装・プレビュー稼働確認)。

## 2分割(仕様=app/list/page.tsxコメント2026-06-13裁定に準拠)
- **一覧索引** `manga-list-index.json` = 表示用slim(slug/題/かな/cover事前計算/年/状態/著者/ジャンル/総巻数/最大版巻数/最新刊月/popularity等)。full65kで49MB/gz9.3MB。
- **検索索引** `manga-search-index.json` = 検索専用(slug/題/かな/romaji/別名alt/人物名au)。13.5MB/gz4MB。**検索ボックス入力時だけ**fetch(既定ブラウズは読まない)。
- 検索専用field(title_romaji/alternative_titles/credits)は一覧索引から除外し検索索引へ。

## 実装の要点
- 生成 `scripts/_build-list-index.py [src_dir] [out_dir]`(引数: 既定 data/manga.v2→data/。プレビュー= `.preview-data/manga public`)。**manga.v2を直読み**(data/mangaはスタブ)。masterはdict形式={key:{name}}でload。~5分(66k yml)。
- `lib/schema.ts`: `MangaListItem`/`MangaSearchItem`/`ListBundle`型。
- `lib/loadData.ts`: `loadMangaListIndex()`/`loadMasters()`/`loadArtBooks()`/`loadListBundle()`追加。`loadAllManga`(full)は詳細ページ用に温存。
- `lib/useMangaIndex.ts`: `useMangaIndex()`(一覧・常時) / `useSearchIndex(enabled)`(検索時のみ)。module cacheで全ページ共有。
- `lib/filters.ts`: `matchText`はMangaSearchItem化、`searchMatches(q,idx)→Set<slug>`、`applyFilters(items,state,matchedSlugs)`でAND合成。
- browse/list=manga空のpropsでSSR(247KB)→クライアントfetch。genre=サーバsubset描画(loadListBundle)。

## 配置(2系統で別物)
- **本番full索引(49MB)** = gitignore。**R2にアップ**(別ファイル配信・CDN/キャッシュ可)。
- **プレビュー索引(491件340KB)** = `.preview-data`から生成し **public/ ＋ .preview-data/ 両方にforce-add commit**(publicはgitignoreだがforce)。public=クライアントfetch用、.preview-data=genreサーバ描画用(MANGAL_DATA_DIR=.preview-data)。
- ★**プレビュー(mangal-preview.pages.dev)はgit pushで自動再デプロイ**(Cloudflare Pages git連携)。索引もpushすれば反映。

## 残(本番化)
- full索引生成を蒸留パイプラインに組込(promote後再生成)。
- R2デプロイ時にfull索引2本をアップ。
- 別件: loadAllManga(詳細/home)が読むdata/mangaがスタブ→manga.v2へ向ける本番対処。

## ★軽量化v2(2026-06-26実装・CI通過): 配列化+cover slim+catch分離
索引を **`{f:フィールド順, d:値配列[]}` の配列形式**に=キー名の65,980回重複を排除。読込側が**デコード層**({f,d}→オブジェクト復元)になるので **コンポーネント無改修**(m.title等そのまま)。
- ★**デコードは client＋server 両方に要る**: `useMangaIndex`(client一覧)/`useSearchIndex`(client検索)/`loadMangaListIndex`(server=genre等のSSG)。Step1でserver側(`loadData.loadMangaListIndex`)を見落とし→ /browseでなく**SSGのloadMangaListIndex consumer**がbuild失敗(a2769a586)→loadData修正(d39b48d9f)で解決。**配列化したら両側デコード必須**。
- **cover軽量化** = `lib/coverSlim.ts` `fullCover()`。楽天サムネの共通prefix(`...@0_mall/`)+default suffix(`?_ex=200x200`)を索引から剥がし可変部のみ保存("book/cabinet/.../x.jpg")。デコードで復元。例外(300x300/非楽天)はhttpで始まるfull URLのまま。
- **catch分離** = `manga-catch-index.json`(slug→catch・26,257件)。一覧索引から外し**遅延ロード→merge**(useMangaIndexがcatch listener、loadMangaListIndexはbuild時merge)。カードのキャッチは維持(一瞬遅れて出る)。catchは60%空。
- ★ローカル`next build`の「a[d] is not a function / Could not find /_error」は**.next古いキャッシュの偽陽性**(CIフレッシュは通る)。鵜呑みにせずCI(REST API)で確認。
- 結果: **一覧索引(常時) 51.1→26.1MB(-49%)** / 検索索引(遅延) 13.7→10.1MB / catch(遅延) 5.9MB。
- 未実施(B): 検索索引のtitle/title_kana重複削除(一覧索引からslug join・-4MB)=matchText改修要・検索コアなので保留。awards等は消さず空省略(将来使う・[[index_lightening_plan]])。
