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
