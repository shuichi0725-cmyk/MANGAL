---
name: gyara_type_regression_cleanup_state
description: ギャラ型(巻×発売日の大逆行)是正。worksheet 80件中74件完了・残6件は理由つき保留。トリガー「ギャラ型続けて」
metadata: 
  node_type: memory
  type: project
  originSessionId: 11f90ab9-a3a1-4cd0-b8a8-b5174b421920
  modified: 2026-08-17T02:13:27.844Z
---

**トリガー「ギャラ型続けて」**。worksheet(30年+の80頁)は **74件是正済 / 残6件**。次は残6件か、30年未満の層へ広げるかをユーザに確認する。

## 状態(2026-08-17 一巡完了)
- 検出器 = `scripts/_audit-vol-date-regression.py`(月次サニティ登録済)。flag **489版**(初回573)
- worksheet = `docs/production-diagnostics/vol-date-regression-worksheet.tsv`
  - B_REPRINT_MIX 49件 → 残5 / A_SPLIT_WORK? 28件 → 残1 / C_INTERNAL_MIX 3件 → 残0
  - ★**A_SPLIT_WORK?はほぼ誤分類**だった。複数sidに見えたのはクラスタリングの副作用(著者欄に「白泉社」「花とゆめコミックス編集部」等が混入して副次sidができる)で、実体は復刻混在(B型)。真に別作品が同居していたのは銭形平次だけ
- 是正内容は `data/seeds/edition-canonical/*.yml` の source: と `edition-fix-changelog.jsonl` に全部書いてある

### 残6件(理由つき保留)
- **鉄腕アトム** = 最難関。9 sid / 33 edition / volume行267。うち ed42075 が「レーベル名なし42冊」でISBN接頭辞で4 runに割れる。専用の腰を据えた回が要る
- **SWAN** = 続編『ドイツ編』『モスクワ編』(平凡社)が同一頁に混在=A型判断が要る。初出はマーガレット・コミックス全21巻(集英社1977-81)
- **クイーンエメラルダス** = 初出の講談社コミックス全4巻がMADBに無く4run混線
- **流れ星五十三次** = サンコミックスのv5だけ1968-07-25でv1-4の1973から5年逆行。NDLに当該runが無く裁定不能
- **ピカドンくん / タンク・タンクロー** = MADBの巻が全てv0=巻番号不明

### 別頁として登録すべき候補(canonical化で各頁から外れた別作品)
- 女帝エカテリーナ ← 榎本由美『世界美女秘話シリーズ』(9784792604035 2007-09)
- サハラ ← 高口里純 Emerald comics(2014-02)
- 春が来た ← 新田真子 ワールドコミックススペシャル(9784765903783 1993-10)
- 沙漠の魔王 ← 林よしお『砂漠の魔王』(新生閣漫画絵本)
- 銭形平次捕物控 = 同一原作の3社別コミカライズが同居(石森章太郎プロ/大石賢一/さとう勝己)。頁分離が本来の解

## レシピ
1. worksheetから候補 → `python .cache/gyara/dumpvol.py <sid...>` で種2の巻明細dump
2. **NDL SRU**で裏取り= `python scripts/_lookup.py --title X --creator Y --live`(1.2秒/req。`--creator`が無いとNDLを叩かず楽天になる。タイムアウトしたら1回リトライ)
3. **edition-canonical/*.yml**(キー=SRC slug)で再構築: volumes=**完備最古**run / 他は全て extra_editions
4. ★**`python scripts/_check-edition-canonical.py`** を必ず走らせる(下記の番人)
5. changelog1行 → `_reflect-targeted.py --only <slugs>` → **「消えたISBN」警告を必ず検分** → 検出器再走 → preview cp+索引 → commit/push

## 厳守(実踏済みの罠)
- ★★**壊れたcanonicalは無警告でskipされる**: promoteの get_edition_canonical() が `except: continue`。YAMLが壊れていてもreflectは「再生成N/検証ゲートOK」と成功を返す。→ **新設した番人 `scripts/_check-edition-canonical.py`**(パース/slug一致/死にキー/巻番号重複/release_dateが文字列か/isbn13が13桁)を毎回走らせる。実験人形ダミー・オスカーで実踏(volumes配下のインデント2スペースと0スペースの混在)
- ★**反映の「消えたISBN N件」は必ず追う**。少年ケニヤ(角川文庫11/12/17巻)とダミー・オスカー(漫画スーパーワイド5巻)はこの警告だけが取りこぼしのサインだった
- ★**連載中の作品にcanonicalを使うな**(巻が固定され続巻が出なくなる)。1巻だけ重版日で逆行しているような型は **`data/seeds/release-date-override.jsonl`**(isbn13→date の強制上書き)で直す。キン肉マン(93巻)で実証
- ★**文庫タブの混在は canonical では直らない** → `suppress_types: [bunkobon]` + bunkobonのextra_editionsで作り直す(canonicalが自動で作り直すのは standard/aizoban だけ)
- ★**extra_editions は既存タブを消さない** → 種2側に同じ版が居ると**二重タブ**になる(black-angels)。extraを足す時は suppress_types をセットで
- ★**版元が両ソースに無い版は `publisher: 不明`** と明示してよい(pub_key_of が解決せず publishers[] を汚さない)
- ★**レーベル名が不明な主版は `canonical_label` と `canonical_imprint` を両方省略**(labelだけ書くとレーベル欄に「通常版」が出る)
- ★**古いvolume-excludeが版分離の邪魔をする**(2026-07-04の「激マン型混入」67件)。canonical新設時は該当ISBNが除外入りしていないか見る
- ★**work-level publisher は最多巻の社の多数決**(canonical後に再導出)。温存タブのpublisherが空だと化ける
- **捏造しない**: 両ソースに無い巻は入れない/欠番は空けたまま/1冊しか記録の無い版はその1冊だけで立てる。NDL不在≠不存在
- release_dateは**必ず引用符**(裸のフル日付はYAMLがdate型にする= shumariで実踏)
- **A型(別作品混在)はギャラ式**: 同_skeyのstub×2 + edition-overrides(公開slugキー)+ `"anilist": false`

関連: [[edition_canonical_mechanism]] [[edition_mix_same_author_ayako]] [[never_delete_because_broken]] [[merge_needs_external_proof]]
