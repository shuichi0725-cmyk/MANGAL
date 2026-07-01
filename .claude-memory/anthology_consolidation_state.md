---
name: anthology_consolidation_state
description: アンソロジー統合の調査・seed・過統合監査の状態(Web照合372→safe270)。promote結線は未実装。過統合検出=題発散/imprint実体社/巻数照合の3ガード(ISBN5桁prefixは同一社多帯で誤検出)
metadata:
  node_type: memory
  type: project
  originSessionId: 40db3460-5533-4358-8d06-8214ea9ecaea
---

★アンソロジー統合 = 本番のアンソロ分裂を(レーベル×フランチャイズ)1ページに束ねる作業。2026-06-25時点。

## 調査(完了・Web/Wiki照合・コスト度外視で実施)
- 候補372単位(imprint型54[劇場/4コマ] + title型318[アンソロジー/傑作選])を**分散workflow 38agentでWeb照合**。
- 裁定: **真アンソロ304** / 傑作選40(=既刊再編・drop寄り) / 単著4コマ13(誤検出) / 本編混入11 / uncertain4。
- 結果永続化: `data/seeds/antho-investigation-2026.json`(全372のverdict)。

## seed(構築済・未実装)
- `data/seeds/anthology-merge.yml` = 真アンソロ×(one-page-all/split-by-label)×conf≥0.7 の296単位/646断片sid。
- 巻数ドライラン検証(種2統合ISBN数 vs Web巻数)=**一致265/90%**。
- ★**safe 270**(自動統合可=一致+種2不足[=種4補完領域]) / **要確認26**(過merge疑い5・split-by-label18・複数社1[夢王国]・web不明6)。

## ★過統合監査の3ガード(私の悪癖対策・再利用可)
1. **題発散**: 断片題に共通する4字以上のフランチャイズ片が無い=別作品混入。safe内=**0**(健全)。
2. **imprint実体社**: 断片のimprintが**別の出版社**に跨る=split-by-label漏れ=過統合。★**ISBN5桁prefix(isbn[4:9])は同一社の複数帯で誤検出**(佐世保=電撃EX/NEXT両KADOKAWA等8件が偽陽性)→**imprint文字列→出版社family判定が正**。safe内の真の複数社=**夢王国1件のみ**(一迅社IDコミックス+KADOKAWAビーズログ)→降格。
3. **巻数クロスチェック**: 統合巻数 > Web巻数 = 過merge。一致265で強くガード(過剰5は隔離済)。

## 統合model(Webが単位ごと裁定)
- **(レーベル×フランチャイズ)=1ページ**に全寄稿者。★**同フランチャイズでも別レーベルは別ページ**(艦これ横須賀[KADOKAWA,23巻] vs 佐世保[電撃,21巻])=[[clustering_unit_is_series]]の1レーベル単位と一致。
- **本編コミカライズは別ページ**(keep_main_separate=261)。傑作選は題に有っても要Web判別(COM傑作選=best-of=drop / 浅見光彦傑作選=実は各話別作家=真アンソロ)。

## ★未実装(promote結線=慎重に・ユーザGO待ち)
現状アンソロは title「アンソロジー/傑作選」で**drop**(_promote-bulk-v2.py L2313)=本番から消えている。統合には①seed安全分のdrop免除 ②find_related強制統合(homonym guard上書き) ③**page-dedup**(断片の非アンカーslug重複防止=最注意) ④入力源確認。ユーザ指示=「無理に進めない・過統合に注意」。

## ★方針追記(2026-06-25 ユーザ確定): アンソロは「今はdefer・後で無理なく」
- ユーザ: 「アンソロジーは出したいが壊れる原因なのも事実。後から無理なく出せる時に出す方針」。
- ★現preview/蒸留からは**全アンソロを非掲載(defer)**。NONMANGA_TITLE(アンソロ/アニメコミック/読者投稿)+NONMANGA_SERIES(ムック/ぐる漫/MAY'S)で除外。
- ★後日、本番が固まったら anthology-merge.yml(safe270) の (レーベル×フランチャイズ)1ページ統合で出す。
- ★落とし穴: discovery題の文字数truncで末尾「アンソロジーコミック」が切れ検出漏れする(40字→3件しか検出、120字→28件顕在化)。**題は長く取る**(_ndl-discovery.py title[:120])。
