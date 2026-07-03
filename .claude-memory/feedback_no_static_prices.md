---
name: feedback-no-static-prices
description: 【厳守】価格の静的表示は絶対禁止(アフィ規約違反+誤データ)。動的取得のみ可
metadata:
  type: feedback
---

# 【厳守】値段は動的以外、絶対に表示しない (2026-07-03 ユーザ裁定)

**Why:** ①楽天アフィリエイト等の規約違反(キャッシュした古い価格の掲示は禁止・価格は常に最新であることが要求される) ②手元の価格データには間違いがある(特装版priceなど)。

**How to apply:**
- UI コンポーネントに price/円/¥ の静的レンダリングを書かない。variants.price 等のデータは**内部ソート用のみ**(豪華版判定など)に使い、画面に出さない。
- 新コーナー/新UI実装時は grep で price 表示が無いことを確認してから commit。
- 価格を出したい場合は楽天APIの動的取得(リアルタイム)のみ許可。将来の在庫/割引率表示([[version_tabs_stock_ebook]])も同じ制約。
- 2026-07-03 に VolumeCoverflow の variants 価格表示を撲滅済み。
