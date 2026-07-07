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

**済(2026-07-07 R1-R3 = 計65群81頁drop)**: ダブリISBN 2033→1361・ペア601→488。
- R1 AUTO(同題×集合完全一致) 19群19頁: 空手バカ一代/BOYS BE/國崎出雲/魔法科高校等
- R2 楽天題裁定(題違い×集合一致、`_isbn-dup-r2-titlefix.py`) 45群61頁: 共有ISBN全冊の楽天題が90%以上単一作品に収斂+★少数派頁題ガード(闇都市伝説×キミノトナリ型=別作品union疑いはSPLIT送り)。スパイラル/WINGS/千里の道も3部/ギリシア神話巻題7頁等
- R3 包含(同題×著者×⊆、`_isbn-dup-r3-subset.py`) 1群: こち亀226⊂227統合

**残 ≈ 204群 = 全て per-case**(機械層は掘り尽くした):
- **SPLIT 38群**(docs/production-diagnostics/isbn-dup-split.tsv、楽天題グループ証拠つき) = union汚染の分割(こわい本/ハニ太郎/ダイの大冒険巻題群)。dedup でなく巻の振り分け直し=volume-exclude/種4移設
- FLAG 4群 = 楽天キャッシュ0件(wani-bunsho等)→楽天live/NDLで裁定
- 題不一致+集合不一致 102群 / 著者不一致系 58群 / ヤマト・ウルトラマン(相互固有1冊) = 外部確証(Wiki/NDL)per-case、誤merge厳禁
続きのトリガー=「ISBNダブリの続き」。SPLIT38 から着手が効率的(楽天証拠が既に付いている)。

**注意**: AUTO の canonical 選定はメタ充実度優先のため、slug が汚い方(無分かちローマ字長串)が残った群がある(呪具師/レンガ城等)。slug品質是正は別軸(slug-fix ラウンド)で。誤merge厳禁=集合完全一致以外は必ず外部確証([[merge_needs_external_proof]])。
