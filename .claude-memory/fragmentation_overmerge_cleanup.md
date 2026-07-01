---
name: fragmentation_overmerge_cleanup
description: 本番の分裂(重複ページ)と過剰統合(別作が同ページ)の検出法と是正進捗。種2照合で真の所属を確定。残=巻ISBN除去機構
metadata: 
  node_type: memory
  type: project
  originSessionId: 40db3460-5533-4358-8d06-8214ea9ecaea
---

本番manga.v2の地道クリーンアップ(2026-06-26)。**分裂**(同一作が複数ページ)と**過剰統合**(別作が1ページに混在)を全DBスキャン。

## 検出法
索引で**同題(NFKC正規化・副題strip)＋著者共有**のペア→候補。各ペアの全volume isbn13集合を比較: **包含(⊂)=重複/部分重複=分裂/disjoint=同名異作**。★ISBN包含だけだと別作混入を見逃すので**著者＋種2照合で最終確認必須**([[feedback_dont_repeat_regrouping_error]])。

## ✅ 適用済(可逆=.cache/*-bak)
- **分裂dedup 11面→統合**(commit 717e449d3): 日本の歴史(角川2015・同ISBN15巻の量産9面→1)/幻獣の國物語(猫十字社=Team猫十字社表記揺れ3→1)/ウスズミの果て(同岩宗治生4⊂5・完全版をclean slugへ)。
- **過剰統合のページdrop 3件**(commit 48ec22ffb): Boys be 2nd season(33巻完全複製→boys-be)/ring-suzuki-2005(中身が稲垣版sid24814の重複→ring-inagaki-1999)/doraemon-1994(声優エッセイ文庫を藤子F誤ラベルの非漫画→doraemon)。
- 機構: page-dedup.yml(drop slug)+slug-overrides+slug-aliases+_redirects。

## ✅巻ISBN除去機構 構築済(2026-06-26 commit cd4f0c7a2)
**page-dedupは丸ごとdropのみ**だったので、slug単位で混入巻を除去する機構を新設。
- seed=`data/seeds/volume-exclude.yml`(`excludes: [{slug, isbn13, reason}]`)。
- promote 3箇所結線(loader/build_yml後の適用/集計print)。★グローバル除外(art-book-exclude-isbn.yml)と違い**slug単位=同ISBNが正しい別ページには残る**([[feedback_dont_repeat_regrouping_error]])。
- 適用済2件: 気分はもう戦争`kibun-wa-mou-sensou-2002`から大友版ISBN`9784047133877`(sid127576)除去(2→1巻) / `doraemon`本体から声優エッセイ文庫`9784091940018`(sid142928・非漫画)除去(29→28巻)。即時yml編集(backup=.cache/volexclude-bak)+seed恒久。

## ★残(裁定根拠=docs/overmerge-6-investigation.md。種2 sid/ISBN確定済)
- **銀河鉄道の夜**: 学研系別翻案(木野陽sid164869`...39201`/Teamバンミカスsid164868`...57779`)が松田一輝版/ますむら版に混入。除去は volume-exclude で可だが、松田版の正ISBN(現2巻は他者版)をNDL/楽天で確証してから再構成(空ページ化を避ける)。
- **ドラえもん著者欄**: 「朝松健/大山のぶ代」汚染剥がし(エッセイ文庫由来)=sid34088巨大クラスタ精査と併せて。
- エッセイ文庫sid142928の14 ISBNが他の本編にも混入してないか横展開確認。
- 魔法科高校の劣等生=ページ間共有ISBNゼロ＝**スキャン誤検出**(原作者佐島勤共有で誤flag)。ただし各ページ内に別アーク(よんこま/来訪者編等)同居の別問題。
- 別件: 連結slug595件(ラノベ文章題の未ハイフン化)=語分割の大仕事・価値は見た目。
