---
name: shu2-qid-is-author
description: "種2 series.qid は 作品QID でなく 作者QID (mangaka.qid と100%一致)。種3 key の qid: も作者"
metadata: 
  node_type: memory
  type: project
  originSessionId: 0f064c18-034b-4d7f-b14a-3625a848da25
---

種2 (`.cache/db-v2.sqlite`) の `series.qid` は **作品の Wikidata QID ではなく、作者(mangaka)の QID**。

**検証事実 (2026-05-29)**: qid 付き series 66,579件の **100% が `mangaka.qid` と一致**。
- Q219948 = 高橋留美子(うる星/犬夜叉/めぞん/らんま/MAO 等 全作品がこの1 qid に紐付く)
- Q193300 = 手塚治虫(577 series)、Q471103 = 石ノ森章太郎(419)、等

種3 (`series-supplement-v2.yml`) の key 形式 `qid:Q1049526|name:アリオン` も同様で、
Q1049526 = 安彦良和(作者)であって「アリオン」(作品)ではない。形式は `qid:作者QID|name:作品名`。

**Why**: この構造を「同一 qid = 同一作品」と誤解しやすい(実際 Claude は数セッション誤解していた)。正しくは「同一 qid = 同一作者」。

**How to apply**:
- v9 マッチング ([[[なし]]]) の author signal が強力なのはこの構造のおかげ(作者紐付けが qid で揃う)。アリオン3版(徳間/新装/中公)が1 series に統合されるのも「同一作者QID + 同一作品名」で寄るから。
- 逆に `_promote-bulk-v2.py` の `build_parent_map`(spinoff 親子判定)は同 qid 内で title prefix を見るため、**同じ作者の別作品**(「犬夜叉」↔「犬夜叉奥義皆伝」、「うる星やつら」↔「うる星やつら2 ビューティフル・ドリーマー」)を誤って親子(spinoff)扱いするリスクがある。名寄せ・統合ロジックを触る時はこの前提に注意。
- 同一作品でも作者名表記が揺れて別 mangaka QID になると、別 series に分裂しうる。
