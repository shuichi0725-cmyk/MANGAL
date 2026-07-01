---
name: ndl_nonmanga_sweep
description: ユーザNDL RDF出力×ISBN突合で非漫画(アニメコミック/原画集等)を炙り出す手順と注意。罠=ファンブックに漫画/画集に混在
metadata: 
  node_type: memory
  type: reference
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

★MADB titleがmarker欠落の非漫画(アニメコミック/フィルムコミック/アンソロジー/画集)は既存filterをすり抜ける(例: 北斗の拳∅=実体アニメコミックス)。 ★**ユーザがNDL詳細検索→DCNDL RDF出力(ISBN列込)→私がISBN突合**で全DB横断検出(著者付き非漫画=鳥山明DBZ/青山剛昌コナン劇場版も捕捉=APIの著者ゼロ監査では不可)。 ユーザはAPIレート制限を受けない=最強。

**手順**: RDFをBibResource単位でparse→ISBN(ISBN10→13変換)抽出→`SELECT series_id FROM volumes WHERE isbn13=?`で突合→ratio(一致/総巻)≥0.7 or 自前title markerでseries-drop。 ★**広いAND検索(スペース有「フィルム コミック」)はノイズ→「NDL記録のtitleにmarker有のISBNだけ」採用で除外**(489→99等)。

**実績(2026-06-04・non-manga-drop.yml)**: アニメコミック154 / フィルムコミック25 / 原画集→**画集方針転換でrevert**([[art_book_inclusion]])。 初回著者ゼロ11。

**★罠(ユーザが発見・慎重必須)**:
- ★**ファンブックは漫画が載りうる**: 猫なんかよんでもこない。その後(9784408414171)=Amazon全5巻の5巻目=公式ファンブックだが**描き下ろし漫画入り・シリーズ巻**→keep。 →**ファンブックは一律dropせず、 シリーズ巻/同作画家/漫画入りはkeep**。 ファンブック22件はrevert済。
- ★**1巻・画集・2巻の混在**: 漫画seriesに画集巻が紛れる(うる星165巻に画集1巻)→series-drop不可→**ISBN単位で除外**([[art_book_inclusion]]のexclude-isbn)。
- ★**画集なのに小説**: とあるVISUAL BOOK=画集に書き下ろし小説。 ハイブリッドは主体で分類+作画家紐付け(原作者回避)。
- ★**本編存在チェック**: 非漫画dropの前に本編漫画がDBに在るか確認(無いと作品消滅)。
- ★**作品集はkeep**(描き下ろし)、 傑作選/総集編はdrop。 漫画集(まんがしゅう)≠画集。

**安全カテゴリ(dropして良い)**: アニメコミック/フィルムコミック(映像のコマ=描き下ろし無)。 **危険カテゴリ(漫画混入)**: ファンブック/アンソロジー/トリビュート→慎重に。 ★月次監査候補=NDL完全title照合。
