---
name: inflight-state-2026-09-01
description: 【本番待ちの台帳】★2026-09-23 全集title作品一覧化+robots /api/ 遮断=機能蒸留待ち。2026-09-08の週次で検索残務/発売日SEO面/ハブ850面/PC共通シェルは公開済。★2026-09-14 追加=SEO基本4件(メタdesc/最終巻/書影alt/title・OG)が週次蒸留待ち(機能蒸留では出ない)
metadata:
  type: project
---

## 本番待ち(=「機能蒸留して」で出る。dry-run 3回 build OK・同期計画 約41,000 PUT)
1. 検索残務2点(64cac8eda): HomeSidebar の haystack/別名先読み + ListClient の useSearchParams 同期初期化(Suspense境界)。
2. 発売日SEO面(5f3dc9ad6→26918912b): /shinkan 静的化(今月焼き込み)+ /shinkan/YYYY-MM(23か月)+ /shinkan/this-week + /shinkan/next-month + 解説文 + 作品頁description(発売予定/最終巻)。詳細=[[seo_release_date_pages]]。
3. アニメ季節コーナー(データ): 結線3,282→3,440・2026秋37→52作・両載せ(薬屋/やはり俺)。view JSONは週次で再生成=週次で出る。詳細=[[animatetimes_season_source]]。
- preview には薬屋2頁/やはり俺2頁/まどマギ頁を投入済(subset 12頁前後)。

## 公開後の手作業(ユーザ)
- GSC URL検査で `/shinkan`・`/shinkan/this-week`・`/shinkan/next-month`・`/shinkan/2026-09`・`/shinkan/2026-10` を「インデックス登録をリクエスト」(1日10件前後)。
- sitemap は機能蒸留では更新されない(除外対象)=月別URLが載るのは**次の週次蒸留**。その後 GSC で sitemap.xml を再送信。GSC画面の「69,441/08-30」は週次前の旧読込=削除不要。

## 未決・宿題
- makai-tenshou(魔界転生とみ新蔵版)= promote が db-v2 で series not found → 8/21から再生成不能(anilist:false が届かない)。要検死。
- アニメ nopage台帳194件(登録候補)/ B13(OVA形式がハーベスト対象外=岸辺露伴型)。

## 追記 2026-09-02: /shinkan 年月ナビの固定2行化(年チップ1行+月行横スクロール+当月へ初期スクロール)= preview確認待ち→機能蒸留で本番へ(コードのみ: components/ShinkanMonthNav.tsx, app/shinkan/this-week/page.tsx)


## 追記 2026-09-02(夜): アップ直前リハーサル済み([[weekly_rehearsal_2026_09_02]])
- step1→preflight→CODE週判定→フルビルド42分→sitemap→`_r2-sync.py --dry --prune`(PUT 180,880/削除136)まで通した。**R2/KV/finalizeは未実行**=上記1-3は依然「本番待ち」。
- 本物の「週次蒸留して」の前にやること: ①未反映書影337頁の反映(`docs/production-diagnostics/cover-override-unreflected-2026-09-02.txt` を `_promote-bulk-v2.py --only-file`) ②アイドル書影ジョブ(`_placeholder-cover-refresh.py --all`)を止める ③`--prune` 必須(台帳41件・実削除40頁)。
- 連鎖alias3本(スゴ盛)は是正済(8de66d807)。ps1ラッパはUTF-8化済。

## 追記 2026-09-02(夜): ヘッダーナビ改訂も本番待ち(コードのみ=機能蒸留で出る)
- ユーザ裁定: 「一覧」アイコン廃止、右クラスタを **検索→新作(/shinkan 今月の新刊一覧)→AI書評→過去ログ→使い方** に(ホームは左端固定のまま)。≡メニューの中身は不変。
- 実体は**2か所**(片方だけ直すとホームと他頁でズレる): ホーム=`app/home-design-12/page.tsx` の D3Nav / 他全頁=`lib/homeDesign.tsx` の DesignNav。コミット 227a3077f。preview で両方の並びを実配信HTMLで確認済。
- /list はメニュー「一覧表(全作品)」とフッターに残置(頁自体は削除していない)。

## 追記 2026-09-04: SEO構造是正2点も本番待ち(コードのみ=機能蒸留で出る)
- ジャンル面32頁の頁別title/description + 作品頁ジャンルチップ→/genre/[key](commit c44360ea9)。詳細と残レバー=[[seo_structure_gaps_2026_09_04]]。

## 追記 2026-09-04(午後): 雑誌/出版社/年ハブ850面+ジャンル下位面219も本番待ち(コードのみ=機能蒸留で出る、sitemap反映は週次)
- commit 4a916dec1。詳細=[[seo_structure_gaps_2026_09_04]]。機能蒸留の同期は out/ から manga/calendar/索引/sitemap を除く全ファイル=新ディレクトリ magazine/ publisher/ year/ genre/<key>/ も自動で載る。

## 追記 2026-09-04(夕): IndexNow 自前送信を配管(scripts/_indexnow.py + r2-sync/finalize/feature/differential にフック)
- 鍵ファイル public/efa08…txt は本番404のまま(次の機能蒸留/週次で R2 に上がる)。上がるまで送信は pending 保持。上がった後の最初の finalize/機能蒸留で自動送信が始まる。[[indexnow_self_submit]]

## 追記 2026-09-06: 今日のデータ変更(= 本番待ちに積み増し。次の週次蒸留で出る)
- トリニティセブン: 番外巻15.5(9784040721446)+ 11巻ブルーレイ付き限定版をvariantで併記。全34巻+15.5
- x.5の番外巻 7件を各頁へ: 30禁5.5 / アカメが斬る!1.5 / 兄に愛されすぎて困ってます4.5 /
  ろんぐらいだぁす!6.5 / 過剰妄想少年2.5 / モテキ4.5 / 範馬刃牙10.5
- 皆様の玩具です 1-3巻(ユーザ提供のNDL全件TSVで裏取り)。全9巻
- 悪役令嬢後宮物語～王国激動編～ 6,7巻(series-merge で3sid統合)。全7巻
- エイリアンヘッドバット 2巻(preorder-pages へ直接追記)。全2巻
- ★コード: .5巻を通す番人4か所 / 巻抜けの「1巻が無い」判定 + 入力を索引由来へ /
  カードの全N巻から小数巻を除外 / 孤児監査の照合4層+著者ゲート+索引の陳腐化自動検知 /
  新検出器 _audit-shu2-unlisted-volumes.py(月次サニティ登録済み)
- ★preview は **①のセット72頁**に入替済み(無作為3,000頁は退場)= [[unlisted_volumes_review_state]]


## 追記 2026-09-07: PC表示の全面是正(コードのみ=機能蒸留で出る。漫画頁ぶんは週次)
詳細と不変条件 = [[pc_shell_and_widths_2026_09_07]]。
1. 「電子書籍で買う」= 箱ごとタップでKindleと同挙動(70d4e1bba)★**漫画頁=週次でしか出ない**
2. /list の保守用チップ「slug修正のみ」撤去(7c26b1305)= 本番索引の `_slugfix_new` は 0/69,240 の死にボタンだった
3. ナビを layout へ一本化(1c0b29f20)= 47箇所の `<DesignNav />` 全廃
4. カテゴリ8枚をPCで1段+太枠1本の帯(894ee1b00 / 18e94f517)= ホームと /browse の**両方**(実体が別)
5. PC左レール = 検索窓 + 絞り込みパネルを全ページ(a9d8ade8a)★**漫画頁ぶんは週次**
6. 器を7種類 → 2系統に統一(9d7caea53・28ファイル)
7. 過去ログの全幅を是正(35432b083)/ /list はシェルで自動解決
8. PCの検索窓を左の1つに(2b42df8e6)
9. 本文の器をヘッダー/ナビと同じ 1152px に(00a51ea29)
- preview セット = **人気順 上位200頁**(2d5479efb)。



## ★2026-09-08 週次蒸留で**全部公開済み**(= 上の「本番待ち」は解消)

フルビルド 91,157ルート / R2 PUT 183,488 / prune 647 / 疎通 PASS 14・FAIL 0。
上記1〜3(検索残務・発売日SEO面・アニメ季節)に加え、ヘッダーナビ改訂・ジャンル面title/チップ・
雑誌/出版社/年ハブ850面・PC共通シェル(左レール+器の統一)も同時に公開。
**sitemap も 90,911 URL に更新済**(ハブ面852が初掲載)= GSC で sitemap.xml 再送信が可能になった。
IndexNow は 298 URL 受理(削除分の通知)。鍵ファイルも本番に載ったので以後は自動送信が回る。

### 残っているユーザ手作業(上の節のまま有効)
- GSC URL検査で `/shinkan` 系5本を「インデックス登録をリクエスト」+ sitemap.xml 再送信。

### 新しく見つけた小さな穴(未対応・裁定待ち)
- **sitemap に `/publisher/(unknown)` と `/publisher/(unknown)/2` が載っている**(90,911中の2URL)。
  publisher 未確定(preflight基準で339頁)の受け皿ハブがそのまま索引対象になっている。
  出さない方が良いなら sitemap 生成側で publisher スラグの除外が要る(次の機能蒸留級の変更)。


## ★追記 2026-09-14: SEO基本4件が**週次蒸留待ち**(= 機能蒸留では出ない)

★重要: これらは **作品頁66kのHTMLに焼かれる**ので、機能蒸留(非漫画面+チャンクのみ)では届かない。
「週次蒸留して」1回でまとめて出る。詳細は [[seo_structure_gaps_2026_09_04]] の 8〜11。

| commit | 内容 | 実測 |
|---|---|---|
| 11720eb5e | メタdescriptionの重複解消(catch無し頁を事実文で埋める) | 固有 72.1%→100.0% / 重複 22,039→54頁 |
| 1a8b635be | 「全M巻で完結。最終巻N巻は…」の M≠N を是正 | 2,749頁→0 |
| 0e2d1244b | 書影のaltに作品名(全66k頁が `alt="第1巻"` で同一だった) | 書影の空alt 0件 |
| 68109904b | titleの語順+著者2名上限 / 既定OG画像 / descriptionの余白 | title最大 272→143字 / OG画像なし 10,837頁→0 |

- 監査 = `python scripts/_audit-meta-description-dup.py`(公開前後の再測に使う)。
- OG画像の再生成 = `python scripts/_gen-og-default.py` → `public/og-default.png`。
- ★公開後にユーザ側でやること: GSC でトップと主要ハブの URL検査(title/description の再取得を促す)。
  サイト全体の title 変更なので**順位が数週間揺れうる**([[seo_title_suffix_decision]] と同じ注意)。

## ★追記 2026-09-14(夕): この日の変更も本番待ち

### コードのみ(= 「機能蒸留して」で出る)
- **ヘッダーのナビ「新作」→「新刊」**(fc21a3726)。行き先 /shinkan は不変。実体は
  `components/GlobalNav.tsx` **1ファイル**(2026-09-07 の一本化以降。旧記述の「実体は2か所」は無効)。
  ★NAV_SVG のキーはラベルで引くので、ラベルだけ変えると**アイコンが黙って消える**。
- **ホームのカレンダー + タイムマシンを完全撤去**(231ca7ef7)。
  CalendarView/TimeMachine/ReleaseCalendarMock を削除、public/calendar(1,251ファイル)削除、
  out/calendar overlay と JSON面同期からも除外。★`data/calendar` の生成だけは残す
  = /shinkan の入力 → [[calendar_ui_removed_data_kept_for_shinkan]]

### データ(= 次の「週次蒸留して」で出る)
- 日次蒸留(2026-09-14): 続巻163巻を種4へ / CONTINUATION 3件を per-case 転送
  (異世界魔術師 vol7+8 ・俺の召喚魔法 vol2 ・部長の夜テク vol12) /
  発売日ドリフト3件適用(★陰陽廻天 Re:バース 2巻が 2026-11-20 → **2027-11-22** の367日延期) /
  ひかりめぐりまたたいて 下巻を preorder-pages seed へ直接追記(上下巻1頁に統合)
- **preview に日次ドラフト116頁**を投入済(レビューシート `.cache/review-sheet.html` 送付済)。
  この116頁は**まだ本番化していない**= 確認GO後に `_preorder-promote-drafts.py`。
- 非掲載 deny 10件(ガイドブック/画集/手塚の既刊再編集2/多人数アンソロジー2/コンビニ再録2/欧州BD翻訳/ドキばぐ闇鍋編)

### 裁定待ち・宿題(この日に見つけた)
- ★**源なし manga.v2 孤児頁 414件**(`.cache/orphan-source-pages-2026-09-14.txt`)。
  次のフルpromote(月次)で**黙って消える**層。一括復元は大規模=GO待ち → [[orphan_source_pages_restored]]
- **鎌倉ものがたり・推理編 ぶんぶく茶釜** の既存頁が、今回denyした魔界編と同じ
  Coinsアクション(コンビニ廉価の既刊再編集)。新規は機械で止めたが**既存頁の扱いは未裁定**。
- **R2 prune 待ち**: `calendar/**`(読み手の居ない死蔵物)を `data/seeds/pending-r2-prune.jsonl` に記帳済。
- NDL新着の掲載可2件(クズ女子…NOiPA編 / 黒革と悪人)は**あらすじ材料が楽天に無く保留**。
  捏造しない=ゲートの正しい動作。材料が要るなら skill `external-enrich` の守備範囲。

## ★追記 2026-09-23: 本番待ち(コード+索引。★週次蒸留で出すのが正)
1. ジャンル面「この条件で検索・絞り込む」ボタン(6500222a8)+ 作品頁「同じジャンルの漫画を探す」ボタン(3e2d892e0)= コードのみ。
2. 検索の読み込み高速化(c959290b9 + f4244ef06)= 詳細 [[search_perf_hotspots_2026_08]] の 2026-09-23 節。
   ★列形式索引 `manga-list-cols.v1.json` は **r2-sync(週次)/差分反映 だけが上げる**。機能蒸留は索引に触れない
   ので、機能蒸留だけで出すと新コードは行配列へ自動フォールバック(壊れないが転送は減らない)。
   → 週次蒸留で出す。週次後の確認 = `curl -sI https://mangal-db.com/manga-list-cols.v1.json` が 200。
3. 索引の「毎回確認」(workers/r2-serve.js)= **Worker コードの変更 → 週次蒸留で `npx wrangler deploy -c wrangler-r2.jsonc` を忘れずに**
   (R2同期はファイルだけ=Worker は別デプロイ。weekly-distill skill の手順に既にある)。詳細 [[index_json_browser_cache_stale]]。


## 追記 2026-09-23: SEO小物2点が本番待ち(コードのみ=**機能蒸留で出る**)
- 全集10頁の title を「<作家> 作品一覧(<全集名> 全N巻)」に(d302c8b10)。作家名は `_gen-zenshuu-data.py` の AUTHOR が単一ソース。カムイ伝全集は従来形。
- robots.txt に `Disallow: /api/`(同commit)。根拠 = 9/22 Googlebot 174件中56件が /api/like。
- 効果測定: Bing「水木しげる 作品一覧」(9/23時点 8.9位・クリック0)を `_bwt.py queries` で追う。
- 道具: `_bwt.py crawl` を是正(94ee82e90)= 登録数(InIndex)+前日比を表示。★9/22 Bing登録 5,236。
- `/authors` 分割(6f0a8f17b)= 目次86KB + `/authors/<行>-<n>` 72枚。**機能蒸留で出る**(分割頁の sitemap 掲載は次の週次)。
  出たら GSC で `/authors` の登録リクエストをやり直す(ユーザ作業)。
- ★機能蒸留の staging に titles-pages.json が無かった → 追加+ビルド入力欠けで abort する番人(0ea46b206)。
  直す前の機能蒸留だと本番 /titles を空頁で上書きしていた。
- ★**2026-09-23 ユーザ裁定: 上の3点(全集title・robots /api/・/authors分割)は機能蒸留せず次の週次蒸留で出す。**
  週次の経路で問題なし: zenshuu-view.json は repo の data/ を静的import(staging非依存)/ robots は public/ /
  /authors分割と sitemap の分割頁72件は週次のフルビルド+_gen-sitemap で載る(titles-pages は週次 preflight INDEXES で既に同期)。
  週次公開後のユーザ作業 = GSC で `/authors` の登録リクエストやり直し + 全集10件(4日目分)。
- 関連作品の見直し + 差分反映の全件データ化(22fa5f9d5)= **週次で出る**(漫画頁コード変更)。週次後は差分反映が ~15分になる。
- 表示速度2点(383d53ec8)= 巻サムネ3重SSR廃止 + ドット体フォントCSSを全頁から外す。**週次で出る**。preview に ONE PIECE を追加(ループ確認用)。
- EditionVolumes に題名だけ渡す(RSC の作品データ重複を除去・約130MB)= **週次で出る**。

## 追記 2026-09-24: ランキング是正+ホームのアニメ季節(★週次蒸留で出る)
- ランキング「今年完結した大作」: こち亀(連載終了2016)を status-corrections で year_ended 2016 に /
  「チキン型」=後から足した巻で完結判定をやり直す処理を promote に追加(c31dc0c54)。targeted反映10頁済
  (6頁→連載中・2頁 year_ended 2026)。/rankings はビルド時集計なので**本番に出るのは週次**(作品頁も週次)。
- ホームのアニメ季節コーナー: ビルド時の季で固定されていた → 今季+次の季を渡しJSTで切替(コードのみ)。
  出れば以後はビルド日に関係なく季の境目で切り替わる。機能蒸留でも週次でも出る。
