---
name: cover_harvest_plan
description: 【計画済】書影harvest=楽天紙→Kobo電子→ISBN無の3段。docs/cover-harvest-plan.md。ISBNキー安全/題キーは誤書影リスク最悪で厳格orskip
metadata: 
  node_type: memory
  type: project
  originSessionId: eead35c9-02b6-4f7c-9201-3923c98dedb6
---

書影未取得巻の補完計画（2026-06-21策定、`docs/cover-harvest-plan.md`が本体）。

## 規模（サンプル3000作/11,052巻実測）
- 書影あり80% / **ISBN有・書影無16%(≈39千巻=収穫対象)** / **ISBN無2%(≈7千巻=要注意)**。
- ★OFFSET/GAP harvestで追加した巻はcover_url=null(この16%に含む)。

## ★大原則（ユーザ指示）
- **ISBNキーの書影=安全**(ISBNが本を一意特定)。**題キー(ISBN無)=誤書影リスク最悪→厳格一致orskip**(無書影＞誤書影)。

## ★まとめて1周回（ユーザ指示「選択肢3」2026-06-21）
楽天起点を同じ周回に束ねる: ①書影 ②説明文itemCaption(同API応答で同時保存) ③**版バリアント追加1,119作**(`data/seeds/edition-variant-candidates.tsv`=愛蔵版261/完全版257/新装版331/復刻99/ワイド162/カラー12。書影/アフィ/発売日もキャッシュ済)。
- ★版バリアント表示=**うる星やつら方式で完全に同じでOK**(ユーザ確認)= 同巻数→刷タブ`versions[]`/別判型→別editionタブ→`_regroup-versions.py`→promote配線で恒久化。
- ★**特装版は別物**(混同禁止): 巻単位 `volume.variants[]`=ベルセルク/案B(通常版主+特装を巻詳細に併記。表紙/ISBN/価格別)。`special-edition-fix.yml`/`_special_edition_fix_apply.py`で別パイプライン既存。[[special_edition_fix_state]]

## 3段（優先順）
1. **Phase1 楽天紙CDN**(ISBN有・書影無): 既存`_cover_gap_fill.py`流用=ISBN→`thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/{isbn[-4:]}/{isbn}.jpg`(+_1_2/_1_4)＋API largeImageUrl。CDN直叩きはAPI不要・高速。
2. **Phase2 Kobo電子**(楽天紙ミス分): ★取得法要研究(楽天ブックスAPI電子ジャンル/Kobo CDN kbimg.rakuten-static.com/Ichiba)。紙ISBN==電子ISBNならISBNキー安全、別番号なら題完全一致+著者+巻で照合。Kobo=楽天圏でアフィOK。
3. **Phase3 ISBN無**(≈7千): 原則貼らない。貼るなら題+著者+巻の3条件全一致1件のみ。flag出力。

## ★書影と説明文を同じパスで取る (= 2026-06-21 ユーザ指示、時間ある時に実行)
- ★**楽天API応答1件に largeImageUrl(書影) も itemCaption(説明文) も両方入る**。書影だけ取って説明を保存しないと取りこぼす(うる星新装版34巻=各話タイトル付き説明を取り逃していた実例)。
- ★**書影harvestを回す時に itemCaption も同時にキャッシュ保存**する(= rakuten-isbn.jsonl 相当に full item で追記)。一度のAPIで両方=取りこぼし0・効率的。
- 対象同じ: OFFSET/GAPで追加した1,613巻 + ISBN有書影無39千巻は説明文もキャッシュ未取得。書影パスで一緒に回収。
- 説明文は楽天著作物=表示はそのまま不可→AI要約([[synopsis_ja_seed]]同様)。ただし**▼各話タイトル列挙は「収録話」として事実列挙で出せる可能性**(要確認)。

## 実装メモ
- harvest機構=`_offset_harvest.py`(Referer+Origin必須/1s/全角NFKC/著者照合/dedup/resume)流用→`_cover_harvest.py`(仮)。★API段では largeImageUrl と itemCaption を両方保存。
- 全て可逆+cover-changelog+純粋追加。GAP batch完了後に着手予定([[rakuten_cover_data_asset]][[cover_source_affiliate_only]])。

## ★追記(2026-06-25): 楽天ブックスAPI ≠ 楽天市場(書影取得源の3段)
- **BooksBook API(現用)=楽天直営書籍のみ**。g-walk等の小規模社/市場出品は載らない(例: きみの心にさわりたい=楽天市場には有るがBooksBookは0件)。ユーザ確認済。
- **IchibaItem API(楽天市場)=マーケットプレイス含む→ブックス未収録を拾える**。但し★現アプリ(RAKUTEN_APP_ID)は400「valid applicationId」=市場API用の別アプリ登録/権限が要る(未設定)。
- ★書影取得=3段: ①BooksBook(直営) ②IchibaItem(市場・要権限) ③Amazon PA-API(最終)。distill-enrichで楽天0件の実在作はAmazon or 市場APIへ。
