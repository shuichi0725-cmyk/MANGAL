---
name: ndl_volume_completion_better_than_rakuten
description: 巻補完=NDL SRU title検索が楽天title検索より強い(ニッチ/表記揺れ作の全巻を持つ)。書影は楽天ISBN直引きでtitle0件でも取れる
metadata: 
  node_type: memory
  type: project
  originSessionId: 04923414-a96f-48e2-b7f4-5622fc881e58
---

NDL発見作の巻補完で確立(2026-06-28、 キラーズホリディで実証)。

★★**ユーザ厳命(忘れるな): 「NDLで見つけたものだからNDLで探してるもんだと思っていた」**。= **発見源で巻も探すのが当然**。NDL discoveryで見つけた作品の巻補完は、 まず **NDLに戻って探す**(楽天title検索に一律で行かない)。発見源=最も網羅的なsource。私が一律で楽天title検索に行き、 ニッチ作(キラーズホリディ等)を取りこぼした反省。

**問題:** 楽天 **title検索** はニッチ作/表記揺れに弱い。キラーズホリディ(マイクロマガジン社, 松)は「キラーズホリディ」「キラーズホリデイ」「Killer's Holiday」どの表記でも **0件** → 楽天では巻が見つからなかった(NDL原本は「Killer's Holiday. **7**」= vol7のみ持っていた)。

**解決(2段):**
1. ★**NDL SRU の title検索で全巻ISBNを取る**。`https://ndlsearch.ndl.go.jp/api/sru` に `query=title="キラーズホリディ"` `recordSchema=dcndl`。応答は **HTMLエンティティ化**(`&lt;`)されてるので `html.unescape` 必須。`dcndl:volume`=巻、 `dcterms:identifier datatype=ISBN`=ISBN。→ 全8巻 9784867160084〜9784867168516 を取得。
2. ★**楽天 ISBN直引き(`isbn=`param)で書影/発売日**。title検索0件でも **ISBN直引きなら本はある** = largeImageUrl取得可。8巻全部 書影付きで再構築。

**教訓(再利用):**
- ★巻補完の本命source順 = **NDL title検索(全巻発見) → 楽天ISBN直引き(書影)**。楽天title検索だけに頼らない([[harvest_match_mechanism_applied]]の題+巻照合を補強)。
- NDLは凍結MADBや楽天が持たない巻を持つ([[ndl_clustering_design]]/[[madb_data_acquisition]]と整合)。discovery原本が「. N」形式なら多巻シリーズのN巻目signal。
- 機構=`scripts/_ndl-find-missing-volumes.py`(楽天title+著者照合) を NDL title検索でも引けるよう将来拡張すると、 楽天title漏れ(ニッチ作)を全部拾える。
- レート=NDL SRU 1.2-1.5s/req([[ndl_access_rate_method]])。
