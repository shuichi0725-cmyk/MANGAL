# 書影harvest計画 (= 楽天紙→Kobo電子→ISBN無の3段、2026-06-21)

## 背景・現状
- 現行の書影source = **楽天のみ**（`_cover_gap_fill.py`: ISBN→楽天CDN `thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/{isbn[-4:]}/{isbn}.jpg`(+_1_2/_1_4) ＋ 楽天API largeImageUrl）。NDL画像は不可（[[cover_source_affiliate_only]]）。Koboは未実装。
- サンプル3000作/11,052巻実測:
  - 書影あり **80%**
  - **ISBN有・書影無 16%（全DB推定 ≈39千巻）** ← 収穫対象本体
  - **ISBN無 2%（≈7千巻）** ← 全て書影無・要注意
- ★OFFSET/GAP harvestで新規追加した巻は cover_url=null（この16%に含まれる）。

## ★大原則（ユーザ指示＝画像間違いが最悪）
- **ISBNキーの書影取得 = 安全**（ISBNが本を一意特定→その画像は必ず正しい）。
- **題キーの書影取得（ISBN無）= 危険**（別作の表紙を貼る事故が最悪）。→ 厳格一致 or skip（無書影＞誤書影）。

## 優先順位（ユーザ指示）
1. **紙の本の書影をまず探す**（未取得のISBN有巻）= 楽天紙でリトライ。
2. **無ければ電子版**（Kobo電子書籍の書影）。多くは紙と同一画像。
3. **ISBN無は要注意**（画像無いかもだが、貼るなら厳格検証）。

---

## Phase 1: 楽天 紙書影リトライ（ISBN有・書影無 ≈39千巻）
- **機構**: 既存 `_cover_gap_fill.py` を全DBに適用（ISBN→CDN直叩き＋API largeImageurl、noimage除外）。
- **安全**: ISBNキー=誤画像リスク無し。
- **手順**: ① CDN試行(.jpg/_1_2/_1_4) ② 外れたらAPI(isbn照会, outOfStockFlag=1) ③ noimage/サイズ<2KBは不採用。
- **記録**: cover-changelog.jsonl（slug/number/isbn/cover_url、純粋追加）。
- **出力**: Phase1後に「楽天にも無い」残=Phase2対象を確定。

## Phase 2: Kobo 電子書影（楽天紙ミスの巻）
- **要研究（バッチ後にテスト）**: Koboの書影取得法を確定する。候補:
  - (a) 楽天ブックスAPIで**電子書籍ジャンル**(booksGenreId 001=本の電子 or 別ジャンル)を検索→largeImageUrl。
  - (b) 楽天Kobo CDN（`kbimg.rakuten-static.com`等）をKobo商品IDで叩く（ISBN→Kobo-IDのmapping要）。
  - (c) 楽天市場(Ichiba)APIで電子書籍を検索。
- **照合方式**:
  - ★**紙ISBN==電子ISBNが取れるなら ISBNキー=安全**（最優先）。
  - ISBNが紙/電子で別番号の場合 → **題完全一致＋著者＋巻番号** で照合（OFFSET harvestと同じ厳格matcher流用）。一致しなければ skip。
- **法務**: Kobo=楽天Kobo＝楽天アフィ圏内なのでアフィ source要件OK。
- **注記**: 電子の書影は紙と微差（帯無し等）の場合あり＝表示上は許容。

## Phase 3: ISBN無（≈7千巻）= 最注意・最後
- **既定 = 原則貼らない**（誤書影リスク＞無書影）。
- 貼る場合のみ: 楽天/Kobo題検索で **題完全一致＋著者一致＋巻番号一致** の3条件全て満たす1件のみ採用。複数候補/曖昧は skip。
- **flag出力**（手動レビュー用tsv）。自動採用は保守的に。

---

## 実装メモ
- harvest機構は `_offset_harvest.py`（Referer+Origin必須・1s/件・全角題NFKC・著者照合・dedup・resume）を流用。
- cover専用に `_cover_harvest.py`（仮）: ①ISBN-CDN ②楽天API ③Kobo の順で試行、cover_url純粋追加。
- 全て可逆（.cache/cover-bak）＋ cover-changelog ＋ typecheck。
- バッチは ~39千巻 = 楽天API 1s/件で長時間 → CDN直叩き(API不要・並列可)を先に回し、CDNミス分だけAPI/Koboへ落とすのが効率的。

## 実行順（GAP batch完了後）
1. Phase1 CDN直叩きバッチ（API不要・高速）→ どれだけ埋まるか測定。
2. 残をPhase1 API → さらに残（楽天無し）を確定。
3. **Kobo取得法を3-5件でテスト**（ISBNキー可否を判定）→ 方式確定。
4. Phase2 Koboバッチ（ISBNキー優先・題厳格fallback）。
5. Phase3 ISBN無=flag出力のみ（自動採用は厳格1件限定）。
6. プレビュー索引再生成＋総括。
