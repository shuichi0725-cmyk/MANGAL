---
name: anilist-link-verification-plan
description: "【①②③全✅ 2026-07-18】AniListリンク検証完了: ゲート稼働・全裁定済(SUSPECT0/FAIL0/PASS51,381)・recall+330。残=本番反映(次promote)と将来のファジーrecall"
metadata: 
  node_type: memory
  type: project
  originSessionId: 2263dd16-1146-4141-862a-d1a3408de999
---

## 完了 (2026-07-18 実行、トリガー「AniListリンク検証やって」)
方針=誤マッチ潰し(precision)が先([[feedback_accuracy_is_the_goal]])。[[anilist_link_quality]]も更新済。

1. **①検証ゲート稼働** `scripts/_anilist-verify-gate.py`: enrich全51,505リンクを独立証拠合議
   (T題完全一致/W=P8731ラベル/R骨格[副題込み=旧S3疑惑の精緻化]/A著者/Y年/V巻/F読切/G乖離/K確認済み)。
   dump v3+delta(柱⑥)をin-memory重ね掛け(dumpファイル不変=Opus専権遵守)。s3側証拠はv14 TSV+種2sqlite fallback。
2. **②裁定完了**: FAIL44+SUSPECT1,968=2,012 →
   - 機械 `_anilist-adjudicate-gate.py`(dump全体native/synonym完全一致+著者ゲート): relink89/drop38
   - AIスライス(Sonnet12体×~158行、precision優先・迷いはWeb裏取り): keep1,471/drop402/unsure12
   - `_gen-gate-overrides.py` で `anilist-link-overrides.yml` へ畳込(942→**1,448**、relink616/drop813)
   - ★AI keepは `data/seeds/anilist-link-confirmed.json`(key→a_idペアallowlist)でゲート再走時PASS化
   - 証跡=`docs/production-diagnostics/anilist-gate-ai-verdicts.tsv`(git永続)
   - 再走結果: **FAIL 0 / SUSPECT 12(unsure、要目視: アタゴオル/深夜食堂の勝手口/マジンガー等アンソロ系)**
   - 6/13の「本編へ寄せる」旧relink 20件を正確な当該エントリへ置換(鬼滅外伝→外伝ID等)
3. enrich map再生成済(.cache/anilist-enrich-map.json 50,919キー)。**本番反映は次promote(週次蒸留)で自動**。
4. CLAUDE.md 月次サニティ監査に「AniListリンク層」として登録済(蒸留後に再走→新規FAIL/SUSPECTだけ裁定)。

## ③recall v2 ✅ (同日実施)
- `_fetch-p8731-full.py`: ★P8731全量8,072項目(jaラベル7,818+別名2,512)をQLever取得=.cache/p8731-full-map.json。
  AniList側typo(リーセロッテ/スカバンジャーズ)をWikidata正ラベルで橋渡す独立正解チャネル。ゲートW+もこれで拡大(5,836→6,466)。
- `_anilist-recall-v2.py`: 未マッチ37kに C1広域題一致/C2 P8731/C3著者×骨格 → 証拠合議で **新規310+drop復活relink20**(進撃の巨人悔いなき選択→外伝ID等)。
  ★実装ガード3種: A-(両側著者あり不一致=同名異作) / Y-はV+必須(坊っちゃん型=原作者経由の別作画遮断) / 純ASCII<3文字候補化禁止(MÄR→"mr"衝突)。
- unsure12は専任エージェント深掘りで**全件drop確定**(頁実体がエッセイ本/画集/レシピ本/米版邦訳/選集の部分一致等)。
- 最終: **リンク51,383 / PASS 51,381 / SUSPECT 0 / FAIL 0**(NO_DATA2=dump外aidで実質no-op)。overrides 1,460(relink636/drop805相当)。

## 残
- **本番反映=次promote(週次蒸留)で自動**(enrich map 51,234キー再生成済)。
- 将来recall: 残る未マッチ大半はAniList未収録 or ファジー題(AI照合要)。素材ハーベスト(wiki/楽天)が受け皿で正。
- 蒸留後の運用: ゲート再走(dump/match更新後)→新規FAIL/SUSPECTだけ `_anilist-adjudicate-gate.py`→AIスライス→`_gen-gate-overrides.py`。

## 素材の所在
- dump=.cache/anilist-manga-dump-v3.jsonl.gz(5/31)+delta=.cache/anilist-delta.jsonl(柱⑥随時、mergeはOpus専権=[[idle-run]])
- ゲート出力=.cache/anilist-gate.tsv / 裁定=.cache/anilist-gate-adjudication.tsv
- enrichマップ生成器=_build-anilist-enrich-map.py(overrides+recovery+authorroute読込)
