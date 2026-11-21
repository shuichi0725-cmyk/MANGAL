---
name: openbd-eol-amazon-required
description: OpenBD サービス終了予定 + 書影は Amazon PA-API のみ合法、 最初から Amazon API で 書影出す方針
metadata: 
  node_type: memory
  type: reference
  originSessionId: 6146d01a-d071-41e5-9ffa-4568e252bbb1
  modified: 2026-10-20T15:15:05.905Z
---

# OpenBD = サービス終了予定 + 書影は Amazon API 必須

## ★2026-10-06 更新: PA-API は終了 → **Creators API**
- PA-API v5 は **2026-05-15 にエンドポイント完全停止**(Offers v1 は 2026-01-31 終了)。後継 = **Amazon Creators API**(OAuth 2.0 Bearer)。
- 利用資格 = アソシエイト参加 + **直近30日で対象売上10件以上**(Web上の移行解説複数で確認。旧PA-APIの「180日で3件」より重い)。
- MANGAL = 2026-07-29 アソシエイト開設(mangal08-22)。まず本登録(180日で3件)→ API は月10件の売上が要る = **流入が先**。
- 以下の本文の「PA-API」は Creators API と読み替える。
- ★**2026-10-21 鍵を発行済み**(アプリ名 Mangal・Version 3.3 = 極東/日本)。鍵の CSV はユーザが持つ(会話に添付 = `~/.claude/uploads/d6d1e4c1-…/…-Mangal-credentials.csv`。★repo は公開なので git・記憶に鍵を書かない。本運用は GitHub Secrets)。
  - 1回だけ試した結果: トークン取得 = **200(鍵は有効)** / getItems = **403 `AssociateNotEligible`**「Your account does not currently meet the eligibility requirements.」= 売上条件が未達。条件を満たせば同じ鍵でそのまま通るはず。
  - ★2026-10-23 再試験(ユーザ「申請から使えるまで時間がかかるらしい・1回試して」): トークン 200 / getItems **403 AssociateNotEligible のまま**(10/21と同じ)= 待ち時間ではなく売上条件。CSV の列は `Credential Id`(=client_id)と `Secret`。
  - ★★**2026-11-21 再試験: getItems = 200 で通った**(ONE PIECE 1 = ASIN 4088725093 → 題・書影 500px・tag=mangal08-22 付き detailPageURL が返った)= **売上条件を満たして使えるようになった**。トークン取得 `https://api.amazon.co.jp/auth/o2/token`(client_credentials・scope `creatorsapi::default`)→ `POST https://creatorsapi.amazon/catalog/v1/getItems`(Bearer・`x-marketplace: www.amazon.co.jp`・itemIdType ASIN・ASIN=ISBN-10)。
  - ★鍵の CSV は uploads から消えていた(10/21 の会話記録にだけ残っていた)。資格は直近30日の売上で外れることがある=使う前に1回試す。
  - 通った呼び方: トークン = POST `https://api.amazon.co.jp/auth/o2/token`・JSON `{grant_type: client_credentials, client_id, client_secret, scope: "creatorsapi::default"}` → getItems = POST `https://creatorsapi.amazon/catalog/v1/getItems`・`Authorization: Bearer <token>`・`x-marketplace: www.amazon.co.jp`・JSON `{itemIds:[ISBN-10], itemIdType:"ASIN", marketplace:"www.amazon.co.jp", partnerTag:"mangal08-22", resources:[images.primary.large, itemInfo.title, parentASIN]}`。

## OpenBD 状況

- **OpenBD は サービス終了予定** (= 時期不明、 既に announce 済)
- 既存 `scripts/fetch-openbd-bulk.ts` は **将来 廃止対象**

## 書影 (= 表紙画像) の 法的問題

- **書影は 合法的に使うには Amazon 等の 商用サービス 以外 事実上使えなくなる**
- OpenBD 含む 非商用 source の 書影 = 法的に NG 化
- → MANGAL の 書影 = **Amazon PA-API のみ 合法 source**

## MANGAL 方針

- **最初から Amazon PA-API で 書影出す予定**
- Amazon 審査 通過後 PA-API 利用
- ★ 過去 ユーザと 議論済 = 確定方針

## 代替 source

| 用途 | source | 状態 |
|---|---|---|
| 巻別 ISBN / 発売日 | NDL Search (= `scripts/fetch-ndl.ts`) | ✓ 既存、 継続利用 |
| 書影 | **Amazon PA-API** | 審査必要、 通過後利用 |
| 価格 / メタ補完 | Amazon PA-API + 楽天 Books API | 同 |

## 影響

- OpenBD = 議論時 出てきても 「廃止対象」 と扱う
- 書影 議論 = 全件 Amazon PA-API 前提
- L1 巻欠落 補完 = NDL Search で 巻別書誌、 書影は Amazon

## ★ 訂正 = OpenBD は終了まで 2 用途で利用可

書影 ✗ だが **書誌情報** (= title/著者/ISBN/発売日/分類/内容紹介) は **法的 OK**:

1. **巻補完** = ISBN ベースで 巻別書誌 取得 (= MADB 入力漏れ救済)
2. **成年コミック判定** = OpenBD `onix.DescriptiveDetail.Audience` / `SubjectScheme` で MADB `contentRating` 漏れ補完

サービス終了まで は この 2 用途で使う、 終了後 は:
- 巻補完 → NDL Search / 楽天 Books API
- 成年判定 → Amazon PA-API `is_adult_browse_node`
- 書影 → Amazon PA-API (= 全期間 通じて)

**How to apply:**
- 議論で OpenBD が 出たら 「終了予定、 書影は Amazon API 必須」 と 即補足
- L1 補完 / 書影 議論 では NDL + Amazon 前提
- 関連: [[project-architecture-seeds]]

## ★2026-11-21 Creators API 調べ(試験のみ・本番未適用)
- 鍵は `.env`(AMAZON_CREATORS_CLIENT_ID / _SECRET / _VERSION=3.3)。試験道具は scratchpad の ca.py(リポジトリ未収録)。
- **紙**: getItems(ASIN=ISBN-10・1回10件)。Amazon に紙頁が無い巻は `errors[] InvalidParameterValue "ItemIds … is invalid"` = 犬の404巻を**事前に判定できる**(こんにちはマイコン1 4091041019 で確認)。externalIds に eans/isbns。
- **Kindle**: searchItems(searchIndex KindleStore・title/author 引数可・1頁10件・itemPage)。Kindle版の publicationDate = **紙の発売日**(ONE PIECE 1=1997-12-24・マイコン1=1982-10-01)= 題+巻+日付で照合できる。ONE PIECE はモノクロ版/カラー版が両方出る=版の選別が要る。**ASINは連番でない**(1=B009GZK2YE・2=B009GZK31Q・102=B09TKX1NX9)=1巻ずつ保存が要る。紙↔Kindleの関連を返す項目は無い。
- **書影**: 抜き取り75件(書影なし25・Kobo借り25・楽天紙25)全部 Amazon 書影あり(500px高・代わり画像でない・目視確認)。Kobo借りの巻で Amazon が紙の元装丁=正しい例(あさってDANCE)。★規約: Images は**キャッシュ1日**(best practices)/Associates方針は画像の保存禁止・画像URLは24時間まで = 週次静的ビルドに焼くのは規約上危ない(未解決)。
- **回数**: 初期 1TPS・8,640回/日、getItems 10件=1回。資格は直近30日に売上0件が続くと失効(売上発送後2日で復帰)・超過は429。
- 現行リンクは画面側で ISBN→ISBN-10→ `https://www.amazon.co.jp/dp/<ASIN>?tag=mangal08-22` を組み立て(HTMLにURLは入っていない)。全巻 277,271(書影: 楽天紙 228,001 / なし 35,098 / Kobo 15,527)。
