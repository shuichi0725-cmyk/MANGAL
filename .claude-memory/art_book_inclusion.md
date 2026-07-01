---
name: art_book_inclusion
description: 画集/原画集/イラスト集を漫画と別カテゴリで掲載する方針と進捗(Phase1済・Phase2 step1-3実装済・frontend未)
metadata: 
  node_type: memory
  type: project
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

★方針(2026-06-04確定): **漫画家の画集/原画集/イラスト集を掲載**する(以前の「非漫画でdrop」から転換)。 ★**絶対に漫画の巻列に混ぜない**。 **作画家(artist role)に紐付け、 原作者には紐付けない**(ラノベ等。 例: 灰村キヨタカ=はいむら画集はとある原作者鎌池和馬でなく灰村に)。 **アダルト除外**。 ★**網羅は目指さない**(小説イラストレーター画集=とある等はMADB未収録の取りこぼし=不要と判断)。

**スコープ確定**: Q1=画集/イラスト集/原画集/ART WORKS のみ(設定資料集/VISUAL BOOK/ファンブックは含めない)。 ★アニメコミック/フィルムコミックは「映像のコマ」で画集でない=drop維持。

**Phase 1済(データ確定・commit済)**:
- `data/seeds/art-books.yml` = **203件**(漫画家画集。 series_key/artist/adult/multi_artist)。 marker欠落画集も追加済(妖鬼化=水木しげる妖怪原画集/タッチ=あだち充/彩=大和和紀等。 NDL突合で発見)。
- `data/seeds/art-book-exclude-isbn.yml` = **7件**(漫画に混在した画集巻のISBN。 うる星やつら165巻に画集1巻/12歳/少女革命ウテナ/ドメスティックな彼女等→promoteで漫画から除外する)。

**Phase 2 step1-3実装済(`docs/art-book-display-design.md`、 2026-06-05)**:
- **step1 schema**: `ArtBookSchema`(slug/category「画集」/title/kana/romaji任意/artist/multi_artist/adult/linked_works/publisher/year/qid/volumes)+ `DataBundle.artBooks`(manga[]と別配列)。 loader=`data/art-books/`読込・adult既定除外(lib/loadData.ts)。
- **step2 adult**: 監査ツール `scripts/_audit-artbook-adult.py`(known成人作家2035件×title marker、 種2 adult_score)。 ★人手確認で **adult確定=艶夢のみ1件**。 ★**アシオART WORKSは誤爆=adult除去**(作家signal単独。 実体=千の魔剣と盾の乙女画集/一迅社文庫=全年齢LN)。 残KNOWN9件(FE/風の聖痕/OKAMA/あずまゆき等)は全て非adult(作画家≠画集)。
- **step3 promote分離**: 画集series_keyをmanga.v2から除外(混入ガード)+混在ISBN除外(うる星等で上下再連番)+別ループ `build_artbook`→`art-books.v2/<slug>.yml`(slug暫定`artbook-<sid>`、 merge群でクラスタ統合、 成人は`.adult`退避非出力)。 機械検査=漫画.v2に画集ISBN 0件PASS。 実測162出力/1成人/23巻データ無/16統合=202。
- ★**registry検証の教訓**: art-books.yml(Phase1)に**漫画本編/外国版が誤登録され得る**。 削除2件で **203→201**: ①「悪魔の花嫁(あしべゆうほ/デイモスの花嫁37巻)」=版違い水増しの漫画 ②「Le grand livre de sailor moon」=**仏語版**(ISBN978-**2**=仏語圏/Glénat刊。 Amazon.co.jp輸入販売≠日本出版)。 ★title markerだけで信用せず **複数巻+marker無は版/ISBNを実見**(うしおととら全集=実は原画集/妖鬼化=妖怪画集はKEEP)。 ★**ISBN国コード点検**で外国版検出(registry全体で仏版1件のみ確認)。 [[shu2_qid_is_author]]でqid救済は著者の別漫画混入になるため不可。
- **フリガナ補完済(2026-06-05)**: 画集はNDL監査未通過でtitle_kana空26件→1件。 `_audit-artbook-furigana.py`でNDL照合し、 clean18(NDL)+手当て19(姉妹転写/固有名構築/カタカナ化)を `furigana-corrections.yml` に純粋追加(450→487)。 ★**NDL盲目適用せず**: MISMATCH7件は既存が正(風の聖痕=スティグマ[公式当て字]>NDLセイコン[へうげ型誤])。 [[furigana_ndl_audit]]。 romaji/slugは漫画と共通保留=[[pending_slug_generator]]。

- **step4 loader同期済(2026-06-05)**: `art-books.v2`→本番 `data/art-books/` に**159件**commit。 `loadAllManga().artBooks=159` zod全件通過確認。 ★registry最終調整=**199件**(203→199。 追加除外: 成田亨画集[特撮美術家=漫画家でない]/少年倶楽部名画集[雑誌挿絵アンソロジー=単一作画家なし]。 高橋ツトム画集=artist補完)。 ★ArtBookSchema は artist 必須(漫画家紐付けが核)=緩めない。 巻データ無40件は非出力(159=199-40[no_edition/dup/adult])。

- ★**MADB誤parse=単一文字題に巻が埋もれる型**(2026-06-05、 高橋ツトム画集で発覚): NDLの「S : 高橋ツトム画集」(集英社)/「K : 高橋ツトム画集」(講談社)= 2社同時発売の別2冊を、 MADBが **title「S」「K」** と誤parse → 巻ISBN付き実体が1文字題seriesに埋もれ、 別に**空の重複series**(高橋ツトム画集/巻無)も生成。 ★対処: `build_artbook` に **art-books.yml の `title`/`title_kana` 上書き機構**を追加(MADB誤parse是正・種2/種3不変)。 空genericを除き実体S/Kを正題で登録。 ★教訓: 巻データ無の画集は **NDLで同名・別出版社・同時期を疑い**、 ISBNでDB内の誤題seriesを探す([[ndl_volume_structure_resolves_fragmentation]])。 art-books.ymlのtitle上書きは他のMADB誤parse画集にも再利用可。

**step5(画集の見せ方)実装済(2026-06-05、 最小・インライン方式)**: ★ユーザ確定UX=**「ジャンル欄に画集チップ→押すと一覧がその場で全画集に切替」**(別ページ/ヘッダタブは不採用=試作後撤去)。 `lib/filters.ts`に`FilterState.artBooks`+`applyArtBookFilters`(query=題/作画家・出版年・sort、 漫画用filter非適用)、 `FilterPanel`ジャンル末尾に「🎨画集(161)」ChipButton、 `HomeClient`が`artBooks`時は`ArtBookCard`グリッド描画(見出し「画集から探す」)。 `ArtBookCard`+`lib/amazon.buildAmazonUrlForArtBook`(ASIN>ISBN>題+作画家)。 ★書影は🎨プレースホルダ(PA-API後)。
- ★**Amazon表記の扱い(2026-06-05確定)**: 未登録(tag空)でも**プレーンテキスト「Amazonで見る」リンクはnominative fair useで適法**(ロゴ不可・提携を匂わせない)。 ★PA-APIはリンクの条件でなく**書影(画像)に必須**(本承認後)。 ★違反だったのは**「アソシエイト参加者です」等の提携主張**→未登録のため将来形/中立に修正済(layout/privacy/about/terms)。 実登録時に正規開示文へ戻す。 [[store_affiliate_architecture]](楽天先・Amazon後回しが既定)。

- **画集の作品ページ実装済(2026-06-05)**: `/art-books/[slug]` = 漫画 `/manga/[slug]` と同構造の軽量版。 ★ユーザ指定: **ジャンルは「画集」固定タグのみ**(元漫画ジャンル流用しない)、 **あらすじ無し**、 作画家(押すと同作家絞込)/出版社(有る時)/出版年/巻ごと購入リンクを表示。 ArtBookCardは「カード→作品ページ」遷移(Amazon直リンクでない)。 ★slug=**暫定`artbook-<sid>`のまま確定**(本番URLは漫画のslug生成器を作る時に画集もフリガナから一括確定。 slugは後rename困難なため規則裁定前に焼かない。 [[pending_slug_generator]])。 フリガナはslugの素として準備済。

- **「この作家の画集」枠 実装済(2026-06-05)**: 漫画 `/manga/[slug]` 下部に同作画家の画集を表示(`app/manga/[slug]/page.tsx`、 `manga.authors`名 ∩ `artBook.artist`、 ArtBookCard再利用)。 ★**紐付けは作者名のみ**= **作品名一致(特定漫画への紐付け)は廃止**(特定漫画に紐付かない一般イラスト集も多く誤紐付けになるため)。 原作者には紐付けない(manga.authorsのみ照合)。 実証: ハンター×ハンター(冨樫)→幽遊白書画集 / SLAM DUNK(井上)→バガボンド画集 等。 render時filter=事前計算不要。

- **step6 通し検証 完了(2026-06-05)**: `scripts/_verify-artbooks-step6.py`(混在ゼロ/adult除外/データ整合[slug一意161・kana全・外国版ISBN0]/購入リンク/作者紐付け[原作者除外])=失敗0・警告1(24件古書pre-ISBNで題検索fallback=仕様上正常)。 `next build`=**210/210ページ静的生成成功**(161画集+42漫画+一覧)。 画集機能の通し検証クリア。

**残(任意・機能は完成済)**: 書影(🎨placeholder → 楽天無料API or PA-API差替=体験向上の本命) / slug本確定(漫画のslug生成器と同時) / トリビュート画集の代表artist紐付け確認 / ★本checkoutは漫画42サンプルのみ=「この作家の画集」のフル規模検証は全漫画データ環境(蒸留)で。

**未決(§6、 step5前に裁定要)**: 画集slug最終命名(暫定artbook-<sid>。 ローマ字生成器GO待ち=[[pending_slug_generator]])/ カタログ入口(タブ?)/ トリビュート画集の紐付け(代表1人?)。 関連=[[ndl_nonmanga_sweep]][[merge_needs_external_proof]]。
