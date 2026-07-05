---
name: kobo-covers
description: Koboして/書影補完して=楽天Kobo電子版の書影で紙の欠け巻を補完。装丁目視ゲート必須(電子が別装丁なら弾く)。resumable
---

# Kobo書影補完 (= トリガー「Koboして」「書影補完して」「Kobo続けて」)

書影欠けの紙巻を、楽天Kobo(電子版)APIの書影で埋める。**装丁が紙と一致する時だけ採用**する目視ゲートが肝。
釣りキチ三平/サザエさん/ゴルゴ13等で実証(2026-07-05)。母集団=軽症組(表紙あり×ISBN欠け)約2,450作。

## 大原則
- ★**電子版の装丁が紙と違う作品は弾く**(= Koboは「デジタル大全」「完全版」等の別装丁で再出版されることがある。サイボーグ009=講談社デジタル大全の無地表紙・花のあすか組=新装アート で REJECT した実例)。誤書影は誤ISBNより悪い([[cover_source_affiliate_only]] [[feedback_accuracy_is_the_goal]])。
- ★**題+巻番号の完全一致のみ**候補化(スピンオフ/同題別作を吸わない。BiNGO!=葉芝真己版とコロコロ松村版の混在を発見した型)。
- 楽天API=**必ず`scripts/_lookup.py`相当のヘッダ/レート(1.2-1.3s・Referer/Origin)**。Koboエンドポイント=`openapi.rakuten.co.jp/services/api/Kobo/EbookSearch/20170426`([[external_data_access]]参照)。

## 手順 (= バッチループ)
機構 = `scripts/_kobo-covers.py`(git追跡)。covers seed = `data/seeds/covers.jsonl.gz`(isbn13→cover_url純粋追加、promoteが書込直前に充填)。

1. **prepare**(欠け巻数上位N作をKobo照合+比較ペアDL):
```
python scripts/_kobo-covers.py --prepare 30
```
   - preview(.preview-data=軽症組)から欠けISBN巻降順でN作。Kobo全ページ照合し題+巻一致の書影を収集。
   - 各作 `.cache/kobocheck/<slug>-kobo-vN.jpg`(Kobo候補) + `<slug>-paper.jpg`(既存紙表紙) をDL。一致なしはdone記録しskip。
2. **目視判定**(★私がやる=画像Read):
   - 各作の kobo画像 と paper画像 を Read で並べ、**同一装丁シリーズか**判定。紙表紙が同edition内に無ければ `--anypaper` で別版から代表を落として比較。
   - ACCEPT=装丁一致 / REJECT=別装丁(done記録して次へ)。
3. **apply**(合格slugをcovers seedへ):
```
python scripts/_kobo-covers.py --apply slug1,slug2,...
```
4. **反映**: touchedを `_reflect-targeted.py --only ... --push`(skill reflect-targeted)。
5. **検証**: 反映後 `残欠け` が減ったか数字確認。REJECT/発見(同題混在等)は docs/production-diagnostics のworklistへ。

## ヒット率の実測
軽症組でKoboヒット~35%、さらに装丁目視で絞られ**実補完は推定800-900作**。電子未配信(ドカベン=水島新司拒否/学習まんが/貸本)は埋まらない=無理しない。1回10-20作。

## 罠
- 楽天cacheに題があっても書影が`noimage`のことがある→除外必須([[rakuten_out_of_stock_flag]] [[rakuten_cover_data_asset]])。
- ISBN無し巻(プレISBN古典)はKoboでも埋まらない=母集団外(ISBN有欠けのみ対象)。
- 藤子Ⓐ系は頁側の装丁次第でACCEPT/REJECTが割れる=必ず個別目視(まんが道=REJECT/魔太郎がくる=ACCEPT)。
