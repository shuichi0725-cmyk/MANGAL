---
name: data_assets_inventory
description: 全データ資産の地図(種1-4/DB/seed/master/cache/出力)と役割。実スキャン2026-06-08。新規取得・作成物を忘れないための台帳
metadata: 
  node_type: memory
  type: reference
  originSessionId: b2aea090-84ca-49f7-ac76-8bc5d5c410db
---

MANGAL の全データ資産(実ファイル走査 2026-06-08)。 ★これが「何を持っていて何を作ったか」の台帳。 著者系は別途 [[author_data_map]] に詳細(私が忘れがちなため独立)。

## 種1 = RAW MADB (`.cache/madb/`、 gitignore、 再DL可)
- `metadata101.json`(660MB)/ `metadata101-clean.json`(479MB)= **巻(class:MangaBook 約398,605)**。 schema:isbn(10/13混在)/publisher/brand/numberOfPages/datePublished/**creator(ヨミja-hrkt付)**。
- `metadata104.json`(179MB)= **シリーズmaster(★2024-11-25凍結)**。 著者役割[原作]/[漫画]はここのみ。 [[madb_cm104_frozen]]
- `metadata105.json`= 雑誌master(凍結)。 `metadata103`= ? `metadata505`= 小。
- ★`metadata504.json`(44MB)= **作者master(74,982 Agent、 ヨミ21,140、 ma:ndla=NDL典拠IDリンク)**。 著者読みの本命源。 [[author_data_map]]
- 入力CSV `data/seed/mangaka.csv`(6,751 curated)/ `mangaka-madb.csv`(42,115 MADB派生)。

## 種2 = 派生DB (`.cache/db-v2.sqlite`、 165MB、 ★不変protocol、 .bak-* 多数)
- ※ `.cache/db.sqlite` は **空(0byte)= 旧・未使用**。 本物は **db-v2**。
- 主table: `series`(series_key/publisher_key/magazine_key/qid=著者QID)/ `editions`(type/label/imprint=レーベル)/ `volumes`(isbn13/number/release_date/asin/madb_book_id)/ `mangaka`(48,866、 全qid付)/ `series_authors`(229,593 link、 series_id+mangaka_id+role)/ `publishers`/`magazines`/`adult_*`(signals/publishers/mangaka_known/imprints)/`asins`/`amazon_metadata`/`series_archive`/`series_excluded`。

## 種3 = AI fill (`data/seeds/`、 git追跡)
- `series-supplement-v2.yml`(926,278行)= 現行。 旧 `series-supplement.yml`(609,741行)。 ★publisherは**持たない**(ISBN由来=焼かない、 [[publisher_model_edition_level]])。

## 種4 = 巻補完 (`data/seeds/`、 git追跡)
- `volumes-supplement.yml`(224、 手動)/ `volumes-supplement-auto.yml`(11,787)/ `volumes-trailing.yml`(末尾巻)/ `volumes-pending.yml`。

## 作成 seed (git追跡、 ★高価な生成物 = 永続化対象)
- `title-kana-fill.yml`(82,222行)= フリガナ補完(MADB+NDL+AI読み128)。 kana空0達成。
- `synopsis-ja.json`(あらすじ和訳、 anilist_id key)[[synopsis_ja_seed]]
- `furigana-corrections.yml`(3,343)= NDL ground-truth補正。 [[furigana_ndl_audit]]
- ★`publishers.yml`(161社)+`publisher-aliases.yml`= publisher正規化。 [[publisher_model_edition_level]]
- ★`author-yomi.yml`(19,391)= 著者50音読み(504由来)。 [[author_data_map]]
- `non-manga-drop.yml`(1,159 series_key)= 非漫画除外。 [[non_manga_drop_cleanup]] [[ndl_nonmanga_sweep]]
- `magazines-drop.yml` / `art-books.yml`(画集203)[[art_book_inclusion]] / `series-merge.yml`+`recluster-overrides.yml`(統合) / `adult-imprints.yml`+`adult-overrides.yml`+`adult-wikipedia-cache.yml`(成人)/ `stores.yml`(ストア)。
- slug候補TSV群(未適用・GO待ち): `slug-final-integrated.tsv`(76,436)/`slug-katakana-en`/`slug-num-fixed`/`slug-latinmix`/`slug-c2-*`/`slug-collision-option1` 等。 [[pending_slug_generator]]

## master (`data/*.yml`、 git): publishers/ publisher-aliases/ magazines/ genres/ demographics/ slug-aliases。

## cache (`.cache/`、 再生成可・git無視)
- `anilist-manga-dump-v3.jsonl.gz`= AniList全dump(staff full/native、 genres、 description元)。
- `anilist-enrich-map.json`(11MB)= match→enrich(synonyms/genres/tags/anilist_id)。 ★毎promoteでタダ再join(焼かない)。
- `anilist-author-surname.json`= 著者姓romaji(slug suffix用)。

## 出力 = 本番 (gitignore、 force-add時のみcommit)
- `data/manga.v2/`(約69,475 yml)= 本番漫画DB。 `data/art-books.v2/`= 画集。
- ★再生成は `python scripts/_promote-bulk-v2.py`(~36分)。 overlay(Stage D recluster/版タブ)は全rebuildで消える=再適用要。
