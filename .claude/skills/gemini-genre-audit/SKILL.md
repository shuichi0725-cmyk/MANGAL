---
name: gemini-genre-audit
description: ジャンル検品して/Gemini検品=本番のprovisionalジャンル・要素(~25,000頁)をGeminiでブラインド検品。無料枠(429)まで回して蓄積→不一致だけ裁定。試し読みharvestと並走可の常設アイドルジョブ
---

# ジャンル検品 (= トリガー「ジャンル検品して」「Gemini検品して」。2026-07-14 ユーザ設計)

本番に出ている**AI由来(provisional)のジャンル・要素**には題名だけから幻覚した誤りが混ざる
(実例: パワフル☆まぜごはん=短編集なのに「グルメ」)。Geminiに書誌だけ渡して(=現ジャンルを見せない
**ブラインド**)同定させ、現行と突合して誤りを炙り出す。

## 対象と順序 (= scriptが自動決定・対象リストはClaudeが作る=このscriptが正本)
- `genres_provisional: true` かつ genres 非空の本番頁(~25,396 @2026-07-14)
- 順序: ①catch/synopsis空の頁(=題名だけで付与された疑い濃) ②残りslug昇順(端から全件。人気順禁止)

## 運転 (= 429まで回す・再開可能・並走OK)
```
python scripts/_gemini-genre-verify.py             # queue先頭から429まで(background推奨)
python scripts/_gemini-genre-verify.py --report    # 突合レポート+不一致tsv
```
- **429=日次quota(~500req/日, PT深夜=JST16時リセット)で自動中断**。翌日そのまま再実行で続きから。
- ★**試し読みharvest等と並走可**(Gemini API vs BookLive/TinyFishはホストもレート制限も別物)。
  「やることない時」の常設ジョブ: 試し読みループとこれを同時にbackgroundで流すのが基本形。
- ★quotaは`_gemini-genre-probe.py`(genre:other残の同定)と共有。**probeの残queueが先**、検品は後。

## 裁定と適用 (= 自動では直さない)
1. `--report` → `docs/production-diagnostics/genre-verify-disagree.tsv`(不一致+タグ不適合)
2. AIが不一致を目視レビュー(Gemini側の幻覚もあるので鵜呑み禁止。怪しければ魚でWeb裏取り=[[method_ai_generate_plus_webverify]])
3. 採用ゲート: known × confidence high/medium × master32検証 × **現行がprovisionalの時だけ**(trusted/手動は触らない)
4. 適用 = 頁genres更新 + `genre-rakuten.yml`に修正エントリ追記(後勝ちでshadow) + 索引`--update` + commit/push
5. bad_tags(要素の不適合)も同レビューで剥がす(themesから除去)

## 報告形式
`照会済N(+今回n) / 一致A / 部分P / 不一致D / unknown U`(--reportの出力そのまま)

## 関連
- 材料なし頁のジャンル新規付与=skill enrich-catch-synopsis(Gemini同定の項) / genre:other撲滅=同probe
- master32厳守=[[ai_genre_closed_vocabulary]] / 1件のバグ=型と疑う=[[feedback_one_bug_means_a_class]]
