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

## ★検索v2+索引v3(2026-07-14 会議決定・実装済)
- **検索専用索引を廃止し一覧索引を共有**: `lib/clientSearch.ts` searchSlugs=初回1回だけhaystack前計算→includes照合。2段(①題名系title/kana/subtitle+かな→ローマ字形 ②著者)+③別名=`manga-alt-index.json`(1.96MB遅延fetch)。逐次絞り込み(①ヒットのみ再利用)。romaji列廃止=クエリ側romaji→かな変換+collapseVowels(wanpi-su/wanpiisu同一視)。旧検索索引は移行期のみ併出(TODO 2026-08撤去)。
- **authors列パック**: `"name\tkana"`のタブ区切り文字列(role廃止)。5フラグ列→**flビットフィールド**(1=solo_nonfirst/2=vol_gap/4=cover_gap/8=_anthology/16=_slugfix)。cover slim拡張=任意`?_ex=NxN`も剥ぐ(復元は常に200x200)。**headファイル**`manga-list-head.json`(人気上位200行87KB)=先行表示→full差替。alt索引はalternative_titles+synonyms+**巻title_displayの純副題**(ソーサリアン型)を拾う。一覧22.0MB。
- ★**消費者ルール(ドリフト封じ・実害で確立)**: 索引を読む側は必ず共通デコーダ経由=TS `lib/listIndexDecode.ts` / Python `scripts/_idx_authors.py`(au_name/au_kana/au_names・旧dict互換)。生読み`.get("name")`は即死、`isinstance(a,dict)`ガードは**黙って空集合**(preorder-gen-previewの親slug継承が音なし無効化=最悪型)。2026-07-14に7script修正+anime-season-viewのcover slim未展開(生成物へ生slim書込=次回再生成で書影全滅)も同型で修正。
- **恒久ゲート**: `_audit-index-hygiene.py`(cover slim漏れ/authors形式/head整合/行数急減)=週次preflight step7でFAIL・日次チェックリスト入り。ガードテスト`lib/listIndexDecode.test.ts` 7本。
