---
name: intake-manifest-gate-design
description: 【設計済・未実装】型別マニフェスト+出荷ゲート。ship-first傾向と総当たり再探索を潰す。docs/intake-manifest-gate-design.md
metadata: 
  node_type: memory
  type: project
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
---

ユーザ依頼(2026-06-13)で慎重設計。本体= `docs/intake-manifest-gate-design.md`。蒸留の中核設計。

**動機(実証済み)**: ①完成定義が無い→空フィールドでも出荷(ship-first) ②何をチェックしたか記録が無い→次回蒸留で総当たり再探索 ③成年漏れ2,233件=「成年フィルタは走ってるはず」の暗黙前提を出荷前検証できなかった実例。監査部品は7つ存在(coverage/volume-numbering/furigana/foreign/gaps/trailing/publisher)が**結果がページ単位で残らない**=台帳が無いのが核。

**3部品**: 型分類器(入口=ISBN+NDLクラスタで差分判定)→ マニフェスト(git追跡seed=provenance/checks/holes/ship。**台帳が記憶=総当たり回避**)→ 出荷ゲート(型別必須を満たすか機械判定、ship:trueだけ本番、holdは.hold退避)。

**型(9)**: new_volume(最多・継承だけ・虚構推理型クラスタ整合が罠)/existing_author_new_series/new_author_new_series(著者NDL典拠ID新規=表記揺れ根治)/new_edition/correction(slug安定性=alias必須・dateModified差分でしか拾えない)/retro_volume(=種4再定義)/status_change/merge_split_fix(最危険・外部確証必須)。型ごとに必須フィールドが違う=ユーザ直感の通り。

**種4再定義**: 手動input→「取込もれsweep出力」。各候補がマニフェストに外部確証source必須。手打ちは真の例外(大友全集)のみ。MADB追いつきでsource自動切替→dedup退役。

**MADB×NDL両取りの意味**: 相補的。NDL=典拠ID(表記揺れ根治)/正規化主題/版alt。MADB=★成年マーク(ここにしか無い)+巻書誌+dateModified訂正検知。cm104凍結。→「NDLで束ね、MADBで成年と巻を補う」二層。NDL主体は正しいが成年だけMADB必須。

**段階導入**: Phase0=簿記監査(安い・全ページに型/holes/provenance後追い・adult v3と相乗り→取りこぼし発掘)→Phase1=ゲートをpromote/slug-applyに配線(成年漏れ恒久策)→Phase2=型分類器を入口に→Phase3=NDL典拠クラスタ+種4sweep化。★頻度(毎日vs月次)議論はPhase2以降、まずPhase0-1が最短路。

関連: [[merge_needs_external_proof]] [[clustering_unit_is_series]] [[madb_cm104_frozen]] [[adult_judgment_architecture]] [[author_data_map]] [[feedback_complete_data_before_ship]]
