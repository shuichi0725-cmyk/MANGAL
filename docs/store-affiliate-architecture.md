# 作品→読めるストア 連動・アフィリエイト収益設計

作成 2026-06-04。 ★収益の心臓部＝「各作品ページに『この作品が読めるストア一覧（初回クーポン付き）』を出す」連動の設計。
比較ハブを単独で作らず **7万作品DBに紐付ける** ことが既存アフィに対する唯一の moat（[[openbd_eol_amazon_required]]）。

---

## 0. 現状（2026-06-04 実測）

| 項目 | 状態 |
|---|---|
| volumes 総数 | 382,704 |
| ISBN-13 充足 | 341,621（89%）★物理書誌の強い鍵 |
| cover_url | 0（未取得）|
| asin / amazon_metadata | テーブル有・**0件**（Amazon未投入）|
| 楽天 fetch script | ★**既存**（`fetch-rakuten.ts` / `fetch-rakuten-bulk.ts`）= BooksBook/Search で title+author 検索→ISBN/largeImageUrl(書影)/salesDate 取得 |

★**結論**: 書影もストアリンクも未着手だが、**楽天APIの土台は既にある**。ここから始めるのが最短・最安・無資格。

---

## 1. 設計原則

1. **層化（Tier）**: 安価・確実な検索リンクから、APIマッチの精密リンクへ段階的に。全作品を一度に精密マッチしようとしない。
2. **誤マッチ回避（慎重原則）**: 物理は ISBN で exact。 e-book は文言検索が**曖昧**→ **product直リンクは誤マッチ危険**→ 既定は「ストア内検索結果へのdeep-link」。確実に存在し、誤リンクしない。
3. **無資格・無料を先に**: 楽天API（売上gate無）→ Amazon PA-API（★3件/180日の売上gate有 = 後回し）。
4. **収益はper冊でなくASP特典**: Amazonの数% / 18円より、電書ストアの**初回登録・初回購入（数百円/件）**が本命。
5. **法務必須**: ステマ規制（2023-10〜・景表法）で **広告/PR表記が義務**。クーポン条件・上限は正確に。

---

## 2. ストア接続方式の分類

| ストア | 接続 | 鍵 | deep-link | 書影 | 特典型 | 優先 |
|---|---|---|---|---|---|---|
| **楽天ブックス/Kobo** | 楽天API + 楽天アフィリ | ISBN/文言 | ◎ | ◎(API) | 購入 | ★**1（無料・gate無）** |
| **DMMブックス** | DMM Affiliate API | 文言 | ◎ | ◎(API) | 初回90%OFF=高転換 | ★2 |
| **ebookjapan** | ValueCommerce MyLink | 文言 | 検索◎ | △ | 初回70%×6回 | ★2 |
| **コミックシーモア** | もしも/A8 | 文言 | 検索 | △ | 初回70%/月額 | 3 |
| **BookLive / まんが王国** | A8 | 文言 | 検索/固定 | △ | 初回/ポイント | 3 |
| **BOOK☆WALKER / honto** | affiliate | 文言 | 検索 | △ | クーポン | 3 |
| **Amazon(Kindle/紙)** | PA-API | ISBN→ASIN | ◎ | ◎ | 数%(低) | ★**売上gate後** |

※ A8は merchant により deep-link 不可（固定リンクのみ）= その場合「ストアtop+タグ」止まり。 deep-link 可否は merchant 単位で要確認。
※ ValueCommerce MyLink / 楽天 / Amazon は**任意URLのdeep-link可**（検索リンクが作れる）= Tier 0 が効く。

---

## 3. データモデル

### 3-1. ストアレジストリ `data/seeds/stores.yml`（手動 curate）
各ストア: `key / name / asp / affiliate_id_env / deep_link(bool) / search_url_template / api(none|rakuten|dmm|amazon) / bounty(registration|purchase) / coupon_note / priority / enabled`。

### 3-2. Tier 1 キャッシュ `store_products`（API由来・定期更新）
鍵 = `isbn13`（物理）or `(work_key, store, volume)`（e-book）。 値 = `{store, url(affiliate-wrapped), cover_url, price, in_stock, last_checked}`。
- 楽天/Amazon = ISBN 鍵で exact。 DMM = 文言マッチ後の確定IDを保存。
- 再生成可能（生データ）なので **git 非追跡**（.cache）。 書影だけは本番 promote で manga.v2 へ焼く（[[synopsis_ja_seed]] と同じ「高価な取得物のみ永続化」原則）。

### 3-3. Tier 0 検索リンク（保存しない・render時生成）
`stores.yml` の `search_url_template` に作品 title(+author) を差し込み、ASP の wrap を被せて render 時に生成。 → **全7万作品に即・ストア一覧が出る**（per-product マッチ不要）。

---

## 4. マッチング戦略（誤マッチ＝信頼喪失なので慎重に）

| 種別 | 鍵 | 方式 | 確度 |
|---|---|---|---|
| 物理（楽天ブックス/Amazon紙）| ISBN-13(→10) | API exact | ◎ |
| e-book（楽天Kobo/Amazon Kindle）| ISBN or 文言 | API。 ISBN無/不一致は文言→**人間 or 高trafficのみ精密化** | ○〜△ |
| e-book（DMM/シーモア/ebj…）| 文言 | **検索結果へdeep-link**（product直リンクしない）| 安全（誤リンク無）|

★原則: **「この巻のproductを当てに行く」より「この作品をストア内で探す導線」を既定**にすると、誤マッチ0で全作品をカバーできる。 product 精密化は **書影が要る楽天/Amazon** と **高traffic作のみ**に投資。

---

## 5. 段階ロードマップ

### Phase 1（今すぐ・無料・無資格）★最優先
- **楽天API bulk** で全ISBN(34万)の **書影 + 楽天アフィリリンク** 取得 → ★**書影問題と楽天送客を同時に解決**。 既存 `fetch-rakuten-bulk.ts` を ISBN 鍵で全巻に適用（rate 1req/sec → batch + cache、 incremental）。
- **e-book各ストアへの検索deep-link**（stores.yml テンプレ生成）→ availability funnel 即稼働。
- **ハブページ**（全ストア比較・どれに登録すべき）+ 各作品ページからの導線。
- 広告/PR表記の実装。
→ これで「書影付き・全ストア送客・初回クーポン訴求」が **API資格ゼロで成立**。

### Phase 2（売上が立ったら）
- **Amazon PA-API**（紙+Kindle、ISBN→ASIN）追加 = 書影の冗長化 + Amazon送客。 ★3件/180日の売上は Phase 1 の楽天/電書送客で達成見込み。

### Phase 3（高転換ストア）
- **DMM Affiliate API**（初回90%OFF=転換高）で作品マッチ→product+書影。

### Phase 4（精密化）
- 高trafficページのe-book multi-store **価格比較**（product直リンク検証・キャッシュ）。

---

## 6. 導線設計（スパムにしない）

- **巻カード**: 楽天書影 + 「この巻を読む（楽天/Amazon…）」。 cover_url 入れば自動で実画像化（既存 VolumeTile 設計）。
- **作品ページ下部**: 「**この作品が読めるストア**（初回クーポン付き一覧）」= 検索deep-link群 → ハブへ。
- リンクは**1〜2箇所を綺麗に**（貼りすぎは転換低下）。
- **ハブ**: DB連動の総元締め。 「各ストアの初回特典で別の巻に使うと全部お得」を**正直に**訴求（煽りでなく事実＝信頼＝持続）。

---

## 7. 運用・リスク

- **楽天API rate**: 1req/sec。 34万ISBN ≈ 約4日分のAPI時間 → batch + 永続cache + 月次incremental（蒸留に組込）。
- **ASP分散**: プログラム閉鎖・条件変更に備え単一依存を避ける。
- **2026-02 楽天API仕様変更**: applicationId が UUID 形式必須（`fetch-rakuten.ts` に注記済）。 affiliateId 設定で affiliateUrl 取得。
- **法務**: 広告/PR表記、 クーポン条件・上限の正確表示、 景表法（誇大NG）。

---

## ★まとめ（次の一手）

**Phase 1 = 楽天API bulk（書影＋リンク）＋ 検索deep-link funnel ＋ ハブページ** が、**無資格・無料で収益funnelを立ち上げる最短路**。 書影問題も同時に解ける。 Amazonは売上gateがあるので Phase 2。 収益の本命は電書ストアの初回特典（ASP）で、それを**7万作品DBに連動**させるのが既存アフィに勝てる唯一の形。
