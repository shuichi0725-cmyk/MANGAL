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

注: SEPARATE = merge せず各作品に固有slug(別ページ)。 DEFER = 確証不足で保留(分離のまま)。
適用: `_apply-merge-A.py` / `_apply-merge-A2.py`。
