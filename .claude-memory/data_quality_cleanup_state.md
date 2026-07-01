---
name: data_quality_cleanup_state
description: 【進行中・中核】楽天種オラクル監査(T1-T4)に基づくISBN/巻数是正の進捗。慎重に・多数決・可逆・dry-run必須
metadata: 
  node_type: memory
  type: project
  originSessionId: ec751580-3d99-475b-940c-cf0e3f1feada
---

★楽天種(245k ISBN→正題/著者/出版社)＋NDL(ISBN→著者)＋cm104(版別正巻数)＋Wikipedia(各巻ISBN) を**照合ソース**に、本番DBのISBN/巻数誤りを是正中。方針=[[feedback_dont_repeat_regrouping_error]](単独ソース+解釈で上書き禁止・多数決一致のみ・可逆・dry-run確認)。書影は[[cover_source_affiliate_only]]。

## 監査(読み取り) — data/seeds/audit-T*.tsv
- T1版混在1,247 / T2無画像40k / **T3別物4,111(同一ISBN複数作=1,770核心)** / T4巻数違い248。スクリプト `_rakuten_audit.py` / `_audit_resolve.py`(②索引=シリーズ正規化+巻→ISBN)。

## 適用済(全て可逆・changelog/backup)
- **T3混入除去 77作**(jipang型=自前巻+他作混入→ISBNで除去。`_t3_apply.py`/t3-fix-changelog)。★空化判定はISBN無し巻も数える(worst=小室の本物vol1-4はISBN無し)。
- **T3再ISBN 12作**(丸ごと別作ISBNだが実在→楽天著者一致×cm104巻数一致で正ISBN+書影再構築。`_t3_reisbn.py`/t3-reisbn-changelog)。high-score等。
- **DUPLICATE統合**: 安全自動19群(base+年suffix:doraemon/spiral。`_dup_merge_batch.py`)＋手動2(Dragon Quest=堀井雄二保全/エスパー魔美3→1。`_dup_merge.py`)＋**NDL strip 41件**(別作が同ISBN誤共有→剥がし:gekiman章/kimi-no-tonari。`_dup_ndl_resolve.py`/dup-strip-changelog)。alias=dup-merge-alias.yml。

## ★合議で学んだ罠(重要)
- 同一ISBN複数作でも **同一作の重複 / 別作の誤共有 / 続編 / シリーズ巻断片** が混在。著者だけ/題だけでは誤る。**NDL実題＋著者＋cm104巻数の合議**で仕分け。
- canonical選択は「短いslug」一辺倒NG(ダイの大冒険=長い方が正)。**正式題(cm104/NDL/Wiki)一致**で選ぶ。
- merge は続編(こわい本/続こわい本)・シリーズ断片(マンガギリシア神話7作/June pride)で誤融合の危険→**strip(誤ISBN剥がし)が安全**、mergeは確証時のみ。

## T1版混在=大半は正当(自動一括しない)
- ★T1(standard内2社+)は**正規化後664作のうち大半が「正当な出版社変更=連載移籍」**(ちるらん徳間→コアミックス/ギャングキング少年画報社→講談社/終末のワルキューレ等)。standardに全巻あるのが正しい=**誤りでない**。
- 真の誤り=「別の**完結版**の巻が混入」(北斗型)のみ。区別はcm104の版巻数で(混入側が独立完結版か/連続継続か)。**自動一括禁止・個別対応**。
- 偽陽性源: 社名変更(KADOKAWA/学研/朝日)・[発売][頒布]タグ → `_t1_pubmix.py`のFAMILY/タグ除去で吸収。
- ★手動済: **北斗の拳**=新潮社版vol28-30を集英社standard(全27)から除去(hokuto-shinchosha-stray.json)。**マッド・ブル34**=分裂15統合+別版3除去+Kobo書影27/27。

## T3偽陽性除去(読み正規化)=済
- ★`_t3_reading_filter.py`: フリガナ(title_kana)exact一致=同一作の英題/カナ表記違い(19<Nineteen>↔ナインティーン)を除外。**T3 3,426→真の誤り2,393**(除外1,033/316作)。続編誤判定回避でexact一致のみ。台帳=audit-T3-real.tsv。本番不変。

## 空作23(③)=ほぼ済
- 誤ISBN剥がしで空化した23作を復活: **NDL著者一致11作＋楽天5作=16復活**(正ISBN+書影。チャレンジャーズ15/ぶんぶく8/激マンデビルマンの章/スペシャル 等)。dragon-quest-daino=alias。`_empty23_resolve.py`+empty23-changelog。
- ★残6(雨の法則/ANGEL DUST neo/水面の郷/おねがい!マルチくん/オズマニュアル/怨)=NDL・楽天とも著者一致なし→`empty-still-unresolved.txt`(後日Wiki/手動)。

## ★【方法論転換・最重要】曖昧マッチ廃止→ISBN厳密キー検証(2026-06-19 ユーザ裁定)
- ★ユーザ指摘: 今の誤りは**曖昧マッチ(緩いクラスタリング)が原因**。曖昧マッチで「確定」しても誤りをOKと誤確認するだけ=根本改善にならない。**ISBNだけが厳密キー(1冊1値)**。題名マッチは本質的に曖昧で確認に使うと誤確認する。
- ★正解の検証法=「**ISBN→(題・著者)を 種1/楽天/NDL から並べ、本番DBと厳密比較**」。著者は厳密名照合(区切り正規化+ひらがな→カナ。**LCS等の曖昧は禁止**。読みは author-yomi 辞書=厳密でOK)。
- ★実装 `_isbn_source_table.py`(種1 metadata101 + 楽天種 をローカル権威に全DB照合): **AGREE 223,962(91%)** / **TORICHIGAE(本物の取り違え=題も著者も違う=ISBNが別作に付与)** / AUTHOR_DIFF(同題で著者名だけズレ=別問題) / NO_SOURCE 4,833 に4分類。same_title()で取り違えvs著者ズレを分離。
- ★**本物の取り違え=427 ISBN / 192作品**(著者サフィックス除去後。`torichigae-real-477.tsv`)。4TEEN→楳図14歳(33)/ハッピー!(波間)→浦沢Happy!(23)/GOGOモンスター→浦沢MONSTER(18)/聖闘士BLADERS→赤石SAINT 等。残FPはカナ↔英著者(garfield/pingu)少数。**次=この427を慎重に是正**(ISBNは真の作品のもの→誤作から除去/再付与)。
- 身元チェック`_identity_check.py`(題core×著者ローカル)=**OK94%**だがこれは曖昧確認なので「参考の俯瞰」止まり。`_authorkey_check.py`(著者キー逆引き)も同様に参考。検証本体はISBN厳密照合に一本化。
- 走行中: NOT_FOUND実在確認(楽天=`_notfound_recheck.py` / NDL=`_notfound_ndl.py`、各~2h)→NO_SOURCEのNDL補完に流用可。

## ★取り違え是正=実行完了(2026-06-19・option2=ラベル維持+中身入替・削除巻を失わない)
- 検出427ISBN/192作 → 計画(DELETE/MOVE/CREATE_NEW) → A/B/C仕分け → 実行。全段階 backup+changelog+可逆。空edition0・typecheck緑。
- **CREATE_NEW 139**(`_torichigae_create.py`): 真の中身(別作)を新規作成保全(浦沢Happy!等)。題=楽天巻題LCP/kana=NDLヨミ/slug=ヘボン(漢字ヨミ失敗22作はr-<isbn>placeholder=後でslugパイプライン整形)/genres暫定provisional/publisher多くは(unknown)=後enrich。
- **B欧米コミック5=作らず**(ユーザ裁定「欧米は載せない」: peanuts/garfield/pingu/muumin/superman)。
- **C題不可6=退避**(torichigae-routeC: SF短篇/アンソロ等、後日手動)。
- **DELETE**(`_torichigae_delete.py --apply`): 180作から402誤ISBN除去(★削除前検証=各ISBNが新規作 or 既存 or 欧米に在ることを確認、未保全7はskip=loss防止)。115作空化。
- **RE_ISBN**(`_torichigae_reisbn.py`楽天23 + `_torichigae_reisbn_ndl.py`NDL5 = 28作)空ラベルに本物巻再構築。本物データ無87作=空シェル削除(`torichigae-needs-content.tsv`記録・後日再追加可)。
- ★残follow-up: rescue-slug22(slugパイプライン)/needs-content87(再追加)/未保全skip7/C退避6。
- **A後始末済(2026-06-19)**:
  - A1=新作139をNDL(ISBN権威)で題検証→101是正(楽天誤題:火宵の月→もしかしてヴァンプ等)。`_torichigae_ndl_verify.py`+`_torichigae_title_fix.py`(同一作は楽天きれい題維持/別作のみNDL・副題保持)。
  - ★**scope=楽天booksGenre(001001) OR NDL NDC(726) のOR判定**(ユーザ方式:どちらか漫画判定で整合すれば漫画)。`_torichigae_scope_combined.py`。新作130=漫画86/非漫画0/不明保持44。非漫画6削除済(辞典829/歴史209/小説913/映画778=NDC明確非漫画。`_torichigae_ndc_filter.py`)。★NDC不明≠NDL不在(=NDL有るがNDC欄空が多い)。楽天単独genreは不正確(horaizon=楽天非コミックだがNDC726=漫画)。
  - A3=publisher 109/130解決(`_torichigae_enrich.py`。楽天社名→publishers.yml `name`厳密一致。だろう運転禁止で未解決21は(unknown)維持)。genres=楽天caption空(古作)で導出不可→暫定維持しgenre蒸留track。

## AUTHOR_DIFF(同題で著者名ズレ)=後回し(2026-06-19)
- ISBN厳密照合のAUTHOR_DIFF 15,086(同ISBN同題で著者名違い)。`_author_diff_refine.py`で4852作→(a)表記違い1555除外/(b)真候補3297(`author-diff-real.tsv`)。
- ★**stakes低**=ISBNは正しい作品に付いてる(構造正常)。著者「名」精度の問題のみ。
- ★**裁定が難しい**: NDLは最近作で空(上位12件全部NDL著者無=不可)。種1/楽天を盲信不可(原作creditのみ列挙のことあり=ルパンY:我々「山上正月=作画・正」vs 種1「モンキーパンチ=原作」→我々が正)。我々が誤りの例=シャドーハウス青インク→ソウマトウ。
- ★**本命の裁定者=AniList staff**(原作/作画。最近作に強い)。anilist_id持ちの(b)をAniList照合→我々誤りのみ是正、が正しい道。後回し。

## slug/フォルダ名・kana不整合の調査(2026-06-19)
- ★**再利用索引** `data/seeds/slug-kana-index.tsv`(66,527作 slug/title/title_kana/romaji/一致度。先頭行読みの高速生成`_slug_kana_check.py`)→ 今後のslug系は全yaml読まず表で処理。
- ★一覧表UIに**slug表示(DEBUG赤字・本番前削除)** 追加済(`ListClient.tsx`)=実機でslug≠題名を目視。
- ★**kana不整合193是正**(title_kanaに漢字残=読み壊れ): PIPE_STRIP127(`正しいカナ|漢字junk`の漢字除去・`_kana_fix.py`)＋手動読み40(`_kana_corrections.py`・殺意の底→サツイノソコ等＋「口の興奮」→「日の興奮」corruption)=計167。残26=構造問題(下記)。
- ★**プロジェクトX挑戦者たち16作=構造問題**(title=各話/kana=シリーズ名。16話が別作=本来1シリーズに統合すべき。NHKコミカライズ、笠原倫ら作画=漫画scope内)。アンソロentry(ribonmanga/sasayananae/basara=作品集名がkana)も同型。要統合。
- ★**slug品質: カタカナ外来語がヘボンのまま**(プロジェクト→purojiekuto/マイボール→maibooru。本来project/my-ball)。既存slugにも多数=既存slug pipelineのカタカナ→英が不完全。slug蒸留([[slug_apply_pipeline]]・[[method_ai_generate_plus_webverify]])で一括是正territory。kana-vs-slug不一致check(slug-really-bad89)は英綴り正(curve/eagle)を誤検出するので使えない=漢字残りkanaのみが確実signal。
- ★同名分裂/コピー監査`samename-audit.tsv`(同名+著者共有40。こち亀227+16分裂/Boys be33+33コピー等。版/年バリアントは正当)。取り違え新作dup5は是正済。
- こち亀ジャンプリミックス23・小説3(basutaado/新KOR/ガーベラ)・非漫画2 をscope drop済(楽天seriesName確証)。

## ④身元統合(NOT_FOUND実在確認)=negative result(2026-06-19)
- NOT_FOUND7145を 著者key ∪ 楽天API ∪ NDL API で実在確認→6496確認/638未確認(`ghost-works.tsv`)。
- ★638は**spuriousでなく実在最近作**(100日後に死ぬ悪役令嬢/86オペハイスクール等2022-25。cm104凍結+NDL遅れ+ラノベ原作の著者照合不完全で未確認化)。
- ★真の発見=**最近作の著者名が壊れてる**(frankmatt/hikaripub2022/la軍等)=著者データ品質問題=AUTHOR_DIFF/AniList trackの領分。④で「出すべきでない作」は見つからない(最近作に埋もれる)→打ち切り。

## ①構造問題=episode/アンソロが別作化→シリーズ統合(2026-06-19・済)
- ★方針(ユーザ): **アンソロ/オムニバスはシリーズ単位でまとめる・同名の他シリーズとは混ぜない**。
- **プロジェクトX挑戦者たち18→1**(`_project_x_merge.py`): 宙出版コミック版の各話(別作画者)を1シリーズに。各巻=エピソード(volume_label=話題)、artists=巻ごと作画者、原作=NHK制作班、slug=project-x-chousensha-tachi。
- **ささやななえ作品集2→1 / 少年忍者バサラくん2→1(義見依久) / りぼん新人まんが傑作集2→1**(`_anthology_merge.py`)。巻結合+series題。
- ★basaraは誤グループだった: 田村BASARA(44)/ミナミ新平/望月バサラ戦車隊=各々別作(混ぜない・触らない)。少年忍者バサラのみ統合。
- series-merge-changelog.jsonl。slug basara-3001等は暫定(slug蒸留で整形)。

## slug蒸留(カタカナ外来語→英)=一部済(2026-06-19)
- ★既存slugは2026-06-11 pipelineで大半英化済。真の漏れ≈133(`slug-loanword-genuine.tsv`)。辞書一括は不適(既英化を誤検出/ランキング→run-king誤分解/アンド・マン・typo[フアイヤー]取り逃し=過小)と確認。
- **93件rename適用**(`_slug_loanword_apply.py`・alias=`slug-overrides.yml`): dokutaa→doctor/doragon→dragon/love-ando-fuaiyaa→love-and-fire/maibooru→my-ball/faiaaman→fireman 等。ナイト19は題で判定(騎士=knight/夜=night、曖昧6はnaito維持)。
- **計131件 rename適用**(辞書80→231拡張で+38)。lion/rider/runner/orange/cafe/elf/machine/doctor/dragon等。
- ★★**辞書一括の原理的限界(再発防止)**: 短い外来語ヘボンが**和語形態素と衝突**=アイ→eyeが異世界`isekai`→isekeye/デス→`death`がです/サン→`sun`がさん/アンド→`and`が安藤。**衝突語(アイ/サン/デス/アンド/マン/ワン/ツー/カラー)は辞書から除外必須**。それでも連結(elfyome等)は残る。**完全化はAI per-slug(題を読んでloanword判定)以外に安全な方法なし**=大規模・低価値で残置。
- ★残: 曖昧ナイト6(naiteingu等)・連結slug・辞書外の散在loanword。slug rename不可逆寄り=alias(slug-overrides.yml)必須・backup・要レビュー。`_rebuild_slug_dict.py`で辞書管理。

## ★汚染3タイプ＋検出器(2026-06-20・ユーザが実機で発見)
1. **ISBN集合 重複**(題違いコピー): `_isbn_set_dup.py`=★**題でなくISBN集合でグループ化**(ユーザ発案)。EXACT完全複製49グループ/143作(怖い本三重複kowai-hon/umezu-kazuo/zoku・ハニ太郎14エントリ・千里の道3等、題normalizeが見逃した複製)。`_isbn_dup_dedup.py`で**同一著者×題変種32グループ=68複製削除**(canonical保持・alias=dup-merge-alias.yml・可逆)。★**別著者8+題相違9はun-merge要でflag**(`isbn-dup-unmerge-flag.tsv`=別作が同ISBN誤共有=eroika/栄光のナポレオン・god-mazinger/魔神伝説・私はゲゲゲ/神秘家水木等。dedup不可、片方が誤ISBN)。HIGH高重なり66ペア(分裂/版違い)も出力。
2. **複数著者混在**(別作merge=JOKER型): `_intra_work_author_split.py`=1作の巻ごとISBN→著者が違う。763作検出(joker=河野ヤス子/河奈マリオ/道原カツミ)。ノイズ=著者suffix変種(森薫(漫画家)/(1978-))/アンソロ/原作作画→要精緻化。未適用。
3. **誤あらすじ**(wrong anilist_id): ジハード(題著者正・あらすじが別作ボディガード話)/ドリーム(妖精王のあらすじ)。=[[anilist_link_quality]]の3,238頁。anilist_id↔題照合で検出(別途)。
- ★教訓: 怖い本が長く検出されなかった理由=dedupを**同名グループ内でしか**回してなかった。ISBN集合グループ化で根本封鎖。
- **un-merge ①②済(2026-06-20)**: `_unmerge_apply.py`。①series-dedup(ギリシア神話8→1/プリンセス2→1)②de-interleave(CUE/神秘家・私はゲゲゲ/流月抄・ベスティア/伯爵カイン・赤い羊・忘れジュリ=ISBNを真題著者で振分)。カフカ=束にISBN無→needs-content。
- ★★**un-merge ③=未適用・次回実行(計画確定・最重要残)**: 誤側に実ISBN補完で両作生存。`_unmerge3_investigate.py`済。**修正ISBN6件**: kurotokage-2019(森下裕美)←9784575945614 / gift-2012(塩森恵子)←9784575334906 / 24colors(千葉コズエ)←9784091316073 / venus-2015(麻生歩)←9784776739586 / gift-2006(ユキヲ)←9784047138490 / fire-emblem-thracia-776-2000(日野慎之助)←9784757700321 (★後4件はユーザが外部調査で提供)。**B幻削除**: hiyoko-brand(著者こばやしひよこ=oku-sama-wa-joshikouseiの誤生成)→alias削除。処理=誤共有ISBN剥がし→実ISBN巻に差替(発売日種1/NDL・書影ISBN後付)、正側不変。

## 保留(危険ゾーン・未着手)
- DUPLICATE: DEFER-SIMILAR8(続編/dup疑い)/SERIESFRAG4(シリーズ巻断片=シリーズ統合案件)/UNCERTAIN2。dup-merge-manual.tsv。
- strip/再ISBNで正ISBN未確証の**空作23**(t3-emptied-unresolved.txt。本番に空で残存・previewから除去済)→NDL/Wiki/手動。
- T3 CONFLICT150・T4分裂(マッド★ブル34)・奇子型版分離([[edition_mix_same_author_ayako]])。

## 【後回しTODO・覚えておく】Kobo書影で歯抜け全体再挑戦
- ★ユーザ指示(2026-06-19): **ISBN/巻数問題の解決が最優先**。書影(Kobo歯抜け補完)は**後回し**だが忘れない。
- 手法確立済([[cover_source_affiliate_only]]): 楽天Kobo電子で古い紙本の書影が取れる(釣りキチKC65=65/65実証)。歯抜け約1万巻(北斗後半等)に展開すれば相当埋まる。ISBN/巻数が片付いてから。

## テスト環境
- preview(.preview-data/manga)= **問題作505に入替済**(壊れ→修正の視覚確認用)。修正はpreview+manga.v2両方に適用しpush→pages再デプロイ。本番(R2/Worker)は別。
