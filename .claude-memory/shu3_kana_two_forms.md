---
name: shu3-kana-two-forms
description: 種3の title_kana(スペースなし)=HP表示用、 title_kana_segmented(スペースあり)=slug生成用。2形式は意図的
metadata: 
  node_type: memory
  type: project
  originSessionId: 0f064c18-034b-4d7f-b14a-3625a848da25
---

種3 (series-supplement-v2.yml) は フリガナを **2形式** で保持 (= 意図的)。

- **title_kana**(スペースなし、連結)= **HP表示用**フリガナ + 50音ソート/検索キー。 実測 スペース0件。
- **title_kana_segmented**(スペースあり、分かち書き)= **slug生成用**。 語境界(助詞含む)を半角スペースで区切り、 ローマ字化の手がかりにする。 実測 65,249件がスペース入り(複数語作品)、 残りは1語でkanaと同一。
  例: 「機動戦士Zガンダム」→ seg=「キドウ センシ Z ガンダム」

**Why**: slug は語境界がないとローマ字化で詰まる(助詞ハイフン区切り等)。 だから連結(表示用)と分かち書き(slug用)を並存。

**How to apply**:
- slug 命名規則の詳細は **CLAUDE.md「slug 命名規則」節**(= 2026-05-29 全面改訂: 公式英題不使用 / ヘボン式 / 数字4分岐 / カタカナ=種a english音写フィルタ / 当て字=MADB+種a+Wikipedia 3ソース突合 / 衝突=姓+年suffix)。 segmented はその ローマ字化の入力。
- 既知の誤分割例: 「アラカルト」(à la carte=1語)が「ア ラ カルト」と誤分割 → slug崩れ。 分割品質が slug 品質に直結。
- 表示フリガナは必ず title_kana(スペースなし)。 segmented を表示に使わない。
- 関連: [[project-architecture-seeds]]
