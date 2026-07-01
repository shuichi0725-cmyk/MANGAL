---
name: multi-edition-unification-pending
description: 【未決・重大】版違い統合=同一漫画の複数版をどう1ページに載せるか。edition keyがtype単位で同type多版(別社standard)が潰れる。表紙違い/番外編/復刻BOXの扱いも未決
metadata:
  node_type: memory
  type: project
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

★【未決の設計課題・ユーザが「今までで一番の問題かも」と評した深い論点】(2026-06-03 議論)。

**正しい問題設定**(ユーザ修正): 「多版から本編版を1つ選ぶ」ではない。 ★**同一漫画(シリーズ)の版違いを全部1ページに束ねる**(=うる星やつらモデル: 1ページ・複数edition並置、捨てずに並べる)。 ISBNは各版を捨てずに保持しているので情報は揃っている。

**同一性の根拠はある(=希望)**: 例 天使のたまご(岸香里)の4版は種2で **qid=Q108415280 に既にクラスタ済**。 識別は cm104凍結でも qid で可能。 残るは**描画と束ね方**。

**★核心の技術障壁 = edition keyが type 単位**:
- MANGALのedition区分 = type(standard/wideban/bunkobon/kanzenban/shinsoban/aizoban)。
- うる星が綺麗なのは3版が **type違い**(通常=standard/ワイド=wideban/文庫=bunkobon)だから区別できる(1社がtypeを分けて出した偶然)。
- ★**別社再版が絡むと「学研standard / 青春standard / 2005standard」= 同typeが複数** → promoteが同type同士を潰し1版しか出ない(天使のたまごで学研原版#1#2が消え青春版が残った現象の正体)。
- ★**対策案 = edition key を type → (出版社[ISBN6桁prefix] × type) に拡張**。 これは再版を持つ全作品に波及する **systemic** な設計変更。

**★さらに未決の難所(ユーザ提起、これも先送り中)**: 版違いの「種類」が単純でない:
- ★**表紙違いの同type**(うる星=表紙違いstandardが番外編含め最低2つ)。
- ★**番外編**(本編と別だが同シリーズ)。
- ★**復刻BOX/初代復刻**(箱売りセット商品)。
- = 「standardが複数」をどう区別・命名・並置して載せるか(版名ラベル/出版社/年/装丁)が ★**未決**。 ユーザと「ISBNは捨ててないからどうにかなる」と合意し先延ばししていた決定。

**天使のたまご= 最初のテストケース候補**(詳細は別途調査済): qid Q108415280、4版=①学研ナーシング全3巻(9784051509538/9784051509361続/9784051518639in東京)②青春プチbook1998(9784413098151/8)③幻冬舎文庫2001(9784344401112)④2005上下(9784900963290/306)。 種2の歪み=ed1362が①学研#1#2と④2005を混在、 ③in東京だけ別sid1031分離。 付随作業=押井守版『天使のたまご』(アニメージュ文庫1985・ISBN無=アニメ映画本=非漫画)を drop([[non_manga_drop_cleanup]])。

**★2026-06-04 機構実装済(opt-in)**: blanket(type×imprint)は影響調査で**4912ページ波及・古典重版爆発**(鉄腕アトム=Akita top comics/KCDX/KPC/My first big廉価版…が10+セクションに)と判明→**不採用**(現状のtype畳み込み+最古正典は古典に正しい挙動)。 ★代わりに **opt-in方式**を実装(`_promote-bulk-v2.py`): series-merge.ymlの **`separate_editions: true`** を付けた群だけ edition grouping を (type × imprint) に分離=別版を別セクション併置。 無印は従来通り=**既存ゼロ影響**。 `load_separate_edition_sids`/`get_separate_edition_sids`(renumber機構と同型)、 group_keyにimprint含め、 output typeはprimary_ed[type]採用。 ★**初適用=シートン(谷口ジロー旅するナチュラリスト)**: ACTION COMICS版(巻1,2/2005-08)+谷口ジローコレクション版(巻1-4/2023)の2セクションをユニットテストで確認。 鉄腕アトム(無印)が21巻standard畳み込み維持=非爆発も確認。 ※種4補完併用時のcomposite key対応は将来課題(シートンは種4無し)。

**残課題**: 天使のたまご(qid Q108415280, 4版)は同社別typeでなく**別社standard複数**なので separate_editions 付与で綺麗に並ぶか要検証(ed1362の混在歪みは別途要解消)。 表紙違い/番外編/復刻BOXの版名ラベル付けは引き続き未決。 ★ACTION版シートンは巻3,4取りこぼし=種4補完候補(巻4 ISBN=9784575941517確定、巻3はNDL未登録で要裏取り)。

**★ラベル方針 確定(2026-06-08 ユーザ決定)**: 「同じ作品の別物理版=タブ / 別内容=別ページ+関連リンク」。具体=①**表紙違い(同冊数・同内容)=版タブ**(versions[]) ②**冊数/サイズ違い(ワイド/文庫/新装/愛蔵/復刻)=版タブ**(うる星モデル) ③**復刻BOX(同内容の箱)=版タブ** ④**番外編(別内容)=別ページで独立**(=別漫画扱い、既存「別作品=別ページ」原則どおり) ⑤番外編は**将来「関連漫画」欄を下部に作って誘導**(mergeしない)。→ 新設計不要、既存(版タブ+別ページ)で対応可。残実装=表紙違いがversions[]に乗るか確認/番外編が誤merge されない保証/関連漫画欄(将来)。

**★2026-06-10 本番実測(着手前にスケール測定。Part2ベルセルクの反省で「本当に問題か」を先に確認)**: 本番manga.v2(overlay適用後)で「同一作品が版違いで複数ページに分裂」を測定 → **真の版分裂=2件のみ**(こち亀/マンガ日本の歴史、それもslug表記揺れ実体)。**うる星モデル(版をtype混在で1ページ内に統合)は本番で機能している**(例 bar-lemon-heartが{standard,bunkobon}内包)。= ★**「分裂」manifestationはマス問題でない**。残る「潰れ」(別社standard欠落)は上記separate_edities opt-inでper-case対応。★**両調査(続編96/版違い66)が指す真の残構造問題=「同一作品の重複ページ」~100-150件**(slug表記揺れ`-2`/`-2025`/`ki↔koryakuki`/`o↔wo` + クラスタ分裂由来)。これは版違い統合でなく**重複ページdedup**で、slug作業と表裏一体。教訓: [[promote_hangs_on_exit_windows]]同様、着手前に本番実スケール測定。

**現状**: opt-in機構=実装+ユニットテスト済(本番promoteは次回蒸留 or 明示時に反映)。 ラベル方針=上記で確定。 天使のたまご個別=ed1362のimprint=None混在(学研版+2005版)は publisher(ISBN prefix)分割が要る深い手当て=別途。 関連: [[volume_split_merge]][[series_fragmentation_rootcause]][[madb_cm104_frozen]][[ndl_volume_structure_resolves_fragmentation]]、 CLAUDE.md「うる星multi-edition統合」「KEEP_EDITION_TYPES」。
