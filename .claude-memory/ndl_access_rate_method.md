---
name: ndl_access_rate_method
description: 【厳守】NDLの叩き方=楽天と同じ1.2秒/req(0.2s=5req/秒の大量burstで429/IP遮断を実踏)。SRU=典拠あり要レート/OAI=throttle無だが削除支配+漫画希薄+典拠無で漫画discovery不可。discovery=NDC726.1月分割+再帰日付分割
metadata: 
  node_type: memory
  type: reference
  originSessionId: 40db3460-5533-4358-8d06-8214ea9ecaea
---

★NDL API の叩き方(2026-06-24 確定。 [[ndl_clustering_design]]の運用面を実測で確定)。

## ★レート = 楽天Books APIと同じ 1.2秒/req(厳守)
- **0.2秒(5req/秒)で1,043件連続 → HTTP 429 / IP遮断を実踏**(SRU)。memoryの「継続大量アクセスで遮断」が現実化。
- → ★**全NDL SRU照会は 1.2秒/req(=~0.83req/秒、 楽天parity)**。小バッチ・月分割・間隔空け。**過剰に遅くする必要は無い**(楽天と同じでよい)。
- 遮断されても**回復する**(数時間)。慌てず slow down + 待つ。OAIは別endpointで遮断されない(Identifyで生存確認可)。

## 2経路の使い分け(実測)
- **SRU** (`/api/sru?operation=searchRetrieve&query=CQL&recordSchema=dcndl`): ★**著者典拠ID(`auth/entity/NNN`)が取れる**(homonym/clustering用)。**但しレート制限**→1.2s。CQL例 `ndc=726.1 AND from="YYYY-MM-DD" AND until="YYYY-MM-DD"`(漫画×年月)。**1照会500件窓**(maximumRecords上限)。
- **OAI-PMH** (`/api/oaipmh?verb=ListRecords&metadataPrefix=dcndl&from/until`): ★**throttle回避(オープンデータ)・登録日(datestamp)バルク**。★**だが漫画discoveryに使えない**: ①recent日付feedは **`status="deleted"`が支配**(追加でなく削除/再目録化) ②漫画希薄(~1.7%・NDC/Cコード欠落) ③**著者典拠ID 0個**(dcndl/dcndl_v3とも)。= 登録日OAIは見送り、SRU月分割が正解。

## ★新刊discovery = `scripts/_ndl-discovery.py`(採用)
- NDC726.1を**年月で引く**→種2 ISBN dedup→新刊候補(isbn/date/publisher/title/creators)。
- ★**500件窓は再帰日付半分割**(total>500なら[frm,until)を半分割し再帰)で全件カバー。
- 1.2s・resumable(取得済skip)。検証: 2025-05=NDL漫画2,421件中87件が種2外。
- Stage2典拠enrich=新刊ISBNのみ SRU per-ISBN(同1.2s・小集合なら429内)。

## 他のNDL SRU script(rate統一済)
- `_ndl-date-backfill.py`(発売日backfill・SLEEP 0.2→**1.2**修正済)。`_distill_match_v2.py`のvol1照会も同様に1.2s化対象。
- 商用(MANGAL=アフィリエイト)は本来NDL API利用申請が必要(大量時)。
