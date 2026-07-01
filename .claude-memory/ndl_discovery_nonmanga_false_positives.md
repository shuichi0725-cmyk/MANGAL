---
name: ndl_discovery_nonmanga_false_positives
description: NDC726.1のNDL discoveryは非漫画を偽陽性で含む(エッセイ/ガイド本/インタビュー本/ドキュメント)。名前一致でなく中身(caption/NDL)で漫画性を検証せよ
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 04923414-a96f-48e2-b7f4-5622fc881e58
---

ユーザ指摘(2026-06-28):「**名前だけしかみてなくない？**」(ゲゲゲの女房をページ化+巻補完した件)。

**Why:** NDL discovery(`ndc=726.1`)は漫画分類だが**偽陽性**を含む。「漫画について書かれた本」「漫画家の自伝/インタビュー」「公式ガイド/ドキュメント」がNDC726.1に紛れる。題名が漫画と同じでも中身は非漫画。私が **title一致だけ**でページ化・巻補完し、 武良布枝のエッセイ「ゲゲゲの女房」(実業之日本社文庫・NDL=配架場所:文庫/資料種別:一般図書)を漫画扱いした。巻補完も別ISBN・別出版社の同名本を寄せ集めた。

**実際にドロップした偽陽性(2026-06-28、 caption/NDLで中身確認):**
- ゲゲゲの女房(武良布枝・自伝エッセイ) / MFゴースト…完全**ガイドブック** / おんなじものが違ってみえる(紗久楽さわへの**インタビュー本**・語り下ろし) / 王者の挑戦(マンガ編集部10周年**ドキュメント本**・戸部田誠=ライター)
- 偽陽性でなかった(=実漫画): クニゲイ(青春物語)/SCP財団(コミカライズ)/柴犬食堂(「初のストーリーマンガ」)/BL・恋愛多数。「漫画語なし」caption heuristicは弱い(大半は実漫画)。

**How to apply(検証順):**
1. ★**caption(楽天itemCaption)を読む** = 最良の信号。「自伝/エッセイ(プロローグ漫画でなく)/ガイド/インタビュー/ドキュメント/レシピ本/写真集」=非漫画。「描く/作画/コミカライズ/ストーリーマンガ/連載」=漫画。
2. ★**NDL per-ISBN の `dcterms:description`** = 「配架場所:文庫 / 資料種別:一般図書」は一般書(非漫画寄り)、 漫画は別。`dcndl:genre`/NDC補助。
3. ★著者が**漫画家か** (mangaka masterや既存manga有無)。celebrity/ライター/聞き手著者は要警戒。
4. 巻補完は**同一作の確認**を: 同名別ISBN・別出版社の寄せ集めを排除(著者一致だけでは武良布枝の全エッセイが集まる=不足)。[[ndl_volume_completion_better_than_rakuten]]に追加すべきガード。
- 関連: [[feedback_complete_data_before_ship]](揃えてから載せる)/[[mangal_inclusion_scope]](漫画onlyのscope)/[[feedback_never_default_author_role]](中身を見ずに埋めない)。
