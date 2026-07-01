---
name: audit_fix_queue_post_kobo
description: 【残務・Kobo完走後】広域監査🟡🔵の修正queue。Kobo harvest中はmanga.v2競合で保留。anomaly-*.tsvに証拠
metadata: 
  node_type: memory
  type: project
  originSessionId: eead35c9-02b6-4f7c-9201-3923c98dedb6
---

本番DB広域監査（`_audit-anomalies.py`・66k走査）の修正で、**Kobo全作harvest完走後に着手する分**（Kobo中はmanga.v2直編集が競合するため保留。ユーザ判断2026-06-21）。

## ✅ 完了済（🟢小粒）
年1(姫松1899→2005)/役割接尾strip8/ジャンク著者14/外国版drop8。偽陽性除外=310実在ペンネーム3・979-8 KDP日本作3。yoshida-akimi/isakuは個別2件で保留。

## ⬜ Kobo完走後（🟡中規模・per-case）
証拠=`data/seeds/anomaly-*.tsv`。楽天cache(ISBN→真著者)で回収率測定済:
- **author_publishery 301**: 会社が著者。楽天で真著者**回収可220**/正当会社credit66/cache無13。★回収値に会社token混在(学研/アミューズ/FIREBUG/光栄等)→**クリーニング設計要**(誤って会社を著者にしない・ゲーム原作の正当会社creditは残す)。
- **author_unknown 178**: (unknown)。回収可**111**/unknown64/1。同様にゲーム会社ノイズ。
- **genre_other 904**: 903件がgenre=["other"]のみ=完全プレースホルダ。→[[genre_from_rakuten_story_plan]](楽天あらすじ学習・既6,638作付与)を**この904に拡張**。

## ⬜ 🔵要調査・大半正当
- **title_latin 3,464**: latin題=外国版 or 正当英題の判別要(ISBN国コード/foreigndrop設計)。
- collection_title 313(大半正当な合本)/no_isbn_all 771(大半古書正当)。

## ⬜ 個別2件
- yoshida-akimi(題=著者名「吉田秋生」・ISBN異常0371...)/ isaku(題=「139」・著者も139=両方junk)。

## ✅ クリーン確認
pua_garbled 0(文字化けゼロ)/year異常1のみ=DB全体健全。

## 着手順(推奨)
genre_other(機械的)→著者系(クリーニング設計後・慎重)→title_latin。Kobo完走でデータ充実後が良い。
