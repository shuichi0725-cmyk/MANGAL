---
name: tameshiyomi-harvest
description: 試し読み拾って=BookLiveの試し読みリンク(title_id)を魚で収集しseed化。判断はscript、AIは保留裁定のみ。Sonnet運転前提
---

# 試し読み拾って (= BookLive title_id 収集。2026-07-12 設計)

MANGALの「📖 試し読み」ボタン用に、BookLiveの作品ID(title_id)を集めて
`data/seeds/tameshiyomi-booklive.jsonl` に貯める。**収集だけがこのskillの仕事**
(ボタンUI/中継/via_cd注入は別作業=このskillでは触らない)。

## NEVER (最重要・全部実害防止)

- **title_idを推測や連番で作らない**。scriptの検索+検証を通ったものだけがseedに入る
- **保留の採用は証拠付きのみ**: `--accept` する前に、候補title_idのBookLive頁の題・著者が
  MANGAL頁と一致することをsnippet/fetchで自分の目で確認。曖昧なら保留のまま残す(残すのは正常)
- **seedを手で編集しない**(追記はscript経由のみ。壊すと全ボタンが死ぬ)
- TinyFishは**無料枠のみ**(Fetch/Search)。Agent/Browserは絶対に使わない(クレジット消費)
- 1回の実行は **--limit 100 まで**。それ以上は分割(TinyFish 150req/分制限+失敗時の被害限定)
- 検索失敗/エラーで止まったら**そのまま再実行**(再開可能設計)。リトライ連打しない

## 手順 (= この順で回す)

```
1. python scripts/_tameshiyomi-harvest.py --stats          # 現在地
2. python scripts/_tameshiyomi-harvest.py --limit 100      # 収集(人気順・未収集から自動選定)
3. python scripts/_tameshiyomi-harvest.py --review         # 保留一覧
4. (保留の裁定) 各行について:
   - 魚で `site:booklive.jp <題>` を検索し直し、候補title_idの頁題がMANGAL題と同一作品か確認
   - 確信が持てたものだけ: python scripts/_tameshiyomi-harvest.py --accept <slug>=<title_id>
   - 確信なし/BookLiveに無い作品 → 保留のまま放置(それが正しい)
5. commit+push:
   git add data/seeds/tameshiyomi-booklive.jsonl docs/production-diagnostics/tameshiyomi-holds.tsv
   git commit -m "試し読みharvest: +N件(保留M)" && git push
```

## scriptが保証していること(理解用・いじらない)

- 対象選定=本番索引の人気順(popularity)上位から未収集・未保留のみ
- 採用ゲート=①題の正規化**完全一致**(部分一致は保留) ②著者姓がsnippetに存在
  ③ビューアURL(`bviewer/s/?cid=<id>_001`)の**HEAD 200実在検証**。3つ揃わないと自動採用しない
- 出力=jsonl純粋追加(証拠snippet・検証日付き)・保留=tsv。再実行で重複しない

## 保留の典型と裁定のコツ

- **完全一致なし**: 表記ゆれ(ONE PIECE⇔ワンピース等)や巻数付き題。BookLive頁を魚でfetchして
  題+著者が一致すれば --accept。シリーズ違い(0巻/外伝)を本編と間違えないこと
- **複数候補**: 無印と新装版/カラー版が並ぶ。**無印(通常版)のtitle_id**を選ぶ
- **候補0**: BookLiveに無い(古書・成年など)。放置

## 報告形式

`収集済み合計X件(+今回N) / 保留Y件(うち今回裁定でZ件採用) / 進捗=人気上位何位まで到達`

## 関連

- 魚の使い方=skill tinyfish / ボタンUI・中継(/go)実装=別途(Claude本体の作業)
- 将来: シーモアはビューアURL規則が不透明なため、ASP提携後に別途設計
