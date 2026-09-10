---
name: new_page_creation_srcpage_key2slug
description: 【手順】per-caseで新しい頁を作る=data/manga(合成ソース)にsrc頁+.cache/apply/key2slug.tsvにキー登録。両方git外だが恒久資産。片方だけだと再生成で消える
metadata: 
  node_type: memory
  type: project
  originSessionId: 814118b1-fc50-4622-83ea-59182e2023e1
  modified: 2026-09-10T01:19:29.129Z
---

2026-09-10 実地。過mergeを解いてスピンオフを独立させた時(酷くしないで 小鳥遊彰編)の手順。

## 前提: 頁は「合成ソース駆動」

`_promote-bulk-v2.py` は **`data/manga/*.yml`(合成ソース)の slug を起点**に db-v2 を引く。
種2に series が在っても**src頁が無ければ頁にならない**([[orphan_series_promote_is_srcpage_driven]])。
その合成ソースは `_slug-apply-build.py` が **`.cache/apply/key2slug.tsv`(series_key → slug)** から冪等生成する。

★`data/manga/` も `data/manga.v2/` も **.gitignore(再生成物)**。
`.cache/apply/` と `.cache/db-v2.sqlite` は **git外だが恒久ローカル資産**(scratchではない)。

## 手順

1. **種2に独立した series が在るか**を確認。無ければ頁化しない(捏造禁止)。
   ```
   select id, series_key, title from series where title like '%…%'
   ```
2. **`.cache/apply/key2slug.tsv` に1行追加**(タブ区切り)。ここが恒久化の本体。
   ```
   qid:Q8980314|name:酷くしないで 小鳥遊彰編<TAB>hidoku-shinaide-takanashi-akira-hen
   ```
3. **`data/manga/<slug>.yml` を作る**(最小形。既存頁と同じ5行)。
   ```yaml
   slug: <slug>
   title: <題>
   wikidata_qid: <QID>
   _skey: <series_key と同一>
   title_romaji: ''
   ```
4. `python scripts/_promote-bulk-v2.py --only <slug>` → 頁生成。必須メタ(kana/authors/year/genres)が
   埋まったかを確認(埋まらない=登録保留。空欄で載せない)。
5. ★**冪等確認**: `python scripts/_slug-apply-build.py` を全量実行して **src頁が生き残る**ことを見る。
   2 を飛ばして 3 だけやると、ここで**消える**。

## ★過mergeを解いて独立させる時はセットで

`merge-exceptions.yml` に sid 対を足して遮断しただけだと、**本編から外れた上に自分の頁が無い**
= サイトから消える(2026-09-10 に実際に一時消した)。**遮断と頁化は必ず同じ作業でやる**。

関連 [[seed_silently_ineffective_class]] [[never_delete_because_broken]] [[merge_needs_external_proof]]
