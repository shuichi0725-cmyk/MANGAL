# ISBN誤共有 un-merge 監査台帳 (= 後追い用の人手可読ログ)

機械可読ログ = `data/seeds/unmerge-changelog.jsonl` / 本表 = その人手可読版。
**全操作は可逆** (= `.cache/*-bak-*` に before yml を退避、`dup-merge-alias.yml` で alias 逆引き)。
種2 sqlite は全工程で**不変**。日付 = JST 2026-06-20。

## 操作種別

| code | 意味 | 戻し方 |
|---|---|---|
| dedup/alias | 重複/別名ページを canonical へ統合・除去 | alias行削除 + backupから復元 |
| de-interleave | 共有ISBN束を真題著者で各作へ振分(両作生存) | backupから復元 |
| re-point | 誤ISBNを剥がし自前の真ISBNへ差替 | backupから復元 |
| strip→needs-content | 真ISBN不明で除去しqueue化 | backupから復元 |
| restore | needs-content等を真ISBNで復元 | backupから復元 |
| drop | 掲載対象外と裁定し除去のまま | (意図的除去) |

---

## ① series-dedup (commit `7a3eac20b`, bak `unmerge-bak-20260620-083428`)

| slug(drop) | → canonical | 根拠 |
|---|---|---|
| aporon-no-kanashimi 他6(eiyuu-herakuresu/higeki-no-ou-oidipusu/meikai-no-orufeusu/odeyusseusu-no-koukai/oryunposu-no-kamigami/toroi-no-mokuba) | manga-girishia-shinwa | マンガギリシア神話=8エントリ重複→1 |
| princess | idol-sousei-densetsu-princess | 美少女プリンセス重複 |

## ② de-interleave (commit `7a3eac20b`, 同bak)

| 群 | 振分(各作の巻数) | 根拠 |
|---|---|---|
| cue-2004 / cue | 村上3 / 花見沢1 | 種1/楽天の真題著者 |
| shinpika-mizuki-shigeru-den / watashi-ha-gegege | 各1 | 同上 |
| besuteia / ryuugetsushou | ベスティア / 流月抄3 | 同上 |
| akai-hitsuji-no-kokuin / hakushaku-cain / kafuka / wasure-rareta-juliet | 赤い羊1 / 伯爵カイン6 / カフカ=ISBN無→needs-content / 忘れジュリ1 | 同上 |

## ③ 誤側7件分岐 (commit `c43547b09`, bak `unmerge3-bak-20260620-103905`)

| slug | 操作 | before → after | 根拠 |
|---|---|---|---|
| kurotokage-2019 (森下裕美) | re-point | 講談社黒とかげISBN → 9784575945614(双葉社2019) | 種1[作画]森下裕美・slug年一致 |
| gift-2012 (塩森恵子) | re-point | 講談社GiftISBN → 9784575334906(双葉社2012) | 種1[著]塩森恵子・slug年一致 |
| hiyoko-brand (こばやしひよこ) | dedup/alias | → oku-sama-wa-joshikousei | 同著者+cm104題一致+愛蔵版13ISBN同一 |
| 24colors | strip→needs | 麻生歩COLORS ISBN剥がし | 別著者(千葉コズエ)・真ISBN無→queue |
| venus-2015 | strip→needs | 関口シュンISBN剥がし | 別著者(麻生歩)・真ISBN無→queue |
| gift-2006 | strip→needs | 秋本尚美ISBN剥がし | 別著者(ユキヲ)・真ISBN無→queue |
| fire-emblem-thracia-776-2000 | strip→needs | たかなぎ優名ISBN剥がし | 別著者(日野慎之助)・真ISBN無→queue |

## ④ 残存共有2件 (commit `f4c8c4230`, bak `unmerge4-bak-20260620-115946`)

| slug | 操作 | before → after | 根拠 |
|---|---|---|---|
| colors-2001 (啄木鳥しんき) | re-point | 麻生歩COLORS3ISBN → 啄木鳥4巻(9784757705128/707054/708846/711716,エンターブレイン) | vol4=楽天確認/vol1-3=ユーザ調査+ISBN連番。qid(麻生歩疑い)clear |
| gift-ichinose-2015 (一ノ瀬ゆま) | re-point | 秋本尚美Gift2ISBN → 一ノ瀬上中下3巻(9784344834798/839205/843585,幻冬舎) | 種1で[著]一ノ瀬確認。anilist106164等enrichは本人=保持 |

※訂正: gift-2009(山田J太)/gift-2002(中村かなこ)は汚染なしと判明(resolve-masterが古snapshot)。詳細=`unmerge4-residual-flag.tsv`

## ⑤ needs-content 5件裁定 (commit `e26392225`/`13e0da4fc`, bak `unmerge5-bak-20260620-121144`)

| slug | 操作 | 真の作品 / 正ISBN | 根拠 |
|---|---|---|---|
| 24colors | restore | 24Colors〜初恋のパレット/千葉コズエ / 9784091316073(小学館2008) | NDL+AniList35686(正マッチ=enrich保持) |
| venus-2015 | restore | ヴィーナス:禁じられた危険なキス/麻生歩 / 9784776739586(宙出版2015) | NDL・slug年一致 |
| fire-emblem-thracia-776-2000 | restore | FEトラキア776/日野慎之助 / 9784757700321(エンターブレイン2000) | NDL(たかなぎ版と別作)・誤AniList35619 clear |
| kafuka | alias | → hakushaku-cain | AniList30885=伯爵カインシリーズ全5巻の一編 |
| gift-2006 | **drop(成年)** | Gift/東山翔(官能2007) | AniList55445=別著者の成年作。ユーザ裁定でドロップ確定 |

詳細裁定=`unmerge-needs-content-resolved.tsv`

---

## A: 同一ISBN複数作品(T3核心) — 分析のみ (commit `48ea274b7`, **未適用**)

- Phase1分類(676slug): CLEAN_owner296 / ALL_WRONG164 / UNKNOWN_only162(多くno_yml=既処理) / MIXED_deinterleave41 / WRONG_plus_unknown13
- Phase2(誤claim側 live218): **REPOINT41 / DEINTERLEAVE41 / STRIP・ALIAS136**
- Phase3 re-point proposal=dry-run。★自動番号付けにノイズ多数(mahouka-2025=53巻過収集等)→**bulk適用は危険、小バッチ人手vetting要**
- artifacts: `shared-isbn-classified.tsv` / `shared-isbn-actions.tsv` / `shared-isbn-repoint-proposal.tsv`
- **次の適用はこの表に追記してから実施** (= 段1:単巻16 → 段2:複数巻25 → 段3:strip/alias136 → 段4:deinterleave41)

### A 適用ログ (= ここに段ごと追記していく)

**★重要(2026-06-20)**: resolve-master.tsv は **6/18-19 の t3-fix/torichigae/special-edition 修正より前の古snapshot**。
統合台帳 operations.jsonl で「既処理か」を必ず確認 → 怪しければ実 yml を見る、で**済み作業の上書きを回避**。
(例: samurai-soldier は台帳上 t3-fix 済=現在 山本隆一郎の正26巻。stale proposal の「26→1」を信じれば正巻を破壊していた)

| 段 | 日付 | slug | 操作 | before→after | 根拠 | bak |
|---|---|---|---|---|---|---|
| 1 | 06-20 | eden-sakurazawa-2014 | strip誤著者巻 | 岡田俊平のエデン除去 → 桜沢エリカ1巻 | 種1著者照合 | sharedisbn-step1-bak-20260620-143120 |
| 1 | 06-20 | snow | strip誤著者巻 | 藤谷コマキのスノウ除去 → 吉田優希1巻 | 種1著者照合 | 同上 |
| 1 | 06-20 | stand-up | strip誤著者巻 | 白虎丸のSTAND UP!2除去 → 板垣雅也2巻 | 種1/楽天著者照合 | 同上 |
| 1 | 06-20 | zero-matsumoto | strip誤著者巻 | 冬目景のZERO除去 → 松本大洋3巻 | 楽天著者照合 | 同上 |

**段1の保留**: reset(高橋ユキ標準+山本まゆり文庫の2著者混在+enrich疑義) / comic-higashino-keigo-mystery-2014(アンソロ) / tenyoritakaku(全巻別著者=要re-point) / koi-shita…(matcher誤判定=実は本人作) → 個別精査へ。
**段1で既処理判明(台帳ガード)**: blazblue/box-1991/face/face-2019/kirara-hiramatsu-1987/nito-monogatari/samurai-soldier/work-in (= t3-fix/torichigae/special-edition で6/18-19に修正済)。
**次**: 段1残(未スキャンの全REPOINT/STRIP母集団)は **resolve-master でなく台帳+実DB** で現状確認してから。

#### 段1拡大: reconcile(218候補を現yml+種1/楽天で再判定) → 別著者単巻strip 30件 (06-20)

`_sharedisbn_reconcile.py` で218候補の**現状**を判定: CLEAN_NOW91(既解決=stale確認) / SAFE_STRIP47 / REVIEW42(null・版混在) / REPOINT_full38(全巻別著者)。
SAFE_STRIP47のうち **wrong==1(別著者の単巻混入)30件**を異体字正規化チェック後にstrip適用(bak `sharedisbn-strip-batch-bak-20260620-144553`):
- blazblue/doll-1996/doll-2000/egao-no-yukue-2003/face-1992/get-azuma-1999/gifuu-doudou-naoe…/ginga-tetsudou…1992/gold-2004/hellhound-2018/in-hand/in-hand-2019/isekai…yoi-no-darou/joker-1998/joker-1998-2/joker-yamane-1997/koishita…aite-ga/koori-no-joou-2013/love-taishitsu/manga-grimm-douwa-2003/otome-wa-boku…/rinjou/s/samurai-7/shikei-shikkounin-mine-1984/step-mother/the-bokusaa/the-combat/the-konbatto/tsuukaa
- 各「本人巻own≥1 + 別著者1冊」を除去(例 blazblue=吉岡榊なのにアクシステムワクスのブレイブルー1冊)。

**★保留(wrong≥2のSAFE_STRIP17 = ペンネーム/異体字の誤判定リスク)**: pocket-monsters-special(真斗=山本サトシで55誤判定)/worst(髙橋ヒロシ vs 高橋ヒロシ異体字で27)/mahouka各/buyuden/sora-yori-takaku 等。**matcherの別名解決を入れるまで自動strip厳禁**。
**残**: REVIEW42(null/版混在=reset型) / REPOINT_full38(全巻別著者=自前ISBNへ要差替)。個別精査へ。

#### 段2: REPOINT_full 38をNDL一次調査 → 確定5件差替 (06-20)

`_repoint_ndl_investigate.py`(NDL SRU=絶版でも収録・著者ヨミでペンネーム裁定)で38件の自前ISBNを調査。
NDL自前ISBN vs 現ISBN突合で仕分け:
- **CLEAN_fp 6**(現ISBN=NDL自前=正しい、romaji/かな/ペンネーム誤判定): gurazeni-tokyo-doomuhen(森高夕次=コージィ城倉)/koi-shita/lastman/egao-no-yukue(SalaSharon=シャロンサラ)/koori-no-joou/ragunasenki → 無処理(一部NDL欠け巻=種4候補)
- **REPOINT確定5**(NDL著者×題で全巻照会・check-digit緑、clean stub差替): bak `sharedisbn-repoint-bak-20260620-145821`

| slug | 著者 | 誤(別著者) → 自前ISBN(NDL) |
|---|---|---|
| tenyoritakaku | 現津みかみ | 石川サブロウ天より高く → 9784832277687(芳文社2009) |
| catwalk | けろりん | 佐多ミサキ → 9784757720527(エンターブレイン2004) |
| comic-higashino-keigo-mystery-2014 | 松枝尚嗣 | 高柳衣良他 → 9784408174839(実業之日本社2014) |
| rocketman | 水木しげる | 加藤元浩 → 9784778031541(小学館クリエイティブ2010、大全集ノイズ除外) |
| crusader-kawaso-2002 | 河惣益巳 | 水縞トオル → 9784592172093(白泉社2002) |

**段2保留**: nein(有坂あこ=vol2不確実のstrip混在) / mahouka×2(franchise過収集30) / nhk-sono-toki(多著者アンソロ6) / gifuu-doudou(MIXED一部正)。
**未着手**: REPOINT_full の NO_OWN 22(NDLで自前無=ペンネーム未マッチ/著者unknown[ナウシカ宮崎駿・x-men]/外国[Vivés/LEEHYE manhwa]) + REVIEW42。

#### 段3: NDL著者ヨミで異体字/かな漢字を根治 → 別著者単巻strip 14件 (06-20)

未解決92slugの現ISBN579をNDL直引き(`_ndl_by_isbn.py`)し著者名+ヨミ取得→`_sharedisbn_ndl_classify.py`でヨミ照合再分類。
- **CLEAN 23**(誤判定が解消=現ISBN正しい): ★worst(髙橋ヒロシ=高橋の異体字)own33/buyuden own13/gundam-thunderbolt own26/ringo(こいおみなと=恋緒ミナト)/gurazeni-tokyo(コージィ城倉=森高夕次)/darker-than-black(岩原裕二)/es/hitorijime-my-hero 等 → 無処理(NDLが正と確認)。**ヨミ照合が異体字/ペンネーム誤判定を根治**。
- **STRIP適用14**(AI判断で真の別著者混入のみ。bak `sharedisbn-strip-batch-bak-20260620-151133`):
  eden-2021/gakkou-no-kaidan-koga-1994/last-order-2000/red-dragon/stand-up-yamakawa-2013/sora-yori-takaku(石川天より高く1除去・宮下26残)/joker-2012/fight-2000/hataraku-onee-san/majuugari/yume-de-aetara-1985(Hanako15除去・小椋1残)/hakkou-1985/isekai…yoinodarou/sp-2000(灰原5除去・国友2残)
- **★STRIP除外9(AI判断で保留)**: pocket-monsters-special(真斗=山本サトシのペンネーム→実CLEAN)/gifuu-doudou(原哲夫=正当原作)/mahouka×3(編別アーク=別作画)/x-men×3(海外Marvel+和訳翻案混在)/perman-fujiko-1979(藤子不二雄=藤子・F・不二雄)。ヨミでも解けない別名/共著/franchise=要個別。
**残**: STRIP_multied31(版混在=reset型) / REPOINT_full15(全巻別著者) / NO_OWN・REVIEW群。

#### 段4: REPOINT_full 15をAI判断で仕分け → NDL確定3件差替 (06-20)

- **CLEAN 2**(ペンネーム/romaji=実は正): gurazeni-pa-riiguhen(コージィ城倉=森高夕次)/hal-ayase-2017(hal=ハル) → 無処理
- **著者ラベル誤り3**(作品は正・著者欄のみ誤、ISBN保持で著者修正案件=別途author-fixへ): final-fantasy-lost-stranger(→亀屋樹/水瀬葉月)/kaze-no-tani-no-naushika-1984(→宮崎駿)/the-boxer(→JH manhwa)
- **REPOINT適用3**(NDL著者照会で自前ISBN確定・check-digit緑、bak `sharedisbn-repoint2-bak-20260620-151532`):
  to-heart-2(御形屋はるか)→9784840227742/235334/239011(メディアワークス3巻)/engage-watanabe-2009(渡辺瑞樹)→9784063494228/494327(講談社2巻)/nein(有坂あこ)→9784041050514(KADOKAWA)
- **保留5**(NDL著者照会不調=要web/深掘り): refrain-1988/joker-1998-3/work-in/meioukeikakuzeoraimaa/last-order-kazunari-2021
- **保留2**: x-men(海外Marvelスコープ)/nhk-sono-toki(多著者アンソロ)

#### 段5: STRIP_multied(版混在=reset型) own≥1の18件を版/巻単位strip (06-20)

NDL ISBN別著者で各版の巻を own/wrong 判定→別著者の版・巻を除去(空edition自動drop+renumber)。bak `sharedisbn-strip-batch-bak-20260620-151910`。
全18件AI確認で真の別著者混入: fire-emblem-1993(大沢美月のFE11除去・島田1残)/yume-de-aetara-2000(Hanako8除去・山花典之17残)/tempest-1993(阿仁谷ユイジ7除去・庄司1残)/kuro-1999(ソウマトウ5)/suikoden-2000(李志清5)/hayou-no-ken(松元陽3)/reset(山本まゆり3除去=段1保留分確定・高橋ユキ残)/joker(河野やす子/河奈マリオ2除去・道原かつみ10残)/k-shitsuki-1988(黒榮ゆい2)/sengoku-jieitai-2014(田辺節雄2)/aya(克亜樹)/cinderella-2004(森園みるく)/cool(桜沢エリカ)/ginga-tetsudou-no-yoru(古城武司版)/gold-1997(夢殿りさ)/kaleidoscope(米田仁士)/oz-itsuki-2004(刻夜セイゴ)/zero-yamazaki-2009(冬目景)。
**残STRIP_multied**: own0の13件(charisma-2/kuro/fire-emblem-nintendo-1996/nihonnorekishi系/gundam-wing系/yatsuhakamura系等)=全版別著者=REPOINT/著者fill行き。

#### A 累計(06-20時点)
strip 66(段1:34 / 段3:14 / 段5:18) + repoint 11(段2:5 / 段4:3 / 段4b:3) + CLEAN確認多数(段2:6 / 段3:23 / 段4:2) + 既処理判明91。
**残**: STRIP_multied own0=13 / 著者ラベル誤り3(author-fix) / REPOINT保留7 / NO_OWN・REVIEW群。台帳operations.jsonl=3,799操作。

#### 段6: アメコミdrop + アンソロ分割(NDC726.1/genre=漫画 手法) (06-20)

- **アメコミdrop 5**(ユーザ裁定): x-men(Marvel翻訳)+x-men-1994系4(竹書房和製X-MENアンソロ=Marvel IP)。american-comics-drop.tsv。
- **★NDLで漫画を権威判定する手法を確立**: NDC **726.1**(dcterms:subject) または **dcndl:genre=漫画**(ndlgft典拠)。古いレコードはNDC無でもgenreで判定可。小説(913.6)/画集(726.5系)/雑誌を除外。
- **エリアル(ARIEL)を3分割**(ユーザ裁定。同じ朝日ソノラマ内のシリーズ別。bak `ariel-split-bak-20260620-155833`):
  1. `ariel-comic`=ARIEL COMIC本編adaptation(鈴木雅久作画/笹本祐一原作、act.1-5: 9784257901136/143/167/174/198)。※エリアルコミック アンソロ全14巻+番外編2巻のうち6-14は絶版でNDL ISBN無→要補完(マンガ図書館Z等)
  2. `season-ariel-outer-story`=シーズン(西野司,1993-06,9784257901921)新規
  3. `konchi-koremata-eriaru`=こんちこれまたえりある(Dr.モロー,1993-09,9784257901952)新規
  → 小説エリアル全20巻(913.6)・鈴木雅久画集(画集stream)は除外。手法=[[ndl_manga_filter_ndc726]]。
  ※後にユーザ裁定で**アンソロは出さない方針**→ARIEL分割は巻き戻し(ariel-comic元に復元・新規2ページ削除)。手法とアメコミdropは保持。

#### 段7: 残53件の精査 — 明確分のみ処理 (06-20)

未処理53件をNDL ISBN別著者で再確認: CLEAN23(誤判定=無処理) / REPOINT_full11 / STRIP6 / STRIP_multied13。
明確な2件を処理(bak `misc-fix-bak-20260620-162019`):
- `kaze-no-tani-no-naushika-1984`(著者unknown・部分ISBN) → **dedup alias** → kaze-no-tani-no-naushika(宮崎駿・完全版canonical)
- `the-boxer`(LEEHYE誤) → **著者修正** → JH(韓国manhwa THE BOXER。作品・ISBN正)

**★残=絡まった群(高リスク・要個別de-interleave/方針)**:
- Gundam Wクラスタ5(shin-mobile-senki-gundam-wing系): ときた洸一の講談社ISBN + 細雪純/みずき健の学研ISBN混在=**de-interleave要**(単純aliasでない)
- FE(fire-emblem-nintendo-1996/fuyuki-1999=大沢美月) / 八つ墓村(yatsuhakamura系=つのだ/影丸) / 日本の歴史(nihonnorekishi系=学習漫画多著者) / mahouka×3(編別アーク franchise)
- 著者ラベル誤り残: final-fantasy-lost-stranger(→亀屋樹/水瀬葉月)/kuro/charisma-2/jun-1983 = author-fill候補
- REPOINT自前ISBN要web: refrain-1988/joker-1998-3/work-in/meiou/last-order-kazunari
- CLEAN23(buyuden/worst/ringo/darker-than-black等)=無処理確定
- nhk-sono-toki=多著者アンソロ→非掲載方針で保留

#### 段8: de-interleaveクラスタ + 著者ラベル修正 (06-20、ユーザ「1と2」)

**de-interleave 5**(canonicalは無変更、誤claim側から共有ISBN剥がし。bak `sharedisbn-strip-batch-bak-20260620-162738`):
- `refrain-1988`(ささやななえこ): 岡田ユキオのリフレイン3冊除去→自前9784061754843(1988)残。canonical=`rifrein`(岡田ユキオ)
- Gundam W 4(`shin-mobile-senki-gundam-wing-1996`/-2/-3/-daburyuu): ときた洸一の講談社4冊(9784063340020/217551/667/728)除去→各自前の学研版(9784056xxx)残。canonical=`shin-mobile-senki-gundam-wing`(ときた洸一)無変更
  ※学研版Gundam W(みずき健/細雪純/むっちりむうにい)はアンソロ確定→段9でdrop

**著者ラベル修正 2**(作品・ISBN正、著者欄のみ誤。bak `authorfix-bak-20260620-162819`):
- `final-fantasy-lost-stranger`: むつきらん誤→**亀屋樹**(全12巻NDL一致)
- `meioukeikakuzeoraimaa`: 高屋良樹誤(ガイバー作者)→**ちみもりを/ワタリユウ**(徳間12巻NDL一致)

**残**: STRIP_multied own0(kuro/charisma-2/jun-1983/FE pair/八つ墓村pair/日本の歴史/銀河鉄道) / mahouka×3 franchise / REPOINT要web(joker-1998-3/work-in/last-order-kazunari) / CLEAN23無処理確定。

#### 段9: 学研版Gundam Wアンソロ drop (06-20)

de-interleave後に残った4ページをNDL照会→**全て「新機動戦記ガンダムW・アンソロジー」**(学習研究社 ノーラコミックスdeluxe ぽっけシリーズ、2nd-6th、著者無記名=多著者アンソロ)と確定。アンソロ非掲載方針でdrop(bak `anthology-drop-bak-20260620-164646`、anthology-drop.tsv)。
- shin-mobile-senki-gundam-wing-1996(2nd)/-1996-2(6th)/-1996-3(4th)/daburyuu(3rd,5th)
- スラッグ著者(みずき健/細雪純/むっちりむうにい/樹本祐季/氷栗優)=アンソロ寄稿者で別ページ分裂していたもの。
- canonical shin-mobile-senki-gundam-wing(ときた洸一・講談社・単著)は残す。
★手法: NDL題に「アンソロジー」明記 or 著者無記名多著者 でアンソロ判定→非掲載。anthology-drop.tsv。

#### 段10: 単著author-fix 3 + work-in re-point (06-20)

NDLでフルネーム+ヨミ確認し著者ラベル修正(作品・ISBN正、著者欄のみ誤。bak `authorfix2-bak-20260620-165028`):
- kuro: 青インク誤→ソウマトウ(黒、集英社2014)
- charisma-2: 花小路ゆみ誤→石原理(カリスマ、青磁ビブロス1994)
- jun-1983: 森下裕美誤→紡木たく(純、集英社1991)
work-in re-point: 現9784757546752=高津カリノWORKING(special-edition-fixの誤変換)→鈴木ツタのWork in自前9784862527745(コアマガジン2010)。
**残(絡まり深=要個別/方針)**: 八つ墓村pair(つのだ/影丸/Jet) / FE pair(大沢美月) / 日本の歴史(集英社学習漫画=多著者educational) / 銀河鉄道の夜(古城武司/Teamバンミカス/ますむら3版) / mahouka×3(編別アーク franchise) / REPOINT要web(joker-1998-3野間美由紀/last-order-kazunari).

#### 段11: 重複ページdedup(同ISBN集合) — 確実8群9 slug alias (06-20、ユーザ依頼)

`_dedup_finder.py`で66k走査→EXACT(同一ISBN集合)14群検出。実ISBN+NDL正題で「同一作品の表記/題揺れ重複」のみ確実判定しalias(bak `dedup-bak-20260620-171928`):
- jun-2012→jun-1983(紡木たく純)/hihon-gikeiki→masurao(ますらお秘本義経記13ISBN一致)/akai-kami-no-shounen→akaikaminoshounen(山岸凉子赤い髪の少年)/eroika→eikou-no-naporeon(栄光のナポレオン エロイカ26ISBN)/majindensetsu→god-mazinger(NDL=ゴッドマジンガー)/akai-shundou・aoi-shundou→shundou(NDL=蠢動)/dessin→nico-says(NDL=Nico says)/chocolat memorial→perfect(NDL=パーフェクトコレクション)
- jun-1983のtitleを純に是正(canonical正題)。
**dedupでない(=別作品の誤ISBN共有=JOKER汚染、触らず)**: king/king-z(別著者)・tales-of-destiny(別著者)・bibou他4(おおや和美の別4作)・fuufu-partner他2(それでいいシリーズ)。
残: OVERLAP(高重複=欠け巻/版違い)32対は要個別確認。

#### 段12: 奇子型(同一著者の版混在) 手塚治虫5作を手作業で版分離 (06-20、ユーザ依頼)

cm104(metadata104=版オーソリティ)で版構成を確認し、standardに別出版社/別imprintの巻が混在していたのを版分離(奇子と同手順、捨てず別editionへ)。bak `ayako-bak-*`/`ayako-fix-changelog.jsonl`:
- **w3**: standard=サンデーコミックス(秋田)2巻に正常化、講談社全集vol3を別aizobanへ分離
- **ludwig-b**: 潮出版社standard + 講談社全集を分離(aizoban)
- **neo-faust**: 朝日新聞社standard + 講談社全集を分離(aizoban)
- **fushigi-na-melmo**: 講談社全集standard + 小学館まんが絵本館を分離(other)
- **barbara**: 4版混在(ハード・コミックス大都社/全集講談社/角川/文庫全集)を分離+出版社誤記(講談社→大都社)訂正
※各全集の欠け巻(2巻中1巻等)はISBN未取得=種4候補としてchangelogに記録。
★検出器(`_ayako_detect.py`)は広く誤検出(長期連載)するため、cm104裏付け+少巻数+ISBN記号混在の明白例のみ手作業。残候補は据え置き(実害小)。

#### 段13: 同名フォルダ手作業確認①=綴り違い5ペアを個別修正 (06-20、ユーザ依頼)

同名スラッグ群(`_samename_finder.py`)からハイフン/綴り違いの5ペアをNDLで確認し種別ごとに修正:
- taaheruana-tomiko: ターヘルアナ富子の上下巻(750=v1/767=v2)別ページ分裂→1ページ2巻に統合(taaheru-ana-tomiko alias)
- skyhigh-karma: スカイハイ・カルマ2012再版(9784086193818集英社文庫)を版統合(sky-high-karma alias)
- tezuka-osamu: 大下英治「ロマン大宇宙」=非漫画prose伝記(genre無)→drop
- tezukaosamu: 石子順「未来からの使者」=児童図書(非漫画)除去、手塚「幻の名作集」(726.1)残す
- uchuu-senkan-yamato: ひおあきら版ヤマト2ページ重複→統合(企画noise著者除去)。※松本零士版/聖悠紀版は別作で残置、slug衝突(ひおあきら↔松本)はhomonym suffix要=別タスクflag
★同名群458の大半は正当な別作(年別/年齢別/spin-off)。真の誤り(分裂/重複/非漫画/別作混同)は薄く分布。NDC726.1/genre=漫画で漫画判定。

#### 段14: 同名フォルダ確認②=size2 SAME_AUTHORバッチ監査 (06-20)

size2 SAME_AUTHOR未処理ペア314を監査。★**exact題一致はわずか5ペア**(=同名群の大半は別作で正当を再確認)。5ペアの裁定:
- rakushou-hyper-doll: 伊藤伸平同作の徳間1995+英知2002→版統合(rakushou-hyper-doll-2002 alias)
- shinpi-no-sekai-eruhazaado: つぶらひでとも同作の竹書房+徳間→版統合(-tsubura-1996 alias)
- NHKその時歴史: 歴史系=まとめ不要(ユーザ方針)→skip
- 左ききのエレン: 原作かっぴー vs リメイクnifuni作画=別作→skip
- kuradashi選集: 多著者アンソロ記念編集→非掲載方針で保留
★結論: 同名群監査の真の誤り率は低い(314中exact題2件のみ実修正)。「同名おかしい」は綴り違い/分裂(段13で対処)に集中、残りは別作が大半=深掘りは収穫逓減。

#### 段15: 同名群②=誤帰属 有名作3件を著者ラベル訂正 (06-20)

同名群ページの「現ISBN真著者(種1/楽天/NDL) vs 著者ラベル」照合で誤帰属検出(`_samename_misattr.py`)。
ただし大半は**原作/作画の誤検出**(label=作画は正、種1が原作を載せるだけ。例 なのはViVid=藤真拓哉作画は正)。
★**単一creator古典作が翻案/トリビュート作家ラベルになっていた確実な3件のみ**修正(bak `misattr-bak-*`):
- black-jack: 吉富昭仁(=ブラックジャックALIVE作者)→手塚治虫(現ISBN=本編NDL一致)
- cyborg-009: シュガー佐藤/土山よしき→石ノ森章太郎
- gegege-no-kitarou: 松本しげのぶ/ラルフ・マッカーシー→水木しげる
228候補の残りは原作/作画false positiveが大半=無理に触らない(ユーザ方針「無い間違いを無理に探すな」)。

#### 段16: slug衝突 — 06-11適用後の残c2-unverdicted精査 (06-20、ユーザ依頼)

★slug新規則は2026-06-11本番適用済([[slug_apply_pipeline]]、69,004頁・alias30,533)=**衝突1,794は過去の数字で大半解消済**。
残=`.cache/c2-unverdicted-new.tsv`(210群merge_miss)を現状照合: 同naz題+著者重なりの統合候補41のうち**36が日本の歴史(歴史系=まとめ不要のユーザ方針)**、残りはfranchise編別/続編の誤検出(mahouka/将太の寿司2/DEAR BOYS ACT3vs4/KH3)。
真の修正2件のみ:
- lemon-hakusho: れもん白書(吉田まゆみ)のvol2(089389)別ページ分裂→統合(089372=v1/089389=v2/089396=v3)
- garfield: アメコミ(Jim Davis)→drop
★結論: slug衝突は06-11で解消済。残c2は歴史系+franchise誤検出が大半=実害無し。

#### 段17: 巻番号outlier監査と是正 (06-21、ユーザ依頼)

本番manga.v2直走査(`_audit-volnum-live.py`)で巻番号異常検出: GAP1,504/OFFSET767/DUP2。
outlier37件(=[1,2,51]型 高1点浮き)を★楽天ISBN照合で原因確定。一様な除去は不可(本物の巻が多い)。
**確定6件のみ是正**(bak volnum-bak-*):
- 汚染除去3(浮き巻ISBNが別作): itadakimasu#51=給食のおじさん(三五十一→51誤parse)/kaitou登場編#11+アバンチュリエ#11=813編別アーク
- 誤parse振り直し3(副題数字を巻番号化): chibikasu#50(50音)→3/honda-kanoko#46(46億年)→3/minami#24(タイムリミット24編)→4
★非処理(本物=除去禁止): フラグメント~18(red-eyes#27/夜行#17/グラゼニ#16等、楽天が実在確認=中間欠けは種4領域)/ISBN無~8(shadow通巻42/Zガンダム等=要NDL)/ruriiro#14(楽天は(2)=要精査)。
★durability: manga.v2直編集はpromoteで戻る。汚染=種2 repoint、誤parse=番号補正seedが本来必要(follow-up)。

#### 段18: outlier残31の精査結果 (06-21)

段17の確定6件に続き残31を精査。**追加で確定できたのはruriiro 1件のみ**:
- ruriiro-princess: #14のISBN9784408430171=楽天「るり色プリンセス(2)」=vol2の誤番号(既存#2はISBN無)→#2へISBN移植し#14削除。[1,2,3,4]完成。
★残30は安全に自動修正不可と判明:
- フラグメント18(red-eyes#27等): 楽天で実在確認だが補完に★版の誤分類が絡む(red-eyes欠け8-26は通常版28巻の巻だがページ該当版はデラックス版7巻→混入させると版混合regression)。cache coverage疎(半数0巻)。ライブAPI+版判断要=per-work deliberate。
- no-ISBN8(shadow通巻42/Zガンダム等): NDLが汎用題で無関係作にヒット=確証不能。touch不可。
- jin: alias済で不在。
★結論: 巻番号outlierは確定7件(段17:6+段18:1)を是正。残はregression risk高く、種4harvestは版整理込みのper-work作業。

#### 段19: no-ISBN outlier 8件 Wikipedia/NDL精査完了 (06-21)

ユーザ指摘(F90は1巻)を機にWikipedia/ISBN照合で全8件解決。「NDL確証不能」は早計だった:
- **修正4**: F90(中原れい全1巻・#11=別作ファステストフォーミュラ版混入) / Zガンダム(近藤和久全3巻・著者山口宏誤・F90汚染除去) / 影(山田ミネコ全2巻徳間1982・#42=劇画誌「影」通巻混入) / 空がすき!(竹宮惠子全2巻・#18=角川89再版誤番号)
- **drop2**: ナルト忍法帖(二次創作アンソロ・雄=雄山熊子ほか) / サイバーコミックス(バンダイ漫画アンソロ雑誌・北崎拓は寄稿者)→non-manga-drop.yml登録
- **再分類1**: つゆねこ鉱物学=実は全10巻(つゆねこ企画)=#10実在のフラグメント→fragment群へ移動
- **判断保留1**: マンガ法律の抜け穴=自由国民社の多著者法律解説シリーズ(各巻別篇・別作家、#12実在)=keep/drop方針判断マター
★教訓: no-ISBN/古書はWikipedia+NDL+楽天ISBN照合で作品単位に確定可。NDL単独は汎用題でノイズ。

#### 段20: 巻番号outlier+フラグメント 全タスク完了 (06-21)

監査(GAP1504/OFFSET767)→outlier37件を起点に全精査。Wikipedia/NDL/楽天API(Referer+Origin要,outOfStockFlag=1,全角題NFKC)で作品単位に確定:
- **修正(誤parse/汚染除去/版統合/番号是正)**: 段17の6+ruriiro+F90(1巻)+Zガンダム(近藤和久3巻除染)+影(2巻)+空がすき(2巻)+red Eyes(版誤分割統合27巻)+夢水(版統合13巻)等
- **フラグメント補完~80巻**: 新女喰い18/dream-buster7/遊戯王5D's9/あさかぜ8/真異種格闘10/はた万次郎7/だめんず/グラゼニ16/ef10/新ランチェスター(6-9)/本当にあった愉快な話10(田島みるく単独・誤アンソロ判定訂正)
- **drop(非漫画/アンソロ/雑誌/同人)**: ナルト忍法帖/サイバーコミックス/GIANT KILLING extra/大海賊同盟/夜行/つゆねこ鉱物学
- **多著者化keep**: マンガ法律の抜け穴(教育シリーズ・5著者+監修)
- **元々完備**: 男どアホウ甲子園/アタゴオル(浮きは部分収録の兄弟版)
★教訓: ①no-ISBN/0件の真因は在庫でなく全角題/長検索語/parse ②版誤分割(red Eyes型)は中間欠けでなく統合で解決 ③楽天著者『アンソロジー』『単独作者名』で性質判別 ④誤判定はdrop前に楽天検証で捕捉
