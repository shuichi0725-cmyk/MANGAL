# 本番DB生成前 最終見直しレポート(朝レポート)

作成 2026-06-04。 ★**候補の記録のみ。 未適用**(ユーザGO待ち)。 監査 = `scripts/_audit-preproduction.py`(read-only)。
対象 = 最終ページ 70,615(merge/drop適用後)。 詳細 = `.cache/preprod/*.tsv`。

---

## ★最優先(本番ブロッカー)= slug衝突 1,794 slug / 4,194 ページ

別作品が同一URLに衝突。 ★**これを解消しないと本番でページが潰れる**。 分類:

| 種別 | 群数 | 原因 | 推奨対応(未適用)|
|---|---|---|---|
| **同一著者 franchise** | 469 | 別作なのにAniList romaji(共有aid)でslug潰れ(ゲゲゲ/RE:BORN群/赤塚バカボン各版 等)| ★各作の**完全title(副題込)からkana_hepburn固有slug**生成。 AniList romaji共有を止める |
| **別著者 homonym** | 1,308 | 別作の同読み(oni=男弐/鬼/鬼公子炎魔、 maria、 日本の歴史×29、 源氏物語、 三国志)| ★**姓ローマ字+発売年 suffix**(主版=最古/最多巻 無印)|
| 混在(著者欠落)| 17 | 著者qid欠落 | 個別 |

★**slug生成器の改修が必要**(de-collapse + suffix)。 衝突全リスト = `.cache/preprod/collisions.json`。
※学習漫画の超common題(日本の歴史/三国志/世界の歴史)は ★suffixでなく**出版社別ページ or drop**の方針判断も要検討。

### slug その他
- **slug_empty 4**: `γ`(ガンマ)/ `π`(パイ)/ `＆`(アンド)/ `クラスめいと`(クラスメイト)= ★記号・短title でslug生成が空。 個別マップ要(γ→gamma/π→pi/＆→and)。
- **slug_toolong 1,609**(>60字): 大半は ★**正当な長文LN題**(「不死の軍勢を率いるぼっち死霊術師…」等)。 問題ではないが、 美観で80字超は短縮候補。 `.cache/preprod/slug_toolong.tsv`。

---

## フリガナ(title_kana)

- **kana_empty 1**: `囿者は懼れず` = ★**title が崩れ字**(囿=勇の誤字?/懼=恐?)→ title 訂正候補(下記 title 欄参照)。 kana 空。
- **kana_hasspace 4**: `ソード・ワールド ぺらぺらーず` / `FLORA ComiX` / `コロッケ!BLACK LABEL` / `ポケモンHGSS`(ソウシルバー間にスペース)= ★protocol違反(スペース除去要)。 `.cache/preprod/kana_hasspace.tsv`。
- kana_pua 0(良好)。 ★既存の NDL furigana 監査([[furigana-ndl-audit]])で大半是正済。
- ★**かな主体title 内部整合チェック(新規)= 16,372件照合**: 文字列不一致1,246 → 説明可能除外後317 → ★**その大半も正当**(づ/ぢ→ズ/ジ表記、 Δ→デルタ、 Ⅱ→ツー、 おもひで→オモイデ[歴史的仮名]、 ♀→オンナ)。 ★= **フリガナ品質は高い**と確認。
- ★**真の候補=kana内容ズレ 数件のみ**(actionable): `クロサギ`→kanaに「公式ガイドブック」残 / `ルミナス`→kanaに「ブルー」余分 / `ブレイブルー リミックスハート`→kanaが「ブレイブルー」のみで副題欠落 / `わがままファッション`→kanaに「ルイスタイル」余分。 = ★**別entryのkanaが紛れた疑い**。 `.cache/preprod/kana_mismatch_real.json`。
- ★最終 NDL spot-check を推奨(漢字title の残差は別途)。

---

## 漫画名(title)

- **title_pua 13**: ★**不可視PUA文字混入**。 `❤/★`(U+E2BB等)や `é/à`(Atta2=Attaché?/Dj vu=Déjà vu、 U+E310等)が PUA に化けている。 ★表示title に不可視ゴミ → 復元(❤/é)or 除去候補。 `.cache/preprod/title_pua.tsv`。
- **外国孤児 3**(drop候補): `Raina Telgemeier ; with color by…` / `Yoshihiro Togashi ; [traduit…français]` / `Akira Toriyama ; [Svensk text…]` = ★翻訳credit が title になった外国版 → non-manga-drop 追加候補。
  ※「;」を含む正当題(Steins;Gate / Robotics;Notes / デュラララ Re;)は **誤検出=触らない**。
- **title_latinonly 3,739**: ★大半は正当(Akira/PRIEST[manhwa]/STAR WARS[licensed]/Robotics;Notes 等の英題作=ISBN 978-4=日本出版)。
  - ★★**精査で確定 = 真の外国版 375件**(latin題 ∧ ISBN非9784)。 ★**複数証拠で安全判定**(ISBN単独はtypo誤判定の恐れ→回避):
    - ★**67件 = drop実行済✅**(latin題 ∧ **複数巻すべて非9784**[typoでは全巻一致不可] ∧ 本番slug有)。 Akira仏/Evangelion/Naruto/Inu Yasha瑞典版 / はだしのゲン独ポーランド版 / 千と千尋独版 / ベルばら仏版 / Babymouse/Pearl Harbor英書。 ★日本版9784の正規ページ=0件含まず(原作は別keyで存続)。
    - ★**308件 = 単巻のみ非9784(typo懸念)→ drop せず**。 ★しかも**全てEMPTY slug=本番に出ない**ので実害なし。
  - ★**なぜ既存フィルタをすり抜けたか**: 旧スキャンは「EMPTYslug + 翻訳credit文字列」依存。 これらは ★**クリーンなlatin題→有効slug生成 + credit文字列無**で両方回避。 ★**ISBN国コード(978-4=日本)を foreign判定に未使用**だったのが穴。 → ★**恒久対策=intake/dropにISBN国コード判定を追加**(要script化)。
- 崩れ字 title: `囿者は懼れず`(囿→勇? 懼→恐?)= ★要 NDL/原典確認。

---

## 副題(subtitle)

- **sub_publisher ~8**(15flag中の真): ★出版社/レーベル/形式が副題欄に漏れ込み:
  - `カーラ`→「レディースコミックス」/ `謎の水装置`→「なぞみずぶんこ : Nazomizu Comics」/ `コミック東野圭吾ミステリー`→「アンコール出版」/ `銀魂THE FINAL`→「アニメコミックス」(本体も劇場版=drop候補)
  - ★merge sub-key encoding 由来。 副題クリア候補。 `.cache/preprod/sub_publisher.tsv`。
  ※「国がサラリーマンに…」「恐怖新聞より」等は **真の副題=誤検出**。
- sub_pua 0 / sub_equaltitle 0(良好)。

---

## ★まとめ(本番GO前の必須/推奨)

| 優先 | 項目 | 規模 | 性質 |
|---|---|---|---|
| ★必須 | slug衝突 de-collapse + 姓年suffix | 1,794群 | 別作同URL=本番ブロッカー |
| ★必須 | slug_empty 個別マップ | 4 | γ/π/＆/クラスめいと |
| 推奨 | title_pua 復元/除去 | 13 | 不可視❤/é |
| 推奨 | 外国孤児 drop | 3 | 翻訳credit題 |
| 推奨 | sub_publisher クリア | ~8 | レーベル漏れ |
| 推奨 | kana_hasspace 除去 | 4 | protocol違反 |
| 推奨 | 崩れ字title訂正 | 1+ | 囿者は懼れず |
| ✅済 | 外国版 drop(複数証拠) | **67** | latin題+全巻非9784+slug有=確実(drop実行済)|
| 保留 | 単巻のみ非9784 | 308 | typo懸念+EMPTY slug=本番非出現 |
| 任意 | slug_toolong 短縮 | 1,609 | 大半正当 |

★= ★**最優先は slug衝突の解消(slug生成器改修)**。 他は小規模の個別候補。 ★全て**未適用**、 GOサインで着手。
