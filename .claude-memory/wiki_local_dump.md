---
name: wiki_local_dump
description: 【★】Wikipedia(ja)は手元の本文ダンプ(scripts/_wiki_local.py・C:の.cache/jawiki-dump)から引く。API禁止(15回で429)。新版は日次蒸留の手順0で update
metadata:
  type: project
---

2026-11-07 ユーザ「Dドライブのwikiはcドライブに移して。新しいのが出たら落としてwikiはそこから検索するようにして」。
(実際は最初から C: の .cache に置いていた。 報告で D: の空きを書いた誤り = [[feedback_no_d_drive]])

**仕組み**: `scripts/_wiki_local.py`
- 置き場 = C: の `.cache/jawiki-dump/`(D: なら止まる `_assert_c_drive`)。 中身 = 本文ダンプ 4.9GB・索引・page_props + 作った `jawiki.sqlite`(page=記事名→場所 / redirect / cat=本文の[[Category:]](記事と分類ページ)/ qid)+ `manga-articles.jsonl`・`redirects.tsv`(連載誌の台帳が読む)+ `meta.json`(版)。
- `update` = 配布元の Last-Modified が手元と違う時だけ落として作り直す(約1時間)。 `status` で版を見る。 ★**日次蒸留の手順0で裏で回す**(daily-distill SKILL)。
- 道具から `W.get/text/categories/members(cat,kind)/qid/links/prefix/resolve/is_disambig/dump_date`。

**切り替えた道具(API を外した)**: _element-harvest(要素収集: extracts→to_text・検索API→prefix)・_material-harvest wiki-fetch(柱⑤)・_kana-digit-harvest(柱⑧)・_wiki-date-fetch(Wiki蒸留)・_harvest-wiki-genres(分類の記事/下位分類)・_wiki-extract・_magazine-ledger・mag_master_3。 ★ダンプに無い記事(ダンプより新しい)は「無い」と記帳しない([[feedback_no_negative_record_on_failure]])。

**できないこと**: 全文検索(前方一致で代用)/ テンプレートが付ける分類・隠し分類 / ダンプ以降の編集。 古い一時物 = `.cache/magazine-wiki`(API で取った151本)・`jawiki-latest-all-titles-in-ns0.gz` は不要。

関連: [[magazine_corrections_mechanism]] [[site_gate_robots_claude_denied]]
