---
name: wikipedia_release_date_is_authoritative
description: "【方針・ユーザ裁定 2026-09-03】Wikipediaに巻別の発売日が載っていれば採用。ただし★楽天との2ソースゲート必須(月ズレはwiki正・日ズレは本番正が6割)。機構=release-date-override.jsonl。全DB掃引=2,410頁/10,810巻 適用済(2026-09-04)"
metadata:
  type: feedback
---

★**Wikipediaに巻別の発売日が載っているなら、それを採用してよい**(ユーザ裁定 2026-09-03)。

**Why**: 種2(MADB)の `datePublished` は **奥付の発行日**で、書店の実売日と **1か月ずれる**ことがある。
実測(ういうい♥days 全8巻中5巻)= 種2 2004-05-07 に対し Wikipedia/楽天は 2004-04-07。
Wikipediaの単行本節は **巻別ISBN+発売日**を持ち、楽天の salesDate と月単位で一致することが多い
(日付まで一致する巻もある)。読者が見る「発売日」としては実売日が正しい。

**How to apply**:
- 種2由来の巻 = ★**`data/seeds/release-date-override.jsonl`** に1行追記
  (`{"isbn13": ..., "date": "YYYY-MM-DD", "slug": ..., "vol": N, "reason": "wikipedia-release-date", "at": ...}`)。
  promote が **種2値より優先**して焼く(純粋追加・種2不変・行削除で可逆)。消費者= `_promote-bulk-v2.py`
  の `get_release_date_override()`。
- 種4(volumes-supplement)由来の巻 = seed の `release_date` を直接書き換える(★必ず引用符)。
- 裏取りは **Wikipedia × 楽天の2ソース**が基本([[merge_needs_external_proof]] と同じ規律)。
  月単位で一致すれば、日付はWikipediaの方を採る。
- ★**全DB一括の掃引はしない**。Wikipediaに書誌節がある作品は限られるので、
  per-case是正([[percase-fix]] skill)や Wiki蒸留 で触った頁のついでに直すのが実際的。

## ★実測(2026-09-03 サンプル90頁・突合675巻) = 無条件採用は危険

`docs/production-diagnostics/wikipedia-date-sweep-estimate.md` が正本。要点:

- **月ズレ(年月が違う)= Wikipediaが正しい**。楽天salesDateは月ズレ211巻の **92%(194件)で Wikipedia側**を支持。
- ★**日ズレ(同月・日だけ違う)= 本番の方が正しいことが多い**。日ズレ198巻のうち **118件(60%)で楽天は本番側**を支持。
  → **Wikipediaを無条件に採ると 675巻中118巻(17%)を劣化させる**。
- 結論 = ★**楽天salesDateとの一致ゲートを必ず噛ませる**。
  適用してよいのは ①月ズレ×楽天=wiki支持 ②日ズレ×楽天=wiki支持 ③本番がYYYY-MMでwikiに日があり楽天が月までしか持たない(=反証にならない) の3型のみ。
  「三者バラバラ」「楽天=本番支持」は **skip**。
- 突合は ★**必ずISBNキー**。順番合わせで突合すると、記事に文庫版/新装版が併記された作品(空手バカ一代・BANANA FISH等)で
  全巻が誤差異になる(実際に一度やらかした)。ISBNは本を一意に決めるので別版・別作品の取り違えが構造的に起きない。
- 同名別作品の記事は **著者名が本文に出るか**で弾く(実測 4/90頁)。

## 全DB掃引の規模(実測ベース)

- 候補 = **11,268頁**(jawikiに漫画記事があり題が一致)。★Wikidata/QLever の1クエリで確定するので
  69,223頁を盲目的に叩く必要はない(`.cache/jawiki-title-hits.json`)。
- 記事に巻別ISBN+日付があり突合できる率 = **71%**。
- ゲート後に書き換わる巻 = **約2.5〜3万巻 / 6-7千頁**。
- コスト = jawiki取得3.4h + ローカル処理数分 + フルpromote約2h = **実働6時間程度、AIトークンはほぼ不要**。

## ★全DB掃引 実施済み(2026-09-04) = 2,410頁 / 10,810巻

パイプライン3本: `_wiki-date-candidates.py`(Wikidata/QLeverで候補11,268頁) →
`_wiki-date-fetch.py`(記事10,861件・1.1s/req・5.3h) → `_wiki-date-apply.py`(ゲート+override生成)。
月次で再実行すれば新規作品にも効く。判定一覧= `docs/production-diagnostics/wikipedia-date-sweep.tsv`。

★**適用中に4つの穴を踏んだ。同種の一括是正をやる時は必ず先に潰すこと**:
1. **既存overrideを潰す**: 過去のper-case是正(date-disorder等)を掃引が上書きしていた(39巻を9-11年ずらす)。
   → 既にoverride行があるISBNは触らない(ALREADY_OVERRIDDEN)。
2. **粒度の劣化**: 同月なのに YYYY-MM-DD → YYYY-MM に落とす行が144巻/50頁。
   → 「同月で本番の方が細かければ採らない」。★是正時は**粒度を落とさない**を必ずチェック。
3. ★**日付を揃えると promote の `_dedup_key` が入れ替わる**: 同じ巻に種2 ISBNが2本ある頁
   (通常版/特装版)で、dedup順は (出版者多数派, 実効日付, 最小ISBN) なので**日付を変えると勝者が変わり、
   元のISBNが頁から丸ごと消える**。8件/7頁で実際に起きた。= 発売日を触る作業は**ISBN集合の前後比較**が必須。
4. ★**promoteは発売日の組み立て経路が複数あり override が最終値に効かない頁がある**
   (種4 / edition-canonical / edition-overrides / renumber代表巻)。そこだけ効かないので
   **頁内で一部の巻だけ新基準= 基準が混ざる**。126頁で発生 → 掃引ごと取り消した。

★**検算の型**(このとき有効だった):
- `.cache/isbn-page-index.json`(作業前に作られていた)と現在のISBN集合を突合 → 消えたISBN検出。
  ★走査は `variants`/`versions` も含めて**再帰で isbn13 を全部拾う**(volumesだけ見ると348件の偽陽性)。
- コミット済み `data/manga-list-index.json`(=作業前)の `total_volumes`/`max_edition_volumes` と比較。
- 「override行の値 == 反映後の頁の値」を全行照合し、**一部だけ適用の頁**を洗う。
- ★`_reflect-targeted.py` の「★減少検出」は**stderrに詳細を出す**。ログをgrepで絞ると
  スラッグ名が消えて後で追えなくなる = **絞るなら詳細行も残すパターンにする**。

★注意: 既存の日付を一方的に上書きするので、**同一頁の巻は全部そろえる**(1巻だけ実売日、
残りは奥付日、という混在を作らない)。混在させると巻×発売日の逆行検出器が鳴る。

初回適用 = `uiui-days`(ういうい♥days 全11巻)。[[gyara_type_regression_cleanup_state]] の
日付逆行案件とは別物(あちらは版の取り違え)。
