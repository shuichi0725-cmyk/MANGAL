---
name: anilist-link-verification-plan
description: "【①②✅済 2026-07-18】AniListリンク検証: 検証ゲート稼働・疑惑裁定完了(drop813/relink616/FAIL0)。残=③recall上積み(著者経由23,304+P8731直結線)と本番反映(次promote)+unsure12"
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

## 残 (=③、未着手)
- **recall上積み**: 著者経由23,304([[anilist_matching_state]])+P8731直結線+synonyms改善。AniListに無いロングテールは素材ハーベスト(wiki/楽天)が受け皿で正。
- 東京喰種:re 等、AI dropしたが正しい付替先がdumpに実在しうる分はrecall時にrelink回収余地。
- unsure12の目視裁定(ユーザ or Web深掘り)。

## 素材の所在
- dump=.cache/anilist-manga-dump-v3.jsonl.gz(5/31)+delta=.cache/anilist-delta.jsonl(柱⑥随時、mergeはOpus専権=[[idle-run]])
- ゲート出力=.cache/anilist-gate.tsv / 裁定=.cache/anilist-gate-adjudication.tsv
- enrichマップ生成器=_build-anilist-enrich-map.py(overrides+recovery+authorroute読込)
