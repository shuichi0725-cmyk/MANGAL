---
name: exclusion_priority_policy
description: 【最重要方針】掲載除外の優先度=①成年誌(ダントツ)②コンビニ本③纏められないもの(アンソロ>教育)。汚染源の順位
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1c2cd3c3-946e-46bd-ad68-956f057eed08
---

ユーザ確定の**掲載除外の優先度**(2026-07-01)。「何を出さないか」の判断はこの順で厳しく。

## ①成年誌 = ダントツでダメ(最優先排除)
- 成年(アダルト)コンテンツが**一番の汚染源**。誤って一般表示に漏れるのが最悪。
- 判定は [[adult_judgment_architecture]]。成年imprint例(今回発掘): ピクト・コミックスdeluxe / Philippe Comics Deluxe / Poe backs(BL) / K-book comics / mimi.comics / Clapコミックス / ムーグコミックス / the best best 等の単著成年/BLレーベル。
- ★MANGALは成年を「含めてadult_us/geoで出し分け」設計だが、**未フラグの成年漏れ=最悪**。成年疑いは必ずadult判定を確認。

## ②コンビニ本 = 次にダメ
- **なぜ悪い**: (a)**本編の誤り**を起こす(廉価再録が本編ページに混入/別ISBNで別クラスタ化) (b)正しく出しても**無駄に増えて見づらい**(同じ作品の廉価版が乱立)。
- コンビニ/廉価再録 imprint例(今回発掘): **日本漫画家大全**(双葉社コンビニ廉価再録・18件) / **BIG COMICS SPECIAL**(小学館著者名tribute再録・手塚/藤子/水木等) / **OKS comix作家selection** / **同人誌ベストセレクション** / **the best best / Ap the best** / 原寸大漫画館 / まんだらけliveコミックコレクション。
- ★狭いコンビニ専用labelはimprint dropでOK。BIG COMICS SPECIAL等**広いlabelは正規巻も含む**のでseries_key単位drop(imprint一括は誤爆)。

## ③纏められないもの = 次(アンソロジー/教育系)
- **私(AI)が正しく統合(merge)できない群**が汚染の元。現状の弱点。
- **教育マンガ** = 比較的**纏められる**ので出している(年代版分離はNDL補完で対応済 [[edu_multiedition_disentangle_ndl]])。
- **アンソロジー** = 纏められるなら可だが**大体過統合で汚染**される([[anthology_consolidation_state]]の3ガードでも危険)。過統合するくらいなら出さない方が安全。
- ★原則: **過統合汚染 > 未収録**。確証なく統合しない([[merge_needs_external_proof]] [[feedback_dont_repeat_regrouping_error]])。

## 適用
- 除外判断は ①→②→③ の順で。成年疑いは最優先で潰す。
- title==著者名の壊れレコード([[volgap_per_case_cleanup_state]]の派生で発掘した79件)の大半は②コンビニ廉価再録+①成年selection。正規は小学館フラワーコミックスマスターピーシーズ(夜明け型・作品タイトル有)のみ。


## 2026-07-02 コンビニremixの系統漏れ64頁を根治(ユーザ発見=鳥山明○作劇場「改」)
- ★dropパターン「ジャンプremix」(カナ+latin混合1種)だけでは**latin variant 9種を素通し**: Shueisha jump remix/ガンガンコミックスremix/G fantasy comics remix/Ganganwing comics remix/Shueisya girls remix/My first big special remix/MyBestRemix/バーズコミックス リミックス等。
- 恒久修正: `DROP_IMPRINT_LOWER_PATTERNS`に**"remix"**追加(case-insens・種2実測で全variantコンビニ再録確認・正規版に'remix'無し)+`DROP_IMPRINT_PATTERNS`に**「リミックス」**。
- 実害: remix専用54頁(こち亀年度別コンビニ本'76-'2000系14頁/鳥山明○作劇場改/ベスト・オブ・手塚治虫/必殺仕置長屋等)=non-manga-drop 55キーでdrop。混在11頁(魁男塾/パタリロ/狂四郎2030/隠密剣士等)=remix版除去済。**remix漏れ0確認**。
- ★教訓: imprintフィルタは**カナ/latin/大小文字のvariant全部**を種2実測で洗ってから書く。単一表記のパターンは必ず漏れる。
