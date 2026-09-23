---
name: seo-structure-gaps-2026-09-04
description: 2026-09-04 アクセス向上の構造相談=実測(28日訪問230・Google20/Bing30閲覧)と穴7点の順位。1〜4と6は適用済(機能蒸留待ち)=ジャンル面title/作品頁チップ/雑誌・出版社・年ハブ850面/ジャンル下位面219/anime二重サフィックス/list静的シェル。残=5(著者頁の薄さ)と7(頁の重さ)。8〜11(メタdesc重複/alt/title長/OG画像)は是正済=**週次待ち**
metadata: 
  node_type: memory
  type: project
  originSessionId: 981cfdce-d412-49dd-a505-855ea2bffe35
  modified: 2026-09-23T03:27:34.947Z
---

ユーザ相談「mangalの構造でアクセスを上げるためにやっておいた方が良いこと」(2026-09-04)。
実測(cf-analytics web 28日): 訪問230 / 閲覧1,350、流入は内部遷移1,120・直接180・**Bing30・Google20** = 検索にまだ載っていない。

## 穴(効果順)と状態
1. ✅ **ジャンル面32頁のtitleが全部既定** → `app/genre/[key]` generateMetadata で件数/完結数/代表作3つから title(`◯◯漫画 おすすめ一覧（人気順・N作品）`・「4コマ漫画」等は漫画二重にしない)/description/OG。commit c44360ea9。
2. ✅ **作品頁66k枚→ジャンル面への可視リンク0本**(チップが `/browse?genre=` 行き止まり) → `/genre/[key]` へ。同commit。★`components/DailyBits.tsx` のジャンルリンクは `/browse?genre=` のまま(ホームは別途32本の/genre/リンクを持つ)。
3. ✅ **雑誌・年・出版社ハブ面**(commit 4a916dec1): `lib/hubs.ts` が**単一ソース**(対象・閾値・頁割り300件・title/description文言)。
   - `/magazine`, `/magazine/<key>[/<n>]`(3作以上・連載開始年順) / `/publisher`, `/publisher/<key>[/<n>]`(50作以上≈99社・人気順) / `/year`, `/year/<yyyy>[/<n>]`(5作以上・人気順)。
   - ★年別は「年を持つ全作品」を静的列挙 = 作品頁への内部リンク(孤児頁の発見経路)。本番規模実測: 雑誌84・出版社275・年269 HTML(kodansha 32頁/2026年 9頁)、1頁≈420KB(RSC payloadが66%)・br圧縮後≈40KB・300行/391リンク。
   - 行=`components/HubRow.tsx`(題/ヨミ/著者→著者頁/年/巻数/連載誌→雑誌ハブ。年・出版社は文字のみ=同ハブへの重複リンクを撒かない)、本体=`components/HubListPage.tsx`(パンくずJSON-LD+全頁番号の頁送り=深い頁も1クリック)。
   - 作品頁チップ(出版年/出版社/連載誌)は `hubHrefIfExists` でハブが在る時だけ、無ければ従来の `/browse?` へフォールバック。フッターに入口3本。
   - `_gen-sitemap.py` は **out/ の実在HTML**から拾う(閾値をPythonに再実装しない=titles-pagesと同じ原則)。実測 ハブ850 URL。sitemap反映は週次。
4. ✅ **ジャンル面の肉付け**(同commit): `/genre/<key>/completed` と `/genre/<key>/<yyyy>s`(10作以上の組=**219面**、人気順上位120のグリッド) / グリッドの著者名→著者頁リンク(`components/GenreGrid.tsx`、<a>入れ子回避で著者行を分離) / 主な連載誌→雑誌ハブ(8本) / 他31ジャンル横リンク。preview実測: /genre/action に著者120・雑誌8・他ジャンル31・下位面6。
5. ⬜ **著者頁2万枚の薄さ**(サンプル=作品3本+索引1本)。sitemap を2作以上に絞るか文脈を足すか、要裁定。
6. ✅ 細部(commit 6a82c40b2): `app/anime/page.tsx` と `app/anime/[season]/page.tsx` の title 末尾「- MANGAL」を除去(二重サフィックス。08-31是正の取りこぼし2頁、grepで他に残りなし)。`/list` は generateMetadata「漫画 全作品一覧表（N作品）」+ description、サーバ描画の説明文と常設「索引から探す」(題名/著者/雑誌/出版社/年/新刊/アニメ+ジャンル32+主な連載誌8)=可視401字・作品導線0本の穴を塞いだ。sitemap には残す。
8. ✅ **メタディスクリプションが重複**(2026-09-11 ユーザ相談「同じのが多過ぎ?」)。
   実測 = 重複頁 **22,039(31.8%)**、最大塊は「全1巻で完結。」を **8,845頁**が共有。
   原因 = `desc = ${巻数フレーズ}${catch || synopsis || ""}` で、題名入りの定型文が
   **nVols===0 の時しか使われない**。巻はあるが catch が無い頁(42.5%)は巻数フレーズだけが
   残り、発売日が年月精度(旧作)だと日付の文も付かず8文字になる = **一番助けが要る頁に
   定型文が届いていなかった**。
   対処(commit 11720eb5e)= catch/synopsis が無い時だけ `seoFactSentence` で事実を書く:
   「『題名』は著者によるジャンル漫画。掲載誌連載、出版社刊、開始年〜。全巻の発売日・ISBN・書影を掲載。」
   ★題名を必ず入れる(同じ著者×ジャンル×出版社×年で固まる。赤塚不二夫で24頁実踏)。
   ★`publisher`/`magazine` は**キー**(shogakukan / big-comic)= masters の表示名に直す(実踏)。
   catch が在る頁(57.5%)の挙動は不変。実測 **固有 72.1% → 100.0% / 重複 22,039 → 54頁**。
   残54頁は catch 文そのものの重複(別問題・[[catch_side_wrong_work_class]] 系)。
   検出器 = `scripts/_audit-meta-description-dup.py`(page.tsx と同じ式を再現。月次未登録)。
   ★**長さ**も直した(commit 68109904b): 上限120字に対し45%が80字未満・11%が60字未満だった。
   catch を持つ頁で84字未満の時だけ「掲載誌・出版社・刊行年」を足す(catch 無しは事実文に既に在るので足さない)。
   実測 中央値 82→87 / 50字未満 3,296→475 / 60字未満 7,313→2,457。
   ★同時是正(commit 1a8b635be)= 「全M巻で完結。最終巻N巻は…」の **M≠N が 2,749頁(6.1%)**。
   最終巻を「発売日が最も新しい巻」から取っていたため、後ろの巻の日付が年月精度/欠落だと
   途中巻が最終巻を名乗った(赤いペガサス=全14巻なのに最終巻7巻)。うち1,588頁は版が1つだけ
   = 版混在ではなく日付の粗さが原因。**巻番号が最大の巻**の日付で言い、完全な日付が無ければ
   文ごと出さないよう変更。実測 2,749 → 0、文が出る頁は 45,021 → 45,411 で減っていない。
   ★**反映は週次蒸留(フルビルド)**。機能蒸留は非漫画面だけなので**届かない**(1〜4,6 とは経路が違う)。
9. ✅ **書影のaltが全サイトで同一**(2026-09-14 ユーザ指摘)。作品頁の書影が `alt="第1巻"` で
   作品名を含まず、**66,000頁すべてで同じ文字列**だった = 数十万枚の画像資産がGoogle画像検索から
   一切拾われず、スクリーンリーダーでも無意味。commit 0e2d1244b で `{作品名} 第N巻 表紙` に。
   ・`VolumeCoverflow`(巻サムネ/主書影/版タブ)= title は既にpropに在り配線のみ。
   ・`CoverLightbox` の `label` は**拡大時のキャプションとして表示**される → 画像altは別prop(alt)に分離。
   ・alt="" だった書影に充填: ColorCorner / DailyFeatureCorner(URLだけ持っていたのを[書影,題名]へ) /
     TokushuClient×2 / adult-triage。★`AiReviewSection` の alt="" は**据置きが正解**
     (AI書評家のドット絵アバター=書影ではない装飾画像)。
   ・EditionCorners/MangaCard/VolumeTile/GenreGrid 等は既に作品名入り=変更不要。
10. ✅ **titleが長すぎて稼ぎ頭の語が表示外**(2026-09-14)。実測 中央値**48字**・**全頁が35字超**・最長**272字**。
   旧 `題名 | 著者 - 全N巻の発売日・全巻一覧` は著者名の長さぶんだけ「全N巻」「発売日」が
   日本語SERPの表示枠(≒30〜35字)から落ちていた(超絶フリテンくんで実踏)。
   commit 68109904b で **`題名 全N巻の発売日・全巻一覧 | 著者`** に語順変更 + **著者は2名まで+「ほか」**
   (アンソロジーで15〜20名並んでいた)。実測 中央値48→46 / 最大272→143 / 50字超 20,636→13,641。
   ★サフィックス「| 漫画・コミックのMANGAL」は裁定済のため**維持**([[seo_title_suffix_decision]] A案)。
   ★title の重複は元から4頁のみ = 問題は重複ではなく**長さと語順**だった。
11. ✅ **OG画像が無い頁**(2026-09-14)。`images` を出していたのは作品頁だけ、しかも書影が在る時だけ。
   書影ゼロの作品頁 **10,837件(15.7%)** + ジャンル32面/ハブ850面//list//shinkan/著者2万頁/ホームが
   **全部画像なし** = SNSやチャットで真っ白。commit 68109904b で `public/og-default.png`
   (1200x630・D3テーマ黒×アシッドライム)を追加し root layout に既定を設定、作品頁は書影が無い時に
   **明示採用**(継承の上書き規則に依存させない)。★`output: "export"` なので ImageResponse は使えず
   **静的PNG**(生成器 `scripts/_gen-og-default.py`)。favicon(`app/icon.png`)は元から在った。
7. ⬜ 作品頁の重さ: ★実測訂正= 本番 one-piece 生HTML **341KB**(br圧縮後32KB)、JS 563KB。RSCペイロード重複は Next app router の構造(ハブ面でも66%)。中期。

## ユーザ側スイッチ(未実施)
- ~~Cloudflare Crawler Hints~~ → **IndexNow は自前送信に切替**(2026-09-04 ユーザ裁定。Worker+R2 では Crawler Hints が発火しない疑い。[[indexnow_self_submit]])。残るユーザ側= Bing Webmaster Tools に sitemap 登録。
- 本番待ちの機能蒸留(/shinkan静的化・ナビ改訂・本件1〜4)を出し、GSCで /shinkan 系と /magazine /publisher /year のURL登録リクエスト。

## 実装時の罠(実踏)
- ★`ls -l` の第5列はこのPCでは**グループID(197121)**(所有者名「chiba shuichi」に空白があり列がずれる)。サイズは `stat -c %s` で取る(1と2の相談時に「HTML 197KB」と誤報した)。
- ★ローカルで `npx next build` を素で回すと DATA_DIR=data → `data/manga`(**旧世代・romaji無し**)を読み、著者マップが空になり author/ が `_empty` だけ・著者リンク0本になる。本番/機能/previewは MANGAL_DATA_DIR の staging(manga= manga.v2 のhardlink)を使うので問題ない。検証は preview か `_deploy-feature.py --dry` で。
- Bashツールの heredoc は `\\'''` を `\'''` に化かす(2回目の実踏)。編集スクリプトは Write で書いて python 実行、置換は CRLF を LF に正規化して照合(app/components/scripts は CRLF 主体)。

**Why:** 外部被リンクを待つ間に、クローラが辿れる内部構造と着地面ごとのtitleを増やすのが自力で効く唯一の柱。
**How to apply:** 5以降に着手する時はこの順で。コード変更は機能蒸留で本番へ(sitemapは週次)。ハブの閾値/文言を変えるなら lib/hubs.ts だけ。関連: [[seo_index_coverage_state]] [[seo_release_date_pages]] [[seo_title_suffix_decision]] [[inflight_state_2026_09_01]]

## ★2026-09-23 ジャンルチップの行き先を再確認(ユーザ相談「前は検索フィルターが開いた方が自然」)
- **チップは /genre/<key>(ハブ面)のまま**(66k頁→ハブの内部リンク。GSC実測で作品頁の登録4%に対しハブ60% = 今Googleに効く数少ない経路)。
  ★**2026-09-23 訂正**: 「ハブ60%」は n=5(`/`・`/shinkan`・`/browse` が登録)で、`/genre/action` は未登録だった。
  新ハブ54件の抜き取りは**登録0件** = Googleに効くという根拠は無い。チップの行き先を /genre/ にしておく理由は「人の導線+クロールの発見経路」だけ([[seo_index_coverage_state]] 09-23節)。
  代わりに検索への入口を2つ足した: ジャンル面「この条件で検索・絞り込む」(6500222a8)/ 作品頁「同じジャンルの漫画を探す」
  = 作品の全ジャンルAND(3e2d892e0)。クローラと人で行き先を変える(JSで横取り)案は不採用。
- ★**要素(theme)のハブ面は存在しない**。上の「ジャンル下位面219」は **完結済み/年代別だけ**(`app/genre/[key]/[sub]`)。
  私が一度「要素チップもハブ優先に揃えられる」と誤って提案した。揃えるには要素ハブを新設する規模の工事 → **作るかはユーザ判断・未回答(保留)**。

