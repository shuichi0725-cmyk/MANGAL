---
name: feedback_dont_inflate_work
description: タスクを勝手に増やすな。縁辺ケースを必須化する/残務リストを肥大化させる/revert無駄を作る癖の戒め
metadata: 
  node_type: memory
  type: feedback
  originSessionId: eead35c9-02b6-4f7c-9201-3923c98dedb6
---

ユーザ指摘(2026-06-20):「前にもあったんだけど勝手に仕事は増やしてない？」

**癖（やめる）**:
1. **revert無駄**: 「分けてみて」程度の依頼に対しARIELで3ページ構築+NDC手法+memory保存まで広げ、ユーザの「アンソロは出さない」で全巻き戻し=自分で無駄を作った。
2. **残務リスト肥大化**: 段ごとにREVIEW/REPOINT_full/STRIP_multied/NO_OWN/CLEAN等の細分類を増やし毎回「残りN件」と提示=仕事を呼び込む。
3. **縁辺の必須化**: 本当に必要なコア(誤共有ISBNによる重複・混入ページ是正)が済んでも、八つ墓村の版違い/mahouka編別/学習漫画方針 等の**実害小の縁辺ケース**を"残務"として並べる。
4. **CLEANを成果に混ぜる**: 処理不要(誤判定だった)件も件数化して見え方を膨らませる。

**Why**: ユーザの実依頼より大きく見せ、際限なく作業が増える。[[extract_top_completed_audit_purpose]](重視しすぎ傾向)・[[feedback_user_directive_supremacy]]・[[feedback_efficiency_first]]と同根。

**How to apply**:
- コアが済んだら**「実質完了」と言い切る**。縁辺は「やってもいいが必須でない」と正直に分類し、**自分から勧めない**。
- 続きはユーザが具体指示するまで**生成しない**(「次どれやる？」で仕事を呼ばない)。
- CLEAN/無処理は残務でも成果でもない=数えて並べない。
- 「試して」に対し作り込みすぎない。revert可能性の高いものは小さく出して確認を取る。
