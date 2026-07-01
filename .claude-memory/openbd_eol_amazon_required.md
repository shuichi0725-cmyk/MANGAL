---
name: openbd-eol-amazon-required
description: OpenBD サービス終了予定 + 書影は Amazon PA-API のみ合法、 最初から Amazon API で 書影出す方針
metadata: 
  node_type: memory
  type: reference
  originSessionId: 6146d01a-d071-41e5-9ffa-4568e252bbb1
---

# OpenBD = サービス終了予定 + 書影は Amazon API 必須

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
