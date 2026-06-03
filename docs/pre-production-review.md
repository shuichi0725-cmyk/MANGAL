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
- kana_pua 0(良好)。 ★既存の NDL furigana 監査([[furigana-ndl-audit]])で大半是正済。 ★**最終 NDL spot-check を推奨**(残差確認)。

---

## 漫画名(title)

- **title_pua 13**: ★**不可視PUA文字混入**。 `❤/★`(U+E2BB等)や `é/à`(Atta2=Attaché?/Dj vu=Déjà vu、 U+E310等)が PUA に化けている。 ★表示title に不可視ゴミ → 復元(❤/é)or 除去候補。 `.cache/preprod/title_pua.tsv`。
- **外国孤児 3**(drop候補): `Raina Telgemeier ; with color by…` / `Yoshihiro Togashi ; [traduit…français]` / `Akira Toriyama ; [Svensk text…]` = ★翻訳credit が title になった外国版 → non-manga-drop 追加候補。
  ※「;」を含む正当題(Steins;Gate / Robotics;Notes / デュラララ Re;)は **誤検出=触らない**。
- **title_latinonly 3,739**: ★**大半は正当**(Akira/PRIEST[manhwa]/STAR WARS[licensed]/Robotics;Notes 等の英題作)。 ★低優先。 但し**foreign版の紛れ込み**が残る可能性 → 別途「latin題 ∧ kana無 ∧ 外国ISBN」で絞った spot-check 推奨。
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
| 任意 | slug_toolong 短縮 | 1,609 | 大半正当 |
| 別途 | latinonly foreign精査 | 3,739中の少数 | 大半正当 |

★= ★**最優先は slug衝突の解消(slug生成器改修)**。 他は小規模の個別候補。 ★全て**未適用**、 GOサインで着手。
