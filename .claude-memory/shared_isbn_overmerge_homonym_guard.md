---
name: shared_isbn_overmerge_homonym_guard
description: "shared-ISBN過merge=find_relatedが別著者homonymを読み/題衝突でmerge。生成器に実行時homonym guard(共通著者なし+巻番号∩/min≥0.5)追加で2,264→1,594(-30%)。残=同著者/アンソロ"
metadata: 
  node_type: memory
  type: project
  originSessionId: 40db3460-5533-4358-8d06-8214ea9ecaea
---

★本番の **shared-ISBN(同一ISBNが複数ページに重複計上=巻数破壊)** の根因と修正(2026-06-24)。
発端=ヴァルキリープロファイル巻数破壊→監査で全DB **共有ISBN 2,264 / 影響849ページ / 363クラスタ**。

## 根因 = promote `find_related_series_ids` の過merge
- 種2では各ISBN=1series所属(**共有0**)。過mergeは**promoteが生成**。
- find_relatedの **orphan題一致・kana一致** paths が著者を見ず、`pub_compatible`も**アンカー出版社空で素通り** → 別著者の別作を読み/題衝突でmerge。
- 例: JIPANG(速水翼)≠ジパング(かわぐち) が kana"ジパング"一致で合体→jipangページがかわぐち65巻を吸収。

## ★全signalが自動判別不可と実証(重要な戒め)
著者/題/kana/巻重複/NDL編/多作家 を試した結果、**homonym vs anthology vs editions を単一signalで綺麗に分離できない**(誤陽性陰性両方)。[[feedback_dont_repeat_regrouping_error]]の罠。
- ★**種2 qidは不整合**: 同一著者に別qid(FULL SWING=マツセダイチが2qid)。qid-guardは168 regression。
- ★**NDL著者典拠IDが種2qid不整合を解消**(FULL SWING別qidだが典拠01208718同一で実証)。但しNDL=**429/IP遮断**(1,043連続で踏んだ)・商用API申請要→大量不可。
- → ★**qidでなく「著者名+巻番号」**が実用解。

## ★採用した修正 = 生成器の実行時homonym guard
`_is_homonym(main,cand)`: **共通著者なし かつ 巻番号 ∩/min(小さい方の半数以上) ≥0.5 → 別作=cluster除外**。
- ∩/min必須(Jaccardだと JIPANG3巻/ジパング46巻で薄まり0.07)。JIPANG⊂ジパング域=3/3=1.0=別作。
- 検証: JIPANG/ジパング・カリスマ(花小路≠石原)=分離✓ / FULL SWING(同名別qid)・ドーベルマン(原作作画相補巻)=維持✓。最リスク両≥5巻高重複100も金瓶梅/BABEL/FE=正当別作。
- コード: scripts/_promote-bulk-v2.py の find_related末尾 + `_build_author_vol_index`。

## 結果(再promote後)
- **共有ISBN 2,264→1,594(-30%) / 影響849→627頁**。jipang=速水翼3巻に修正。
- ★**残1,594 = guard対象外**: 同一著者の過merge / アンソロ寄稿者(相補巻で別作と言えない) / qid欠落。
- 次フェーズ = アンソロは [[mangal_inclusion_scope]] 方針で**(レーベル×ゲーム)curated統合**(著者名でなくシリーズ+巻数が主軸=ソーサリアン/ARIEL型)。同著者ケースは別途。

## 関連監査資産
- data/seeds/shared-isbn-audit.tsv(共有ISBN→ページ) / shared-isbn-triage.tsv(363クラスタ分類: 誤接続289/同名異作71/アンソロ3)。
- scripts/_ndl_authority_resolve.py(NDL典拠解決・429回避で小バッチ後日)。
- アンソロ検出: 巻レベル(編/多作家)とシリーズレベル(ソーサリアン=各巻単著・imprintで束ねる)の2層。種2 madb_book_id→madb-mid-roles.jsonで寄稿者回収可(MADBは代表のみ記録)。
