---
name: monthly_distill_real_pipeline
description: 月次蒸留の実体パイプライン(CLAUDE.md記載の旧.tsスクリプトは廃止)。1.2.17取込の全手順と安全な増分マージ機構
metadata: 
  node_type: memory
  type: project
  originSessionId: 04923414-a96f-48e2-b7f4-5622fc881e58
---

★運用手順の正 = **skill monthly-distill**(2026-07-04 skill化。トリガー/順序/監査はそちら)。
本fileは配管の実体・1.2.17実績・検証方式の**記録**(skillの根拠)として保持。

月次蒸留の**実体**(2026-06-28に1.2.17取込で確立)。★CLAUDE.md記載の旧protocol(`_diff-madb.ts`/`_diff-series.ts`/`_select-supplement-diff.ts`/db.sqlite)は**廃止済**。実scriptは下記。

## 配管の実体
- 種2 = **`.cache/db-v2.sqlite`**(db.sqliteは空0byte=旧TS系の残骸)。99.9%がcm101由来(madb_book_id付)+ ndl-distill少数 + 楽天cover/date enrichment。
- ★cm101 ISBNはISBN-10が127k件混在 → normalize後352,719 ⊃ db-v2 341,931。**全再構築は非破壊だがcover/enrichment喪失**するので増分が正。

## 取込手順(1.2.17で実証・全安全)
1. **release取得**: GitHub `mediaarts-db/dataset` releases。最新tag確認(`curl api...releases`)。metadata101_json.zip(50MB)DL→unzip→`.cache/madb-distill/metadata101.json`。cm104/105は2024-11凍結=DL不要。
2. **delta試走(安全・種2 read-only)**: `_distill_delta.py 1.2.17` → delta件数+manifest。★ただしISBN-13のみ比較で過大(madb_book_id dedup無)。正味は下記マージで確定。
3. **clean**: `npx tsx scripts/clean-madb-seed.ts --in <raw> --out .cache/madb-distill/metadata101-clean.json`(~5分・zero data loss検証付)。
4. **temp権威build**(path override env使用=既定の1.2.16成果物を汚さない):
   - `MADB_META101_CLEAN=...clean.json MADB_SERIES_V2_OUT=...series-v2-1217.json python _build-series-v2.py`
   - `cp db-v2.sqlite db-v2-1217-temp.sqlite` (schema+mangaka継承) → `MADB_DB=temp MADB_SERIES_V2=...1217.json python _populate-v2.py`
5. **★増分マージ** `_distill-incremental-merge.py <temp_db> [--apply]`:
   - temp(新tag権威cluster)と現db-v2を**series_key突合**。A.新series=copy / B.既存series=新ISBN巻のみappend。
   - ISBN/madb_book重複guard・**既存行0変化**・backup・manifest(可逆)。clustering再解釈ゼロ(同一script出力)。
   - ★1.2.17実績=**新series 323(308が2026新刊)/純増volume 1,195**(=月1,000-1,300実態と一致)。
6. **promote**(`python _promote-bulk-v2.py`、~20分・終了後hangするのでart-books.v2 log後にkill)。発売日override seedを読む。
7. **cover再適用**(promoteはdb-v2.cover_url[201k]から書影→covers seed[303k]より少)→ `_apply-covers-stage.py`で復元必須(1.2.17で-3,622枚→55,127復元)。
8. **索引再生成** `_build-list-index.py`(~21分)。
9. **種4退役** `isbn13がdb-v2在`の種4を除去(1.2.17で251件・775→524、backup+changelog)。
10. `.cache/madb-last-release.txt` → 1.2.17。

## 検証(必須・データ損失監査)
- ★**表示カタログ不変確認**: pre/post `manga-list-index.json` の slug集合diff(1.2.17=完全一致・損失0)。ファイル数(.yml)の増減はnon-displayable churnで誤警報になる→**indexのslug集合**で見る。
- merge後: series/volume件数=期待値、既存ISBN sampleのcover/date不変。

## 残(種3 AI fill=表示化)
- 新作323はジャンル/あらすじ"穴"でmanga.v2にfile有るが**非表示**(index未収録)。AI fill(genre closed-vocab/synopsis要約)→再promoteで表示化。1.2.17ではここ未了。
- 関連: [[harvest_match_mechanism_applied]] [[monthly_intake_reality]] [[madb_cm104_frozen]] [[feedback_dont_repeat_regrouping_error]]
