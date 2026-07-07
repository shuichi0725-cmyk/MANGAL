---
name: isbn-dup-cleanup-state
description: 【進行中】本番ISBNダブリ潰し。R1=AUTO層19群統合済、残=per-case queue 250群(docs/production-diagnostics/isbn-dup-queue.tsv)
metadata: 
  node_type: memory
  type: project
  originSessionId: a2ed548f-4b21-42ea-9ad0-229054bf2d45
---

D・N・A²分裂(2026-07-07 ユーザ発見)を機に系統検出→一括是正を開始。**全部やる**([[feedback_no_popularity_priority]])。

**道具**(全てgit済):
- 検出器 `scripts/_audit-isbn-dup-pages.py` = 本番66k走査(~1分)、同ISBN複数頁を DUP_PAGE(頁丸ごと)/SHARED_FEW(少数混入) に分類 → docs/production-diagnostics/isbn-dup-pages.tsv
- 層別 `scripts/_isbn-dup-triage.py` = クラスタ化し AUTO(正規化同題×ISBN集合完全一致=外部確証不要で dedup 可) と QUEUE(per-case) に分割 → .cache/isbn-dup-auto.json + docs/production-diagnostics/isbn-dup-queue.tsv
- 適用 `scripts/_isbn-dup-apply.py` = AUTO を page-dedup.yml+alias+_redirects+changelog に焼く → reflect-targeted で反映

**済(R1 2026-07-07)**: AUTO 19群19頁drop(空手バカ一代/BOYS BE/國崎出雲/魔法科高校/DARKER THAN BLACK/北の土龍等。著者表記違い5群=作画交代断片も集合一致で安全)。ダブリISBN 2033→1819・ペア601→582。

**残 = QUEUE 250群**(isbn-dup-queue.tsv)。内訳と型:
- 題不一致(87群+複合): こわい本/続こわい本型=**分割案件**(dedупでなく巻の正しい振り分け。外部確証要)、SPIRAL/スパイラル型=**表記違い**(実は同作、正題を決めて dedup+slug 判断)、ハニ太郎型=**巻割れ**(各巻題が頁化、renumber統合系)
- 集合不一致(部分重なり): 混入巻の除去/移設(per-case、[[volgap_per_case_cleanup_state]]と同型)
- 著者不一致+集合不一致(33群): homonym/過merge疑い=最も慎重に

**注意**: AUTO の canonical 選定はメタ充実度優先のため、slug が汚い方(無分かちローマ字長串)が残った群がある(呪具師/レンガ城等)。slug品質是正は別軸(slug-fix ラウンド)で。誤merge厳禁=集合完全一致以外は必ず外部確証([[merge_needs_external_proof]])。
