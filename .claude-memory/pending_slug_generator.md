---
name: pending-slug-generator
description: slug生成器の新規実装。規則4点は裁定済(長音落/を=wo/敬称ハイフン/カタカナ=英綴り)。7分岐実装→全件TSV→レビュー→GO→適用+alias表 の段階
metadata:
  node_type: memory
  type: project
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

★【2026-06-11 深夜更新: 本番適用も完了】promote3走で69,004ページ生成・alias30,533。実行手順と踏んだ罠は[[slug-apply-pipeline]]に集約(c2 reps凍結/rep単位prep/latin title優先/音写長さガード/dict3カナ制限)。残=Stage E(ISBN振り直し920配線)+Stage F(版クラスタ統合スイープ)。

★【2026-06-11 生成フェーズ完了】6/10裁定4規則を `scripts/_slug_rules.py`(token_roman=長音保持/ヲ=o/定着固有名詞 tokyo/kyoto/osaka/kobe)に実装、v1/v2/assemble/num-fix が共用。全再生成→c-1(1,229群)/c-2(718行)再導出→`_integrate-slugs.py`(恒久統合器=8layer+NDL fix継承67+手動7)→`data/seeds/slug-final-integrated.tsv` 76,435行・ページ71,796・**不正重複0/交差0/junk0**。変更=長音22,919(30%)/を=o 428/tokyo 305。`_slug-apply-prep.py`=統合TSV単一ソース化(旧構造はNDL fix層が適用入力に漏れる欠陥だった)。旧baseキー資産は `_rekey-slug-assets.py` でrep経由再キー(★c2のreps列=\x1f区切り、keyに|を含むため)。★c2 merge306はStage A-3でseries-merge-auto適用済(旧backup比422ページ吸収=正常)。★残=ユーザGO→`_slug-apply-build.py`→promote(~20分)→volume-final REVIEW_APPLYTIME 141行を本番旧slug対応表で解決→alias/_redirects統合。レビュー判断点3つ=docs/slug-rules-v2-review.md(定着綴りリスト/yuuyuu-hakusho型/裁定なし衝突161群[機械suffixで安全・後追い可])。

---(以下は実装前の記録=経緯参考)---

【slug 生成器の新規実装(B-3)】現 makeSlug(group-into-series.ts)=display(漢字)をwanakana=漢字破綻。 CLAUDE.md の新規則(title_kana起点ヘボン+7分岐)未実装=全76,435件の正しいslug生成器が無い。

★**フリガナ土台は検証済**([[kana_validity_state]]、 239誤り修正済)+ 種a連結済([[anilist_matching_state]])でカタカナ英語綴りの音写フィルタ材料も揃った。

**★規則裁定(2026-06-10 改訂=最新。 5/31裁定を上書き、 ユーザ「mahouka-koukou」で確定)**:
1. **長音=保持**(ou/uu 逐字) → 魔法科高校=`mahouka-koukou` / 東京(定着固有名詞は例外)=`tokyo`。 ★5/31の「落とす」を反転。 AniList/MAL圏の打ち方・可逆・衝突減
2. **助詞「を」= `o`**(ヘボン標準。 5/31の wo を反転)
3. **敬称=ハイフン区切り**(両日一致) → `takagi-san`
4. **カタカナ外来語=AniList english 元綴り + 明白な辞書英単語 + グレーはWeb検証**(両日一致)
★影響: v2生成器はパラメータ変更+再生成(安い)。 AI/Web検証済み資産(カタカナ英語4,249/num/latinmix)は英語綴り側なので**無傷**。 CLAUDE.md「ローマ字化4規則」に永続化済(2026-06-10)。

**旧裁定(2026-05-31、 参考=無効)**: 長音落とす(tokyo/mao)・を=wo。

**進め方(残り)**: title_kana_segmented(分かち書き=語境界→ハイフン)起点で 7分岐実装(CLAUDE.md slug規則)→ 全件slug案生成(**適用せず TSV 一覧**)→ レビュー → GO で適用 + 旧slug alias表。 ★slug=フォルダ名=URL で rename困難なので案生成→レビュー→GO必須(CLAUDE.md明記)。 検証例: 鬼滅→kimetsu-no-yaiba / 七つの大罪→nanatsu-no-taizai / らんま1/2→ranma-nibunnoichi / 東京喰種トーキョーグール→tokyo-ghoul / ×一→batsu-1。 詳細は `docs/anilist-match-slug-investigation.md` C節。

★**v2 決定ロジック実装済(2026-06-05、`scripts/_slug-gen-v2.py`、適用なし)**: v1(候補並記)に class別決定層+音写フィルタ(子音骨格類似)+衝突検出を追加。 出力`.cache/slug-gen-v2.tsv`。 実測76,435件: **high 93% / review 6%**(kana-hepburn58,478/kana-fallback5,486/anilist-romaji4,947/latin4,580/num2,943)。 検証OK=鬼滅→kimetsu-no-yaiba / ベルセルク→**berserk**(音写1.0) / ドラゴンボール→dragon-ball。 ★**見直し前提の残課題(GO前)**: (a)カタカナ音写閾値(0.45-0.7のreviewは大半正しい=要調整、SAO/urban-legend等)/ (b)**num 4分岐未実装**(2,943件。 麻雀放浪記2020→年号「2020」保持等)/ (c)**衝突4,422群の-姓+年suffix未実装**(akira×6/kana×3等)/ (d)字面外国語併記(東京喰種→現tokyo-guru、トーキョーグール併記題のみrule#5)/ (e)幽遊白書=`yu-yu-hakusho`(規則#1ハイフン)だがv2は`yuyu-hakusho`。 ★画集161も title_kana_segmented(98件)で同生成器に乗る([[art_book_inclusion]])。 ★**適用は全データ環境(蒸留)+GO後**。 漫画本番ymlは本checkout 42サンプルのみ。

★**(a)カタカナ英語綴り 完了(2026-06-05、`data/seeds/slug-katakana-en-candidates.tsv`、未適用)**: kata-fallback 4,249件を **AI一括(workflow 29並列)で英語綴り生成 → 怪しい外来語780件をWeb検証(workflow、作品特定クエリ「題+作者+漫画」)**。 最終: ai_high2,904/web_confirmed366/web_corrected64/keep_hepburn403/ai_low162/unresolved350。 ★Web是正8%が実誤りを修正(dessert→desert/double-blind→double-breed/ギャートルズ→giatrus/D・F・O→death-fantasy-opera/sky-crawlers等)。 unresolved350=公式英題無し(手動 or AI案/hepburn維持)。 ★スクリプト: `_slug-gen-v2.py`(候補生成)/ workflow kata-en-slug-gather(AI)/ kata-en-webverify-full(Web)。 ★**残=v2生成器にこの候補を統合**(kata-fallbackのslugをこの英語綴りに差替)+ (b)num4分岐 + (c)衝突suffix(option2=原作多漫画化は全版-作画家姓+年・[[collision_slug_investigation]])。

★**(b)num数字 確定ルール(2026-06-05 ユーザ確定。 2,943件)**: ①**音読み数詞**(kanaがニセン/ジュウゴ等)→**算用数字keep**(15歳[ジュウゴサイ]→`15-sai` / 2020[ニセンニジュウ]→`2020`)。 ②**英語読み**(kanaがナインティーン/ファイブ等)→ ★**option2**(2026-06-05確定): 「数字を除くと題がほぼ空=数字そのものが題」なら**英単語**(19→`nineteen`)、 「除くと実質的な題が残る=付随/続編番号」なら**数字keep**(ペルソナ5→`persona-5` / 金色のガッシュ!!2→`konjiki-no-gasshu-2`。 ★2=ツー英語読みでも付随番号なので数字)。 ③★**英語表記/ラテン隣接**(2nd/3rd/AK-69/数字+st,nd,rd,th/latin隣接)→**そのままkeep**(2nd SEASON→`2nd-season` / AK-69→`ak-69`。 ユーザ「2ndはセカンドの英語特殊読みなのでそのまま採用」)。 ④特殊・当て字(139=イサク)→**ヘボン既定**(139→`isaku`)。 ★実装=ラテン隣接keepを先に適用→残った単独数字を **算法案B(数字の音読み・英語読みを生成しtitle_kana内検索→ヒットで型判定。 分かち書き不要)** で判定。 ★適用なしTSV(`data/seeds/slug-num-fixed-candidates.tsv`、 2,943件中変更1,362・要レビューflag1,677)→レビュー(カタカナ英語と同運用)。 ★内訳=純日本語+数字2,355(主対象)/ ラテン混じり588(★**完了**、下記)+ no-segment140(未着手・現状ヘボン維持で無害)。 ★**latin-mixed 588 完了(2026-06-05、`data/seeds/slug-latinmix-candidates.tsv`、未適用)**: segが**ラテンも音写**(AK-69→エーケーシックスティナイン)で「全カナ→ヘボン」は壊れる→**2段workflow**。①AI一括14並列(字面title+公式かな読み→「ラテン/数字run=字面lowercase + 日本語run=読み」再生成)。★**当て字カタカナは英綴り**(魔法騎士レイアース→`magic-knight-rayearth`/ガールフレンド→girlfriend/ワイルドアームズ→wild-arms/サイボーグ009→cyborg-009)、固有名詞コインはヘボン(ガンダム→gandamu)=gap-a音写フィルタを日本語run内にも適用(漢字題はgap-a純カタカナ対象から漏れていた)。②**LOW50件Web裏取りworkflow**(作品特定クエリで公式英題確認)→confirmed34/corrected9/unresolved7。実修正=ゴルゴ13 gorugo→**golgo**/3×3EYES sazan→**3x3-eyes**/Mother2→**giygas**・**ness**。後処理=4koma→4-koma整合・×→x・助数詞ハイフン。conf列(OK538/VERIFIED43/UNRESOLVED7)。同一作slug揺れ(399/401)統一。 [[method_ai_generate_plus_webverify]]。 ★**数詞keep決定の更新(2026-06-05 ユーザ「dai-4-bu とりあえずこれが自然」)**: sino読みに**ヨン/ナナも含めkeep-digit**(第4部→`dai-4-bu`/7人→`7-nin`)。 ★副作用=**4コマ→`4-koma`**(旧案yonkomaを反転、 一貫性優先・レビューで最終確認)。 ★例外ガード=**つ助数詞**(7つ=ナナツ): 数詞読みの直後が「ツ」なら分割せずヘボン→`nanatsu`(4つ=ヨツ/ヨッツはヨンと別音で自然にヘボン=`yotsuba`)。 ★注意=数字+助数詞のsandhi(100回=ヒャッカイ)で hepburn置換が不安定→clean cases優先、 怪しいのはflag。 ★金色のガッシュ例で**フリガナ層の残り誤読(金色=キンイロ、本来コンジキ)**も露呈=slugは「フリガナ→ローマ字」なので**最終適用前にフリガナ健全性チェック**要(NDL監査で大半済・残り少数、 merge[gap c]でも解消)。 [[furigana_ndl_audit]]。
