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

## ★③の精緻化(2026-07-08 ユーザ確定・重要)
「アンソロジーだから排除」は**誤り**。正しくは:
- **アンソロジーそのものは排除理由でない**。**纏められる(1作品/1シリーズに正しく統合できる)なら掲載してよい**。
- 排除するのは**「纏められないもの」**(散在して1頁にできない・実題不明・過統合しか手がない)。
- ★**雑誌(定期刊行)は纏められても排除**。号数=巻でない。実話系4コマ雑誌(ちび本当にあった/スゴ盛=芳文社・確定drop済)がこの型。判定=TinyFish search+Wikipedia「漫画雑誌一覧」+版元ドットコム「雑誌扱」。
- 帰結(2026-07-08 REVIEW36再分類): X-MEN竹書房(全13巻)/テイルズ プレミアムストーリーズ(全6巻)/艦これ4コマ/NHKその時歴史コミック版 = **纏められるアンソロ series → KEEP(統合)**。コミックチューリップ(ピラミッド社・漫画雑誌一覧掲載) = **雑誌疑い→排除**。詳細=docs/isbn-dup-review-36-2026-07-08.md。
- 判定フロー: (1)雑誌か? → Yes=排除 (2)No: 纏められるか(coherent series・実題確定・全巻構造有)? → Yes=統合してKEEP / No=排除。

## 適用
- 除外判断は ①→②→③ の順で。成年疑いは最優先で潰す。
- title==著者名の壊れレコード([[volgap_per_case_cleanup_state]]の派生で発掘した79件)の大半は②コンビニ廉価再録+①成年selection。正規は小学館フラワーコミックスマスターピーシーズ(夜明け型・作品タイトル有)のみ。


## 2026-07-02 コンビニremixの系統漏れ64頁を根治(ユーザ発見=鳥山明○作劇場「改」)
- ★dropパターン「ジャンプremix」(カナ+latin混合1種)だけでは**latin variant 9種を素通し**: Shueisha jump remix/ガンガンコミックスremix/G fantasy comics remix/Ganganwing comics remix/Shueisya girls remix/My first big special remix/MyBestRemix/バーズコミックス リミックス等。
- 恒久修正: `DROP_IMPRINT_LOWER_PATTERNS`に**"remix"**追加(case-insens・種2実測で全variantコンビニ再録確認・正規版に'remix'無し)+`DROP_IMPRINT_PATTERNS`に**「リミックス」**。
- 実害: remix専用54頁(こち亀年度別コンビニ本'76-'2000系14頁/鳥山明○作劇場改/ベスト・オブ・手塚治虫/必殺仕置長屋等)=non-manga-drop 55キーでdrop。混在11頁(魁男塾/パタリロ/狂四郎2030/隠密剣士等)=remix版除去済。**remix漏れ0確認**。
- ★教訓: imprintフィルタは**カナ/latin/大小文字のvariant全部**を種2実測で洗ってから書く。単一表記のパターンは必ず漏れる。

- ★remix除去後の正規版置き換え(2026-07-02完了): 隠密剣士v3=auto種4のtype誤記(standard→deluxe・JC-DX連番で確定)/忍空2nd=JC干支忍編2021全5追加/Golden boy=BJ標準10冊完成/パタリロ=pre-ISBN 8巻に再版ISBN補完(書影104/104化)/コドク=版分離(ソニマガBCDX2000全3+幻冬舎新装上下2016+文庫)。**情事の達人=NDL悉皆で正規版が存在しない**(双葉文庫自選名作集+白泉社リミックスのみ)=そのまま。★教訓: pre-ISBN巻は再版ISBN補完で書影が付く/type誤記はauto/offset種4も疑う。
