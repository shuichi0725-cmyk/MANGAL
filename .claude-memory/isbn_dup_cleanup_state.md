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

**済(R4 2026-07-07)**: SPLIT38群を全証拠精査(`_isbn-dup-case.py`+split38-evidence)で手動裁定→`_isbn-dup-r4-apply.py`で展開。
- dedup 20群48頁(ダイの大冒険/HOLiC×CPC/ナポレオン=エロイカ/ハニ太郎13頁/水惑星7頁/マシュマロ/大魔法峠/クル等=union lossless家族)
- 分割 17群44block(merge-exceptions): ★**number-dedupの不可視本をsurfacing**=ゾクこわい本2025新シリーズ10冊/こわい本角川全11巻/キミノトナリ3巻/ベスティア1-3/カフカ/ドリーム/十蘭/しゅたいんず・げーと!等。検証済(各頁が自分の本だけ持つ)
- ★重要知見: **DUP_PAGE群の正体=find_relatedのグループmergeが「メンバーsidごとに同じunionページをN枚出力」**する構造。しかもnumber-dedup(最古優先)が新しい版/続シリーズを隠す(タッチと同型)。dedupは隠れ本が無い(lossless)時だけ安全、隠れ本があれば分割が正
- 判定手順: ①メンバーsidの自ISBNがunionに全部あるか(隠れ本) ②題系譜(自本の楽天題がcanonical題と相互substring) ③canonical=楽天多数派
- 保留: 妖精国Ballad×継ぐ視の守護者(arc構造の外部確認要・隠れ2冊)

**済(R5 2026-07-07)**: 残139クラスタへR4手順を判定器化(`_isbn-dup-r5.py`=基底題canonical+隠れ本+題系譜+著者不一致はdedup禁止)→全ログ目視→**override6件**(デュエマ世代/双貌のオズO2/ログホラ西風/ダイヤのA外伝=誤dedup→split、C0DE/あおぞら家族セレクト=canonical逆転)→適用。dedup57群64頁(海街diary巻題7頁等)+分割361block(銀河鉄道の夜4作画版/ポケスペ/グラゼニ編別/コーセルテル子竜7冊等)。**機械判定は必ず全ログ目視してから適用**(毎回誤りが出る)。

**残(R5後: ダブリISBN 426個/ペア190件=DUP_PAGE141+SHARED_FEW49)**:
- **REVIEW 33群**(著者不一致×家族題=R5ログ`.cache/r5-log.txt`) = homonym/作画版違い(源氏物語/リング/ウルトラセブン/VALKYRIE PROFILE3頁/X-MEN等)。外部確証per-case。八つ墓村(影丸譲也≠穣也)は同一人名揺れ=dedup可
- **種2二重本籍ISBN**: 同一ISBNが2sidに登録されている型は merge block では消えない → 楽天題を審判に volume-exclude で誤側から除去(気分はもう戦争の前例)
- SHARED_FEW 49件(少数混入) = 同上 volume-exclude 系
続きのトリガー=「ISBNダブリの続き」。

**注意**: AUTO の canonical 選定はメタ充実度優先のため、slug が汚い方(無分かちローマ字長串)が残った群がある(呪具師/レンガ城等)。slug品質是正は別軸(slug-fix ラウンド)で。誤merge厳禁=集合完全一致以外は必ず外部確証([[merge_needs_external_proof]])。
