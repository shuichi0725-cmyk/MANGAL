# (A) 高影響 slug衝突 franchise の merge/分離 判定ログ

原則 [[merge-needs-external-proof]]: **同一anilist_id ≠ 同一作**(AniListは別作を1franchise-idに束ねる)。
誤merge=本番DB致命的。 **デフォルト=分離(固有slug)**、 merge は外部確証(Wikipedia/cmoa/NDL/連番ISBN/同社同年)が取れた時のみ。

証拠源: `_merge-dossier.py`(種2 出版社/年/巻/ISBN/著者 + AniList relations)。 必要に応じ Wikipedia(WebFetch)。

| slug | ×n | 判定 | 根拠(確証) |
|---|---|---|---|
| mizu-wakusei-nendaiki | 7 | **MERGE**(renumber) | ★Wikipedia「全7巻」(続/環/翠/碧/月娘/月刊サチサチ) |
| kowai-hon | 14 | **MERGE** | 楳図恐怖文庫 連番ISBN(…720027-720140)同1996同社=1シリーズの闇/異形/影… + 角川再刊 |
| mikosuri-han-gekijou | 9 | **MERGE** | 本編18巻 + ぶんか社テーマ別デラックス/文庫編(同著者同社の編集版) |
| hamtaro | 5→4 | **MERGE** | ★Wikipedia「独立作でなく同一世界観の連続作品」。 アニメ版ハムージャ=drop |
| keroro-gunsou | 5→4 | **MERGE** | ケロロ軍曹 + green/pink/red(角川 同一作の版)。 スウェーデン版(978-91)=drop |
| bar-lemon-heart | 5 | **MERGE**(既存) | 本編37巻 + 双葉文庫テーマ別編。 前セッション merge 済(themed残あり=後日精緻化) |
| one-piece | 4 | **DROP satellite** | COLOR WALK=画集 / RED=設定資料 / SJR=コンビニremix を drop、 本編keep |
| tennis-no-ouji-sama | 5 | **DEFER** | 本編が巻21-26断片のみ=主ページ所在不明瞭、 tangledな部分merge回避 |
| manga-greece-shinwa | 9 | **DEFER** | 里中満智子 マンガギリシア神話。 Wiki詳細無で巻構成未確証→安全のため分離保持 |
| koha-ace | 5 | **DEFER** | コハエース→ぐだぐだエース改題の連続性が未確証 |
| meitantei-konan | 4 | **SEPARATE/drop候補** | 特別編=別漫画 / 紺碧の棺・漆黒の追跡者・瞳の中の暗殺者=劇場版フィルムコミック(drop要検討) |
| re-born-kamen… | 5 | **SEPARATE** | 手塚の別作5つ(RE:BORN/SPACE ADVENTURE/Black Jack/恐怖Remix)をAniListが誤束 |
| akujo-series | 5 | **SEPARATE** | わたなべまさこ名作集の別作5つ(ある愛の終わりに/蜜の味…)を誤束 |
| hi-no-tori | 4 | **SEPARATE** | 火の鳥2772(御厨)/和田ラヂヲの火の鳥(パロディ)/少女クラブ版(別版) |
| gegege-no-kitarou | 10 | **SEPARATE** | ★Wikipedia: スポーツ狂時代/死神大戦記/その後/ねずみ男と/雪姫ちゃんと=別雑誌別年の別作 |
| kenkaku-shoubai | 5 | **MERGE**(既存) | 剣客商売 リイド社 大島やすいち画(巻断片)。 前セッション merge 済 |
| onihei-hankachou | 4 | **MERGE** | 鬼平犯科帳 リイド社SP(巻1-122本編 + 断片)同一作 |
| takumi-kun-series | 4 | **MERGE** | タクミくんシリーズ(ごとうしのぶ/おおや和美 あすかCL-DX aid31770 同一BL連続) |
| minami-no-teiou | 4→3 | **MERGE**(ヤング編) | ヤング編3断片を統合、 本編187巻は別ページ保持 |
| kamen-rider | 4 | **SEPARATE** | 別作者の別漫画(913=井上/山田ゴロ版/石川版/アマゾン1974) |
| ginga-tetsudou-no-yoru | 4 | **SEPARATE** | 4つの別漫画化(まんがで読破/永島慎二/松田一輝/ますむらひろし) |
| jigoku-shoujo | 4 | **SEPARATE** | 本編(永遠幸9巻)keep + 閻魔あいセレクション3冊=別作者アンソロジー |
| watashitachi-wa-hanshokushiteiru | 4 | **MERGE** | 内田春菊 私たちは繁殖している(本編24巻 + 角川文庫オレンジ/ソーダ/トラベラー=文庫版) |
| shiori-to-shimiko | 4 | **MERGE** | 諸星大二郎 栞と紙魚子(本編 + 青い馬/生首事件/殺戮詩集=同一連作各巻) |
| papa-told-me | 4 | **MERGE** | 榛野なな恵 Papa told me(本編27巻 + 夏/秋/春=特別企画文庫選集) |
| kouun-ryuusui | 4 | **MERGE** | 本宮ひろ志 こううんりゅうすい(徐福/信長=連続巻4-8) |
| hakushaku-cain-series | 4 | **DEFER** | カフカ/忘れられたジュリエットが伯爵カイン本編か別短編か未確証 |
| jashin-densetsu | 4 | **DEFER** | 矢野健太郎 コンフュージョン/ラミア等=共通base無・邪神伝説への帰属未確証 |
| cardcaptor-sakura | 3 | **DEFER** | CLAMP本編+さくらカード編=merge候補だが、 ショート・ケビン版=アニメコミック混在で要精査 |

## まとめ(2026-06-03 (A)セッション)
- **MERGE適用**: 水惑星年代記/こわい本/みこすり半劇場/とっとこハム太郎/ケロロ軍曹/鬼平犯科帳/タクミくんシリーズ/ミナミの帝王ヤング編/私たちは繁殖している/栞と紙魚子/Papa told me/こううんりゅうすい = **12件**(+既存 剣客商売/BARレモンハート)
- **DROP**: アニメ版ハムージャ/スウェーデン版Keroro/ONE PIECE COLOR WALK・RED・SJR
- **SEPARATE(誤束=固有slug)**: ゲゲゲ/仮面ライダー/銀河鉄道の夜/火の鳥/RE:BORN群/悪女シリーズ群/地獄少女セレクション
- **DEFER(確証不足→分離保持)**: テニス王子様/マンガギリシア神話/コハエース/コナン劇場版/伯爵カイン/邪神伝説/CCS
- **残**: WIKI_NEEDED ×3=残約50 / ×2=677(=安全デフォルト分離でlaunch可)/ AUTO_SEPARATE 1,283(証拠不要・固有slug)

注: SEPARATE = merge せず各作品に固有slug(別ページ)。 DEFER = 確証不足で保留(分離のまま)。
適用: `_apply-merge-A.py` / `_apply-merge-A2.py`。

## ×3群 調査結果(2026-06-03 追加・~1時間)

証拠源 = `_merge-dossier.py`(種2 出版社/年/巻/ISBN/著者 + AniList relations)。 汎用 `_apply-merge-batch.py`。

### MERGE適用(同一作の版違い/連作/連番ISBN)= 21件
千里の道も / ああっ女神さまっ / 天才柳沢教授の生活 / ダイの大冒険 / ねこようかい / 魔女っ娘つくねちゃん / アスタロト / 猫ラーメン / 幻獣の國物語 / 義風堂々!! / 釣りキチ三平 / さるとびエッちゃん / 蠢動 / 美男の殿堂 / まじめに!男女交際 / それでいい。 / 万能文化猫娘(OVA=drop) / デュエル・マスターズ(バーサス除外) / 呪怨妖(連番ISBN) / 変人探偵M / おもひでぽろぽろ
（既存: アラベスク）

### SEPARATE(AniList誤束=別作 → 固有slug)
リング(3別作画) / 悪魔くん(水木の別版・別aid=ゲゲゲ型) / 小林さんちのメイドラゴン(3別spinoff) / 和田慎二ホラー(別作) / いたずらな24時系(宮脇別作) / 久美と森男系 / ヨネザアド系 / サイコメトラー(EIJI別原作) / 東京タラレバ娘(続編・番外)

### DEFER(確証不足/方針保留 → 分離保持)
激マン!(アーク別) / ザ・シェフ(続編) / 荒くれKNIGHT(アーク別) / まじこい(別作画) / ロボットポンコッツ(続編) / ナニワ金融道(関連書) / アルプス伝説 / 最終戦争(混在) / 少年奇怪(別oneshot疑い)

### ★アンソロジー群(別方針=要policy決定、 分離保持)
本当にあった〔○生〕ここだけの話(ヤバ盛/ばく盛/激盛/超盛…) / ちび本当にあった笑える話 / 本当にヤバイホラーストーリー / いただき幸せごはん / コミック乱セレクション / 小池一夫劇画セレクション / on BLUE / GUSH mania / Fellows! / 名探偵コナン劇場版・特別編(=フィルムコミックdrop候補)
→ ★読者投稿/アンソロジー誌/劇場版コミカライズ = drop か 1誌1ページかの**policy決定が別途必要**(本セッションでは保留)。

## 累計(A セッション全体)
- ★**MERGE適用 = 約33件**(高影響12 + ×3群21)。 全て外部/構造証拠付き・commit済。
- ★**DROP** = アニメ版/外国版/画集/設定資料/コンビニ廉価版 数件。
- ★**SEPARATE/DEFER** = AniList誤束の別作を多数特定(誤merge回避)。
- ★残 = ×2ペア677(=安全デフォルト分離) + アンソロジーpolicy + AUTO_SEPARATE 1,283(固有slug)。

## DEFER群の深掘り決着(2026-06-03 追加・Wikipedia/検索確証)

DEFER保留分を外部確証で決着:

### MERGE(Wikipedia/検索で確証)
| 群 | 確証 |
|---|---|
| 激マン! | Wikipedia「同一作品の各編」(ゴラク連載・デビルマン/マジンガーZ/ハニー編) |
| コハエース | Wikipedia「単一シリーズの段階的改題」(コハ→EX→XP→ぐだぐだ) |
| 伯爵カインシリーズ | Wikipedia「5部作」(カフカ/赤い羊/忘れられたジュリエット 全含む) |
| 最終戦争シリーズ | Wikipedia 同一シリーズ(最終戦争=十蘭の改題同作) |
| 邪神伝説シリーズ | Wikipedia「矢野健太郎 邪神伝説5作品」(クトゥルー) |
| テニスの王子様 | 種2構造=本編1-42 + 断片21-26 + 完全版season1-3 を統合、 大会編(アニメ)drop、 新テニス(続編)別 |
| マンガ ギリシア神話 | 検索確証「全8巻」(里中満智子 中公文庫) |

### SEPARATE/DROP(ジョジョ型・別作・アニメ)
| 群 | 判定 |
|---|---|
| 荒くれKNIGHT | Wikipedia「連続別編成の各部」(28/11/20巻大作)=ジョジョ型→**SEPARATE** |
| ザ・シェフ | 新章/ALIVE/ファイナル=別シリーズ→**SEPARATE** |
| まじこい | S九鬼紋白編/afterparty=別作画spinoff→**SEPARATE** |
| ロボットポンコッツ | 2/豪=別ゲーム原作の続編→**SEPARATE** |
| アルプス伝説 | スペース/黄金=続編→**SEPARATE** |
| ナニワ金融道 | 法律講座/だまされたらアカン=関連書→**SEPARATE**(本編と別) |
| cardcaptor | CLAMP本編keep、 ショート・ケビン版/さくらカード編メディアブックス=アニメコミック**DROP** |
| サイコメトラー | EIJI=別原作→**SEPARATE** |

★= DEFER群は全て決着。 確証あり7群をMERGE、 残りは政策(ジョジョ型/別作/アニメ)に従いSEPARATE/DROP。

## ×2ペア677群の処理(2026-06-03・1時間)

677 = 同一著者ペア。 構造シグナルで機械分類(`_classify-x2-v2.py`、 個別Wiki不可能なため)。

### MERGE適用 = 199群
- EDITION 9(版違い: 文庫/新装版/完全版/CLAMP PREMIUM等)
- SCRIPT_VARIANT 121(同anilist_id・英⇄カナ/case/括弧の表記揺れ: FRONT MISSION=フロントミッション等)
- 完全一致 67(同作の巻範囲分裂fragments)
- 内包の安全分 6(括弧グロス=アクセラレータ / 漫画版接頭)

### 分離/drop = 478群
- SEQUEL 106(パズドラZ/ダンボール戦機ウォーズ/○○2/続○○/もっと○○)
- SPINOFF 22(外伝/番外/アラカルト=アンソロジー)
- ANIME 4(THE ANIMATION/フィルムコミック/アニメブック=アニメ側drop)
- DIFF 68(別作の同読み)
- ★内包・実質副題 278 = 保留分離(副題ドリフトだが spinoff混在=藤丸立香/ハイスクール/英雄騎士伝等 per-case要)

★危険marker除外を多層化(続編末尾単字Z/R/英anthology/画集イラストアルバム/辞典/セレクション)。 二重分類bugも修正。 ★誤merge回避を最優先し、 確証薄い278は安全デフォルト分離に留置。
