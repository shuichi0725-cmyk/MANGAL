---
name: kishi_gundam_shinsoban_consolidation
description: 【型・是正済】騎士ガンダム型=新装版が編ごとに別頁へ散り、番外編(特別版)が本編1〜3巻と番号衝突で不可視、1作品は頁ごと抜け。楽天captionで収録対応を確定し版タブ統合+新頁2+旧頁5をdrop→301
metadata:
  type: project
  originSessionId: dda2405f-dff7-4d64-8920-5bc40bd58795
  modified: 2026-09-02T21:28:57.209Z
---

**2026-09-03 是正済**(ユーザ提供 NDL書誌29行TSV + ja.wikipedia を起点。反映済み・preview投入済み、本番R2は次の週次)。

## 症状(ほしの竜一『騎士ガンダム』シリーズ 11頁)
1. **新装版が別頁に散る**: 2015年KCDX新装版『SDガンダム外伝 騎士ガンダム物語』全9巻がMADBで**編ごとに9本のseries**に割れ(種2 sid 120769〜120776)、本番は2頁だけ(ラクロアの勇者編1冊/『聖機兵物語編』頁)、**5冊未掲載**。2017年新装版(機甲神/魔龍ゼロ/黄金神話)も原版とは別頁。
2. **番号衝突の汚染**: 『聖機兵物語編』頁の1巻枠に「伝説の巨人編」(別seriesの#1)が座り、真の「聖機兵物語編・上」が dedup 負けで不可視。
3. **番外編の不可視**: ボンボンKC『騎士ガンダム物語 特別版』1〜3巻(デラックスボンボン連載の番外編)が種2で本編と同edition内の #1〜#3 に登録され、本編1〜3巻と衝突して**どの頁にも出ていなかった**。
4. **作品ごと抜け**: 『SDガンダム列伝 ガンダム騎士団』(1998年連載・2017年初単行本化)は種2に在る(sid 132427)のに頁が無い([[orphan_series_promote_is_srcpage_driven]] の実例)。
5. 副次: 桧山智幸(キャラクターデザイン原案)が新装版頁の著者に writer_artist で混入 / 2017新装版『鎧闘神戦記』(9784063932720)が未掲載 / 全頁 magazine 空。

## 決め手の証拠 = ★楽天 itemCaption(講談社の公式文言)
「ボンボンKCで特別版を含めた全13巻が刊行された『騎士ガンダム物語』が全9巻の新装版で再登場」「エルガの妖怪編=特別版1巻2話〜3巻1話」「機甲神伝説・上=1巻1話〜2巻2話」「初単行本化」等、**巻↔新装版の収録対応が caption に全部書いてある**。Wikipedia本体記事には書誌節が無く(『SDガンダム外伝』はリダイレクト)、各編記事の「漫画版」節は連載誌・期間のみ。**新装版の帰属判定は楽天captionを先に読む**。

## 適用(王様の仕立て屋の頁分割手順 [[ousama_shitateya_4part_split]] を再利用)
- edition-canonical 8本: 原版=standard(講談社コミックスボンボン) + `extra_editions`(type=shinsoban, label「新装版(KCDX 2015/2017)」, imprint=KCDX, volume_label=編名/上下)。`suppress_types: [shinsoban]`。
- 新頁2: `naito-gundam-story-tokubetsuban`(特別版 全3巻+新装版2冊。**番外編=別内容=別頁** の2026-06-08方針④) / `esudii-gundam-retsuden-gundam-powers`(パワーズ=当て字読み採用)。stub は `_skey` を親(qid:Q11277743|name:騎士ガンダム物語)/種2 sid 132427 のキーに結線、edition-overrides に title/kana/romaji/years/`anilist:false`/`subtitle:""`、status-corrections(completed)、magazine-corrections(comic-bonbon / **deluxe-bonbon は data/magazines.yml に新設** → .preview-data へも複製)、genre-append(列伝=空だったので fantasy/action, provisional維持)。
- 聖伝 canonical は旧 `versions[]`(刷タブ)→ `extra_editions`(別editionタブ)へ。**冊数違い(3↔2)は刷タブでなく版タブ**(2026-07-08ルール)。
- drop 5頁 → page-dedup.yml + `_redirects` + slug-aliases。★既存の「旧romaji→drop頁」5行も最終行先へ張替([[drop_page_redirect_chain]])。**次の週次で `_r2-sync.py --prune`**(R2上の実フォルダ5つが孤児になる)。
- catch/synopsis は drop頁のものを原版頁(機甲神/黄金神話)へ slug キーで移設(純粋追加)。

## 検算
8頁: 本編10+新装7 / 特別版3+2 / 機甲神3+2 / 魔龍2+1 / 黄金3+2 / 鎧闘神2+1 / 聖伝3+2 / 列伝1 = **48 ISBN = NDL29行+楽天キャッシュで全件題・日付一致**、頁間ISBN重複0、`_check-edition-canonical.py` 異常0。KPC(2004コンビニ版4冊)と講談社のテレビ絵本は非掲載(方針どおり)。

## 一般化(同型の見つけ方)
- 種2で **同qid×題prefix共通×各1巻×extra=1** の series が連番 sid で並ぶ = 「新装版が編ごとに割れた」署名。`_exists.py --title` で原版頁があるなら版タブ統合候補。
- 原版頁の種2 edition に **同番号の別ISBN(日付が本編と交互)** が居る = 番外編/特別版の衝突。楽天題で「（特別版 N）」等が判明する。
