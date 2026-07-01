---
name: method-ai-generate-plus-webverify
description: 【有効な手法】大量の不確実データ精緻化=AI一括生成(workflow並列)→怪しい物だけAI Web検証(workflow・作品特定クエリ)→残りはAI案採用。カタカナ英綴りslugで実証
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b2aea090-84ca-49f7-ac76-8bc5d5c410db
---

【ユーザ確認 2026-06-05「今回のやり方が巧く行った・忘れないように」】★大量(数千件)の不確実データを精緻化する有効な手法。

**手法(2段 workflow)**:
1. **AI一括生成(workflow並列)**: 全件をN件/batchに割り、 multi-agent workflow で各エージェントが担当batchを処理(例: カタカナ題→英語綴り or KEEP)。 ★各エージェントは todo ファイルの自分の範囲を `awk` で読み、 構造化schemaで返す。 ★適用せず候補TSVに集約。
2. **AI Web検証(workflow並列・怪しい物だけ)**: AIが自信なし(low-conf)の物だけを Web検索で裏取り。 ★クエリは**作品特定型**「題 + 作者 + 漫画 + 英語タイトル」が効く(単語だけの汎用クエリ[カタカナ+翻訳]は単語は出るが作品に辿り着けない=弱い)。 found/corrected/UNRESOLVED を構造化で返す。
3. **残り(UNRESOLVED/公式無)はAI案を採用**(問題ないと判断)。

**実証(カタカナ英綴りslug、[[pending_slug_generator]])**: 4,249件をAI生成→780件Web検証→是正8%(dessert→desert/double-blind→double-breed/ギャートルズ→giatrus等の実誤りを修正)。 ★**両方ともAI**(生成も検証エージェントもAI)だが、 「AI生成→AI Web裏取り→人は最終GOだけ」の分業が低コストで高品質。

**要点**:
- ★**段階的に試す**(小batch検証→精度確認→全展開)。 ユーザ「いろいろ慎重に試そう」。
- ★**適用しない**(候補TSVに永続化→最終人手レビュー+GO)。 slug等の不可逆操作で必須。
- ★workflow opt-in 必要(ユーザが「workflow で」と言う)。 ローカル処理/別API(NDL等)はWebSearchと非競合で並行可。
- ★造語/日本語は無理に英語化しない(KEEP)、 公式無は低信頼flag→誤適用を回避。

他の大量精緻化タスク(著者読みNDL補完、 synopsis和訳、 ジャンル付与 等)にも再利用可。
