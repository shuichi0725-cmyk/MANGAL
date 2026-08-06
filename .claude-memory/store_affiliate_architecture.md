---
name: store_affiliate_architecture
description: 収益設計=作品→読めるストア連動。楽天API(無料・gate無)起点、e-bookは検索deep-link、収益本命は電書ストア初回特典ASP
metadata: 
  node_type: memory
  type: project
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

MANGAL の収益の心臓部 = 各作品ページに「**この作品が読めるストア一覧（初回クーポン付き）**」を DB 連動で出す。 比較ハブ単独でなく **7万作品DBに紐付ける**のが既存アフィに勝てる唯一の moat。 設計詳細 = `docs/store-affiliate-architecture.md`、 設定源 = `data/seeds/stores.yml`。

**現状(2026-06-04)**: ISBN-13 89%充足(341,621/382,704)。 書影0・Amazon(asins/amazon_metadata)空。 ★**楽天fetch script既存**(`fetch-rakuten.ts`/`-bulk.ts` = BooksBook/Search で title+author→ISBN/largeImageUrl(書影)/salesDate)。 楽天API=無料・売上gate無。

**核心の判断**:
- ★**収益はAmazon per冊(数%/18円)でなく、電書ストアの初回登録・初回購入(ASP数百円/件)**が本命。 「全ストア登録がお得」は各ストアの初回クーポンが本当にお得なので**正直に書ける**(煽りでない=信頼=持続)。
- ★**Amazon PA-APIは3件/180日の売上gate**があり後回し(Phase2)。 **楽天API(無料・gate無)で書影+リンクを先に**取れば、書影問題と楽天送客を同時解決。
- ★**e-bookは文言検索が曖昧→product直リンクは誤マッチ危険→「ストア内検索結果へのdeep-link」を既定**(誤リンク0で全作品カバー)。 product精密化は書影が要る楽天/Amazonと高traffic作のみ。
- ★**法務必須**: ステマ規制(2023-10〜・景表法)で**広告/PR表記が義務**。 クーポン条件・上限は正確に。

**段階**: Phase1=楽天bulk(書影+リンク)+検索deep-link funnel+ハブページ(無資格無料で収益funnel成立) → Phase2=Amazon PA-API(売上gate後) → Phase3=DMM(初回90%OFF=高転換) → Phase4=高traffic作の価格比較精密化。

**SEOの現実(別軸だが収益と不可分)**: 新規ドメインは権威ゼロ→ビッグワードは数年勝てない。 7万定型ページは thin-content でindexされない危険→**価値の高いページから段階公開+内部リンク**。 勝ち筋=**ロングテール網羅(マイナー作/特定巻/版違い)** ×電書ASP収益。 関連=[[openbd_eol_amazon_required]]。

★2026-06-13 ユーザ予定: **火曜にアフィリエイト申請を各種実施**。カート(購入導線の形式)が可能か確認でき次第、詳細ページの購入ボタン(楽天追加/紙電子切替/Kindleブラウザ強制[[kindle_link_browser_not_app]])を詰める。楽天アフィIDは取得済(.env.local)。

★2026-07-12 ユーザ裁定: **購入ボタンUIはハイブリッド型**。紙(楽天・Amazon等)= 従来どおり**直ボタンのまま**。電子= 「**電子書籍で買う**」ボタンを1個追加し、押すと**電書ストアのリストが出る**(マンバ型の選択リストは電子だけに適用)。理由=電子はポイント経済圏(PayPay/dポイント等)でユーザのストア選好が割れる+複数ASP収益化に直結、紙は楽天起点で確立済み。電書ASP提携が揃い次第このリストに追加していく。試し読みリンク(BookLive、[[tameshiyomi seed=data/seeds/tameshiyomi-booklive-volumes.jsonl 12,175巻]])は別ボタン。

**Amazonアソシエイト開設(2026-07-29)**: ストアID=**mangal08-22**。`.env.local` の `NEXT_PUBLIC_AMAZON_ASSOCIATE_TAG` で配線済(未設定build=素リンクfallback)。紙は**ASIN=ISBN-10**なので `lib/amazon.ts isbn13ToIsbn10()` で全巻 /dp/ 直リンク化(979系のみ検索fallback)。★**180日以内に3件成果で本登録**=週次で本番に出たら早期に成果確認。Kindle別ASIN/書影は将来PA-API(合格後)。

**ValueCommerce/LinkSwitch(2026-08-05 ユーザ申込)**: バリューコマースにサイト登録(mangal ID:3777739・申込時審査中)し**BookLive!プログラム**へ申請。★**LinkSwitch** = layoutに貼った1タグ(vc_pid=892673489+aml.valuecommerce.com/vcdal.js)が、提携広告主ドメインへの**素リンクをクリック時に自動でアフィリエイトリンク変換**する仕組み。個別リンク加工不要=試し読みアンカー25,149件(BookLive title_id)の結線がそのまま収益化になる。タグは app/layout.tsx 末尾に実装済(2026-08-05・本番反映は週次/機能蒸留待ち)。PR表記は結線時に既存のPR方針に合わせること。

**VC実働確認(2026-08-06)**: サイト審査**通過**。★**Yahoo!ショッピングのカートボタンがLinkSwitch自動変換でアフィ化された**(実測=クリックでck.jp.ap.valuecommerce経由。従来の素リンクが自動収益化=LinkSwitch導入の初成果)。BookLive(プログラムID:2138296)=**提携待ち**→承認後に試し読みボタン(bviewer直開き)が自動変換される。承認後のTODO=①ディープリンク保持の実地確認(VCリダイレクト経由でビューアに着地するか) ②BookLive規約「adult配下のコンテンツ訴求禁止」→adult_us頁で試し読みボタンを出すかの点検。★管理画面で **Renta!/honto=即時提携** 可を確認=ストアシート宿題([[ebook-store-sheet-homework]])の即戦力候補(提携→素リンク並べるだけで収益化)。
