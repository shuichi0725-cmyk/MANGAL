---
name: mangal-inclusion-scope
description: 掲載scope=日本出版の漫画(原産問わず)。韓国manhwa日本語版も含む。外国語版書誌のみdrop。EMPTY slugは真作でもありうる
metadata: 
  node_type: memory
  type: project
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

MANGAL の掲載「対象」scope の確定判断 (= 2026-06-02、 ユーザ確認)。

**含める**: ★**日本で出版された漫画**(日本原産に限らない)。 ★**韓国manhwa/中華manhuaの日本語版(正規出版)も掲載対象**。 例=復讐の毒鼓(全6巻=本編)+ 復讐の毒鼓REWIND(全8巻=後から出た前日譚)、 KADOKAWA刊、 作=Meen X Baekdoo。 ★manhwaを一律dropしない。

**除外**: ★**外国語版の書誌が紛れ込んだorphan記録のみ**(= translator credit行がtitleになったもの。 スウェーデン語版ONE PIECE/タンタン/仏BD/はだしのゲン外国版等)。 全76,435中わずか**17件**、 うち明確14件を `data/seeds/non-manga-drop.yml` でdrop(series_key除外、 種2/種3不変・可逆)。 ★「日本で売られる日本語manhwa」と「日本作品の非日本語外国版」は別物。

**EMPTY slug ≠ junk**: ★title_kana欠落(orphan101でMADB読み未伝播)だと真の作品でもslug生成がEMPTYになる。 「上全」(じょうぜん=黄助BL/ビーボーイ2023)/「Page 1」(ぺーじわん=スタジオ・バトル1986)は ★**MADB上 実在**(rdfs:label+ja-hrkt読み有)。 = EMPTYは「外国クレジット行junkの炙り出し」に有用だが、 真作はkana補完で救済する(drop前に必ずMADB生データ確認)。

関連: [[madb_data_acquisition]](MADB生=metadata101.json)、 slug first-pass(`_gen-slugs-firstpass.py`)、 CLAUDE.md「掲載対象 scope」節。
