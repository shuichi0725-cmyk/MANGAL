---
name: ghost_vol_date_disorder
description: 幽霊巻(ISBN無)がvol1より前の日付=多版混在。Type A(1巻もの)=是正済/Type B(多巻名作)=幽霊は本物
metadata:
  node_type: memory
  type: reference
---

「後の巻(vol2+)がISBN無し＋vol1より前の日付」＝**多版混在による日付逆行**(ユーザ指摘 2026-07-08・罪と罰型)。検出=`docs/production-diagnostics/ghost-vol-date-disorder.tsv`(全66k走査)。**492頁/1537幽霊巻**。幽霊は1970-80年代中心。

## 2種類(判定=NDL巻数+ページ巻数)
- **Type A(182頁)=1巻もの**にedition違いが偽の複数巻(vol2/3)で混入。「vol2の日付<vol1＝続巻ではありえない(先に出るはずない)＝別edition誤ラベル」で論理的に確定。全182頁NDLで1巻ものと確認。★**是正済**: 幽霊除去+原作年保持(全巻最古年をyear明示)+ISBN版は版タブ(versions[])で保全(86頁が2版)。edition-overridesで一括。
- **Type B(310頁)=実在の多巻名作**(まんだら屋の良太52/ワイルド7/おれは鉄兵/博多っ子純情/がきデカ等)。幽霊は**本物の原作巻**(pre-ISBN or ISBN未取得)=**削除NG**。日付逆行はvol1が復刻版日付になっている多版混在([[multi_edition_unification_pending]])。★**未対応**=多版分離(日本の歴史型の版タブ化)が要る別プロジェクト。慎重に少しずつ。

## 罠(実装時)
- ★edition-overrideは**内部slug(yml内slug:)でキー**。ファイル名≠内部slugのslug-override頁(聖マッスル=sento-massuru等)はファイル名キーだと不一致で無効化→内部slugで登録。
- ★既に幽霊除去済の頁を一括生成器が読むと原作年を拾えない(罪と罰=1953が1977に化けた)→year明示で復元。
