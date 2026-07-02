---
name: distill-2026-pipeline
description: 2026新刊蒸留の一連の流れ(NDL発見→preview生成→3段fill→AI enrich)。月次蒸留で再利用する完全手順とスクリプト
metadata: 
  node_type: memory
  type: project
  originSessionId: 40db3460-5533-4358-8d06-8214ea9ecaea
---

2026新刊蒸留(NDL由来の新刊をテストページ化)の**完全フロー**。次回月次で再利用する。種2(db-v2.sqlite)不変・preview(.preview-data)のみ。

## パイプライン(順序厳守)
1. **発見** = `_ndl-discovery.py` → `data/seeds/ndl-discovery-2026.tsv`(NDC726.1の月分割+再帰日付分割。 列=isbn13/date/publisher/series/volume/title/kana/creators/**creators_roled**[dc:creatorの役割=原作/作画/著等])。題長は120(アンソロ標記の取りこぼし防止)。
2. **生成** = `_distill_preview.py` → `.preview-data/manga/*.yml`(★中核。 下記の判定を全部やる)。
3. **索引** = `_build-list-index.py .preview-data/manga .preview-data` → list/search索引(`solo_nonfirst`=1冊≠1巻 / `vol_gap`=巻抜け フラグ付与)。
4. **両置き** = 索引を `public/` と `.preview-data/` 両方にcp(appはpublic/から読む)。
5. push → mangal-preview.pages.dev 自動デプロイ。

## `_distill_preview.py` の要点(生成器)
- slug=`kana_slug`(pykakasi)。 `base_title`=末尾巻番号除去(「. 8」「[8]」「**空白+末尾数字**=! 14型」)。 題密着数字(ゴルゴ13/K-9/Season2)は空白無で保護。
- **型1統合**: `psl = INTEGRATE_OVR or prod[norm(title)] or prod_kana[norm(kana)]` で本番ページ照合→既存全巻取込(1巻問題解消)。 既存の**title/kana/publisher/year/catch/synopsis を尊重継承**(t1_*)。 added==0(reprint誤マッチ=ドカベン型)はskip。
- **除外(skip)**: adult(distill-adult-2026.tsv+publisher検出) / コンビニ / 非漫画(NONMANGA_TITLE/SERIES正規) / アンソロ(方針=今は出さず後で安全統合) / leed・扶桑社で楽天不在。
- **FILL統合**: `FILL[slug]` の巻を番号でmerge。 ★`1<=number<=500`サニティ(年コード2012等除外)。 最古巻へ開始年繰り上げ。
- **synopsis** = `t1_synopsis(本番正規=AI要約済) or SYNOPSIS_GEN[slug](新作AI要約) or None`。 ★**楽天caption丸写し(verbatim)は廃止**(著作権)。
- **catch** = `t1_catch(ゴルゴ等既存尊重) or CATCH_GEN[slug](catch無のみAI生成) or None`。
- **書影チェック待ち** = 未来発売(release_date>今月)で書影無→`_cover_pending`、 全未来発売を `cover-recheck-2026.tsv` に記録(月次で書影再取得)。

## 3段fill(巻の埋め残し補完。 [[madb_cm104_frozen]]で新刊シリーズ链0%が前提)
1. `_distill_fill.py` = **NDL題検索**(通常)。
2. `_distill_fill_byauthor.py` = **NDL作者検索＋既存ISBN錨**(題揺れ=アウト→OUT/汎用題。 ISBN錨で続編の自シリーズだけ取得=原作と非merge)。
3. `_distill_fill_rakuten.py` = **楽天ブックス題検索**(★NDL欠の巻を楽天が持つ=ガンダムSEQUEL vol5型。 既存FILLと**和集合merge**)。
- 書影 = `_distill_fill_covers.py`(楽天BooksBook→distill-enrich-2026.jsonl追記)。
- ★順序注意: byauthorは**上書き**、rakutenは**和集合**。 byauthor後にrakuten実行で取りこぼし最大化。
- 結果: **solo_nonfirst 130→0 / vol_gap 21→0**(誤merge・過統合なし。 著者一致+ISBN錨+題一致で担保)。

## AI enrich(Workflowツールで分散。 closed vocabulary厳守)
- **genre再分類** = vol1導入文(fill後synopsis)→master32キー再分類。 `distill-genre-ai-2026.json`。 巻数増で精度向上(283/630変化)。 [[ai_genre_closed_vocabulary]]
- **catch生成** = catch無のみ synopsis→60-100字惹句(本番ゴルゴスタイル)。 `distill-catch-2026.json`(432作)。
- **synopsis要約** = 元detail無の楽天caption→著作権安全な60-120字言い換え。 `distill-synopsis-2026.json`(421作)。 [[synopsis_ja_seed]]
- 各workflow: `.cache/<x>-batches/batch-NNN.json`(50件/batch)を並列agentで処理→merged seed保存→生成器が配線→再生成。

## テスト環境専用UI(本番非表示=isPreview判定)
- 診断ボタン: 画像なし/1冊≠1巻/複数巻/著者なし/複数巻2026/巻抜け/コピー(TSV出力)。 `HomeClient.tsx`の`isPreview`(hostname.includes preview)。
- catch表示: preview=`.preview-mode .catch-clamp`で5行(本番カードは4行)。

## 主要seed(data/seeds/)
distill-{adult,drop,integrate-override-,fill-,enrich-,author-supplement-,genre-ai-,catch-,synopsis-}2026 + cover-recheck-2026.tsv + ndl-discovery-2026.tsv。

## ★落とし穴(404転落=loadDataのsafeParseは厳格)
- loadData(line47)=`MangaSchema.safeParse`、 **失敗ページはskip→詳細404**(一覧索引は寛容で出るので「リンク切れ」に見える)。
- **null禁止**: `synopsis: z.string().default("")`はnull不可(defaultはundefinedにのみ効く)→ **synopsisは`""`、 catchは`z.string().optional()`もnull不可→Noneならキー削除**(undefined化)。 ★Noneを書くと54件まとめて404に転落した。
- **数値/bool風の文字列名**(作画家「029」等)はPyYAMLが無引用出力→**JS側yamlが数値誤読→schema違反404**。 生成器に強制引用representer(`_str_rep`)済。
- ★検証法: `npx tsx`で`MangaSchema.safeParse`を全preview実行(importは拡張子無し`./lib/schema`)→弾かれ0を確認してからpush。 一覧に出る≠詳細が出る。

## 確認方法(公開せず)
本番フル(69k・索引47MB)は重い→**確認は蒸留(.preview-data=698件・0.5MB)だけ**で速い。 ローカルは `MANGAL_DATA_DIR=.preview-data npm run dev`。 本番化は別途promote(未実施=preview止まり)。


## 2026-07-02 後退蒸留ツール化(`scripts/_distill_backward.py`)
- ★3段stage: **--discover**(NDL live=_ndl-discovery委譲・throttle中は回さない) / **--plan**(オフライン: 漫画性フィルタ→既存作A/新規作B仕分け→楽天キャッシュenrich→掲載ゲート→AI worksheet+欠落表) / **--emit**(worksheet検証→previewページ生成=テスト先行→被覆台帳記帳)。
- **掲載ゲート**(ユーザ裁定): 必須メタ完備(題/ヨミ/著者/年/genre/status/demographic)+**楽天書影v1あり**=掲載。不足=欠落表(何が足りないか明記)。fail-closed。
- **漫画性フィルタ**=`_promote_drop_patterns.py`(共有モジュール: CLAUDE.mdのdropパターン+NDL FP型=研究書/』論/図録/画集/インタビュアー役割/絵と文)。+worksheet側is_manga=false最終ゲートの**二重化**。
- 2024smoke実測: discovery1400行→フィルタ後1333→既存作の巻330(A=種4候補・別route)/新規作964→**掲載可250**(AI worksheet待ち)/欠落711(巻不連続=全巻回収要530・v1書影無591・題不一致等)。
- ★worksheet形式=.cache/backward/<year>/ai-todo.jsonl {TODO:{is_manga,slug,genres,catch,synopsis,demographic}}。emit検証=closed vocab/slug衝突/demographic enum。
- 残設計: A route(既存作の巻)→種4ガード付き投入 / 巻不連続→NDL title+creator全巻回収(live) / 楽天miss→live補完 / 日次蒸留=同コアでcursor運転(未実装)。


## 2026-07-02 日次蒸留(skill化1号)
- ★`scripts/_distill_daily.py` = 後退蒸留コアの薄いカーソル運転: --discover(当月NDL live・月初3日は前月も・**429検知で即中断exit2**) / --plan(年plan冪等再実行→**カーソル差分レポート**=新規掲載可/新規欠落/累計→cursor自動更新)。emitは後退と共通。
- カーソル=`data/seeds/distill-cursor.json`(git追跡)。
- ★**正式skill** `.claude/skills/daily-distill/SKILL.md`(トリガー「日次蒸留して」・NEVER=429連打/捏造/単巻先行/closed vocab外・成功判定つき=弱いモデル耐性設計の1号)。
- smoke(2026): 掲載可worksheet待ち34(6月蒸留以降の新着)/欠落319。本番化(種2 INSERT-only --commit)は未実装=preview確認まで。
