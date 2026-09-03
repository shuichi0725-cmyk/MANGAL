---
name: wikipedia_release_date_is_authoritative
description: "【方針・ユーザ裁定 2026-09-03】Wikipediaに巻別の発売日が載っている場合はそれを採用する。種2(MADB)の日付は奥付発行日で実売日と1か月ずれることがある。是正機構=release-date-override.jsonl"
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

★注意: 既存の日付を一方的に上書きするので、**同一頁の巻は全部そろえる**(1巻だけ実売日、
残りは奥付日、という混在を作らない)。混在させると巻×発売日の逆行検出器が鳴る。

初回適用 = `uiui-days`(ういうい♥days 全11巻)。[[gyara_type_regression_cleanup_state]] の
日付逆行案件とは別物(あちらは版の取り違え)。
