---
name: seo-structure-gaps-2026-09-04
description: 2026-09-04 アクセス向上の構造相談=実測(28日訪問230・Google20/Bing30閲覧)と穴7点の順位。1〜4と6は適用済(機能蒸留待ち)=ジャンル面title/作品頁チップ/雑誌・出版社・年ハブ850面/ジャンル下位面219/anime二重サフィックス/list静的シェル。残=5(著者頁の薄さ)と7(頁の重さ)
metadata: 
  node_type: memory
  type: project
  originSessionId: 981cfdce-d412-49dd-a505-855ea2bffe35
  modified: 2026-09-04T06:41:01.312Z
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
7. ⬜ 作品頁の重さ: ★実測訂正= 本番 one-piece 生HTML **341KB**(br圧縮後32KB)、JS 563KB。RSCペイロード重複は Next app router の構造(ハブ面でも66%)。中期。

## ユーザ側スイッチ(未実施)
- Cloudflare **Crawler Hints**(IndexNow自動通知・無料・1クリック)+ Bing Webmaster Tools に sitemap。Bing流入>Google の現状では即効。
- 本番待ちの機能蒸留(/shinkan静的化・ナビ改訂・本件1〜4)を出し、GSCで /shinkan 系と /magazine /publisher /year のURL登録リクエスト。

## 実装時の罠(実踏)
- ★`ls -l` の第5列はこのPCでは**グループID(197121)**(所有者名「chiba shuichi」に空白があり列がずれる)。サイズは `stat -c %s` で取る(1と2の相談時に「HTML 197KB」と誤報した)。
- ★ローカルで `npx next build` を素で回すと DATA_DIR=data → `data/manga`(**旧世代・romaji無し**)を読み、著者マップが空になり author/ が `_empty` だけ・著者リンク0本になる。本番/機能/previewは MANGAL_DATA_DIR の staging(manga= manga.v2 のhardlink)を使うので問題ない。検証は preview か `_deploy-feature.py --dry` で。
- Bashツールの heredoc は `\\'''` を `\'''` に化かす(2回目の実踏)。編集スクリプトは Write で書いて python 実行、置換は CRLF を LF に正規化して照合(app/components/scripts は CRLF 主体)。

**Why:** 外部被リンクを待つ間に、クローラが辿れる内部構造と着地面ごとのtitleを増やすのが自力で効く唯一の柱。
**How to apply:** 5以降に着手する時はこの順で。コード変更は機能蒸留で本番へ(sitemapは週次)。ハブの閾値/文言を変えるなら lib/hubs.ts だけ。関連: [[seo_index_coverage_state]] [[seo_release_date_pages]] [[seo_title_suffix_decision]] [[inflight_state_2026_09_01]]
