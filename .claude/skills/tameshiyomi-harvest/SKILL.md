---
name: tameshiyomi-harvest
description: 試し読み拾って=BookLiveの試し読みリンク(title_id)を魚で収集しseed化。判断はscript、AIは保留裁定のみ。Sonnet運転前提
---

# 試し読み拾って (= BookLive title_id 収集。2026-07-12 設計、同日★全巻展開を追加)

MANGALの「📖 試し読み」ボタン用に、BookLiveの作品ID(title_id)を集めて
`data/seeds/tameshiyomi-booklive.jsonl`(= シリーズ単位アンカー) と
`data/seeds/tameshiyomi-booklive-volumes.jsonl`(= ★巻単位の実データ、ボタンが読むのはこっち) に貯める。
**収集だけがこのskillの仕事**(ボタンUI/中継/via_cd注入は別作業=このskillでは触らない)。

## ★全巻展開の発見 (= 2026-07-12、ユーザ「ドラゴンボールなら42巻分取らないとダメよ？」で判明)

BookLiveのtitle_idは**シリーズ/版単位**。product頁の`vol_no`パスやbviewerのcid末尾3桁を
変えるだけで**同一title_idのまま全巻に到達できる**(TinyFish検索は不要・HEADチェックのみで済む)。
実証済: `title_id/582763`(チェンソーマン)で`vol_no/001`→1巻、`/002`→2巻。
`bviewer cid=582763_001/_002`、`185409_001/_025`、`185407_100` 全部HEAD200。
帰結: **アンカー(シリーズ→title_id)さえ集めれば、巻ごとの追加検索は不要**。
`cid=f"{title_id}_{vol:03d}"` を `max(total_volumes, max_edition_volumes)` 分HEAD検証するだけ
(= `_tameshiyomi-harvest.py --expand`)。TinyFish検索が要るのは**新規シリーズのtitle_id発見時だけ**。

## 収集するのは title_id(+巻の実在HEAD確認)だけ (= 2026-07-13 ユーザ裁定)

**購入ページURLは収集しない**。試し読みビューアも購入ページも `title_id`+`巻番号` から決定的に生成できる:
- 試し読み: `booklive.jp/bviewer/s/?cid=<title_id>_<巻3桁>`
- 購入: `booklive.jp/product/index/title_id/<title_id>/vol_no/<巻3桁>`
アフィリエイトパラメータもURL生成時(ボタンUI実装側)に付ける。収集の仕事を勝手に増やさない。

## NEVER (最重要・全部実害防止)

- **title_idを推測や連番で作らない**。scriptの検索+検証を通ったものだけがseedに入る
  (= ただし全巻展開の`vol_no`/cid末尾3桁を変える手法は実証済みの例外、これは検索でなくHEAD検証)
- **保留の採用は証拠付きのみ**: `--accept` する前に、候補title_idのBookLive頁の題・著者が
  MANGAL頁と一致することをsnippet/fetchで自分の目で確認。曖昧なら保留のまま残す(残すのは正常)
- **seedを手で編集しない**(追記はscript経由のみ。壊すと全ボタンが死ぬ)
- TinyFishは**無料枠のみ**(Fetch/Search)。Agent/Browserは絶対に使わない(クレジット消費)
- 1回の**検索(--limit)**実行は100まで。それ以上は分割(TinyFish 150req/分制限)。
  ★**--expand(HEAD検証のみ)にはこの制限は不要**(TinyFishを一切呼ばない・BookLive直HEAD。★2026-07-13からHEAD8並列=高速。楽天/NDL/TinyFishの逐次レート則は別ホストなので適用外)
- 検索失敗/エラーで止まったら**そのまま再実行**(再開可能設計)。リトライ連打しない

## 手順 (= この順で回す)

```
1. python scripts/_tameshiyomi-harvest.py --stats                   # 現在地(アンカー数/保留/全巻展開数)
2. python scripts/_tameshiyomi-harvest.py --limit 100               # 新規シリーズのtitle_id発見(検索。人気順)
3. python scripts/_tameshiyomi-harvest.py --expand --expand-limit N # ★アンカー済み全シリーズを全巻展開(検索不要・高速)
4. python scripts/_tameshiyomi-harvest.py --review                  # 保留一覧
5. (保留の裁定) 各行について:
   - 魚で `site:booklive.jp <題>` を検索し直し、候補title_idの頁題がMANGAL題と同一作品か確認
   - 確信が持てたものだけ: python scripts/_tameshiyomi-harvest.py --accept <slug>=<title_id>
   - 確信なし/BookLiveに無い作品 → 保留のまま放置(それが正しい)
   - accept後は忘れず3を再実行(新規acceptしたslugも全巻展開する)
6. commit+push:
   git add data/seeds/tameshiyomi-booklive.jsonl data/seeds/tameshiyomi-booklive-volumes.jsonl docs/production-diagnostics/tameshiyomi-holds.tsv
   git commit -m "試し読みharvest: +N件(保留M)/全巻展開+K巻" && git push
```

## scriptが保証していること(理解用・いじらない)

- 対象選定=本番索引の人気順(popularity)上位から未収集・未保留のみ
- 採用ゲート=①題の正規化**完全一致**(部分一致は保留) ②著者姓がsnippetに存在
  ③ビューアURL(`bviewer/s/?cid=<id>_001`)の**HEAD 200実在検証**。3つ揃わないと自動採用しない
- 出力=jsonl純粋追加(証拠snippet・検証日付き)・保留=tsv。再実行で重複しない
- `--expand`=アンカー済み(title_id確定)シリーズについて、`data/manga-list-index.json`の
  `total_volumes`/`max_edition_volumes`を上限にcid各巻をHEAD検証、200のみ
  `tameshiyomi-booklive-volumes.jsonl`に`{slug, volume, title_id, cid}`で純粋追加。
  既に検証済みの巻はskip(再開可能)。1シリーズ完了ごとに件数を表示

## 保留の典型と裁定のコツ

- **完全一致なし**: 表記ゆれ(ONE PIECE⇔ワンピース等)や巻数付き題。BookLive頁を魚でfetchして
  題+著者が一致すれば --accept。シリーズ違い(0巻/外伝)を本編と間違えないこと
- **複数候補**: 無印と新装版/カラー版が並ぶ。**無印(通常版)のtitle_id**を選ぶ
- **候補0**: BookLiveに無い(古書・成年など)。放置

## 報告形式

`アンカー合計X件(+今回N) / 保留Y件(うち今回裁定でZ件採用) / 全巻展開=W巻(V件シリーズ完了)`

## 関連

- 魚の使い方=skill tinyfish / ボタンUI・中継(/go)実装=別途(Claude本体の作業)
- 将来: シーモアはビューアURL規則が不透明なため、ASP提携後に別途設計
