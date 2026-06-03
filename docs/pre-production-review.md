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
- **slug_empty 4** = ✅**解決済**(2026-06-04)。 ★原因=記号題(γ/π/＆)のAniList romajiが記号自体→ASCII除去で空slug、 かつkanaへfallbackしないバグ。 ★`_gen-slugs-firstpass.py`に「空romaji→kana_hepburn fallback」追加 → γ→ganma/π→pai/＆→ando/クラスめいと→kurasu-meito。 ★再生成で **EMPTY 4→0**。
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
    - ★**375件 = drop実行済✅**(67複数巻 + 308単巻)。 ★**ISBNチェックディジット検算でtypo-proof確認**(375全て検算OK=typo 0件)。 3証拠=latin題 ∧ 全ISBN非9784 ∧ 全ISBN検算OK ∧ 日本版9784=0(誤dropリスク無し)。 Akira仏/Evangelion/Naruto/Inu Yasha瑞典/Captain Tsubasa仏/BLACK JACK仏 等の外国語版 + Babymouse/Pearl Harbor等の外国書。 原作(日本版)は別keyで存続。
    - ★単巻も「latin題+ISBN検算+国コード」で多角確認可能と判明(当初の「単巻は確認不可」を修正)。
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
| ✅済 | slug_empty(空romaji→kana fallback) | 4→0 | γ→ganma/π→pai/＆→ando/クラスめいと |
| 推奨 | title_pua 復元/除去 | 13 | 不可視❤/é |
| 推奨 | 外国孤児 drop | 3 | 翻訳credit題 |
| 推奨 | sub_publisher クリア | ~8 | レーベル漏れ |
| 推奨 | kana_hasspace 除去 | 4 | protocol違反 |
| 推奨 | 崩れ字title訂正 | 1+ | 囿者は懼れず |
| ✅済 | 外国版 drop(複数証拠+ISBN検算) | **375** | latin題+全巻非9784+検算OK(typo0)=確実(67複数巻+308単巻、 drop実行済)|
| 任意 | slug_toolong 短縮 | 1,609 | 大半正当 |

★= ★**最優先は slug衝突の解消(slug生成器改修)**。 他は小規模の個別候補。 ★全て**未適用**、 GOサインで着手。

---

## ✅ 2026-06-04 対応完了(本番前最終クリーンアップ)

| 項目 | 対応 |
|---|---|
| **外国版** | ✅ 375件drop(67複数巻+308単巻、 ISBN検算でtypo-proof)。 恒久対策=`_audit-foreign-editions.py`を蒸留intakeに組込 |
| **①title_pua** 13 | ✅ promote `_strip_pua`で不可視PUA(❤/é化け)を除去(title/kana/subtitle、 本番出力で消える)|
| **②sub_publisher** | ✅ promote `_SUBTITLE_NOISE_RE`でレーベル/形式漏れ除去(13件、 誤爆0)。「X : アンコール出版」型はXを保持。 劇場版アニメコミック4(ONE PIECE FILM RED等)はdrop |
| **③kana_space** 4 | ✅ 既存のpromote空白除去で対応済(本番では消える)|
| **④外国孤児** 3 | ✅ drop(Smile Telgemeier/HxH仏/DB瑞典=ISBN無or「A」化けでscanすり抜け→手動drop)|
| **⑤崩れ字** 1 | ★**false alarm判明**: `囿者は懼れず`は正式タイトル(Square Enix/NDL確認)。 ★直さず**furigana補完のみ**(ユウシャワオソレズ、 NDL確証)。 だろう運転回避の好例 |

★= ★**5カテゴリ全て対応 or 正しく不対応(⑤)**。 promote汎用sanitizeは将来の同型も自動で捕捉。 ★残る本番ブロッカーは ★**slug衝突1,794**(de-collapse+姓年suffix)= slug生成器改修が次の必須作業。

---

## ✅ 2026-06-04 歴史物/分断シリーズ統合(衝突解消の前段)

★**多漫画化衝突(296群)を「版違いmerge」と「別漫画化suffix」に安全に切り分け**。判定軸 = `series_authors.role`(writer_artist/artist/original_author)。

### ★決め手 = 巻番号の重複有無
- **boxed series(merge)**: 巻番号が**非重複の1シーケンス**(1..N、各巻≤1回)。MADBが表紙作家/時代別にsid分断したもの。例: 集英社版学習まんが日本の歴史(各巻の表紙を荒木飛呂彦/原泰久等が担当→14sid分断)。
- **別漫画化(suffix)**: 各作品が**vol1から始まる**=巻番号OVERLAP。古典/有名原作の独立した複数漫画化。例: 三国志(横山/園田/李志清…)・人間失格(太宰治原作の7作画)。

### 統合した歴史/分断シリーズ(計6群・series-merge.yml 489→495)
| 作品 | 統合 | 確証 |
|---|---|---|
| 日本の歴史(集英社版学習まんが)| 14sid→1 | 学習imprint∧巻1-20非重複∧本編作画おーじろう共通∧2016 |
| 日本の歴史(角川まんが学習シリーズ)| 9sid→1 | 学習imprint∧巻非重複∧吉崎観音共通 |
| はじめての日本の歴史(小学館版学習)| 3sid→1 | 学習imprint∧巻非重複 |
| 日本の歴史(集英社文庫)| 4sid→1 | 文庫版学習漫画∧巻1-20非重複∧全2007 |
| 大怪獣ガメラ | 3sid→1 | 原作高橋二三共有∧巻1-7非重複(imprint表記揺れで漏れ→原作+巻で回収)|
| 名探偵コナン特別編 | 2sid→1 | 原作青山剛昌∧巻非重複 |

### ★保留(余った物・別途個別確認)
- **日本史サスペンス劇場**(HMB): 作画完全別(井上系 vs 井出系)+片方巻番号なし = boxed seriesでない。
- **マンガ法律の抜け穴**: 原作監修が飯野たから/小早川浩で別+作画も別 = 監修交代の曖昧アンソロジー。

### ★残292群 = 純・別漫画化 → **作画+年 suffix対象**(merge不可と確認)
三国志/源氏物語/人間失格/カノン/マリア/ジョーカー/水滸伝 等。**作画(role)で一意化**する。デスノート型(原作分業だが作画一貫=小畑健)は「同作画→merge側」に落ち**誤suffixされない**(原理的に安全)。

★**slug生成器の改修方針が確定**: ①衝突群を imprint優先→巻番号非重複なら畳む(merge済) ②残りに**作画+年 suffix**(多漫画化)or **姓+年 suffix**(別作者homonym 974群)。
