---
name: wiki-distill
description: Wiki蒸留して=Wikipedia書誌(巻別ISBN+発売日)で壊れた長期連載をcanonical復元。①全自動型/②ドカベン式/③現状維持の型判定つき
---

# Wiki蒸留して

トリガー語: **「Wiki蒸留して」**。壊れシグナル持ち(帯混入/うる星型/巻抜けworklist)×巻数多い順に、
Wikipedia書誌を権威としてページを復元する。釣りキチ三平65巻/スケバン刑事22巻で実証(2026-07-04)。

## 手順
1. **対象選定**: docs/production-diagnostics/ の各worklist(band-intruders-manual / urusei-type-manual / volgap374-triageのMERGE・NONE)を合算し、巻数多い順に10〜15作/回。canonical既存slugはskip
2. **実行**:
```
python scripts/_wiki-distill.py --slugs a,b,c --fetch --write
```
   - 記事raw取得(1s/req・.cache/wiki/にキャッシュ)→書誌ブロックparse→型判定
   - ①巻別ISBN型 → canonical自動生成(下のゲート全通過時のみ)
   - ②構成のみ型/③書誌なし → worklist報告(②は後日ドカベン式=Wiki版構成+楽天/NDL充填)
3. **反映**: ①型のslugを `_reflect-targeted.py --only ... --push`
4. **検証**: 各頁で 帯1種化/日付逆行0/巻数=宣言N を数字で確認(達成できない場合は原因を報告)

## ゲート(fail-closed・緩めない)
- 見出し『題』が**頁題とbase一致するブロックのみ**採用(スピンオフ/別編を吸わない=サイボーグ009のBGOOPARTS事故防止)
- ISBN-10→13は**checksum再計算**(Wikiのハイフン揺れ耐性)
- **宣言「全N巻」と抽出数の一致**必須(取りこぼし=②型へ降格)
- **楽天題baseゲート**: cacheに居るISBNの題が1件でも別作ならabort
- Wiki自体の誤記対策=楽天gate+反映後の帯/逆行検証の二重網

## 型の実測比率(パイロット7作)
①巻別ISBN 約4割 / ②構成のみ 約4.5割 / ③なし 約1.5割。候補プール=壊れ518作(巻数10+は116作)。

## 罠
- 記事の書誌が「新装版のみ」の場合、主版=最多巻ブロック選択が新装を主にしてしまう→反映後検証で頁の帯が全交換されていたら疑う(原版温存が原則)
- 複数部構成(第1部/第2部)の記事は全N巻表記が部単位のことがある→巻数不一致で自然に②へ落ちる(安全側)
- 楽天cache無しの古典はgate素通りになりがち→逆行/帯検証を最終網とする
