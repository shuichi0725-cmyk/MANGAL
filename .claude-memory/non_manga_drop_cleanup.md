---
name: non-manga-drop-cleanup
description: data/seeds/non-manga-drop.yml=掲載対象外をseries_keyで除外。外国版/satellite編集本/画集/アンソロジー。本編照合方式で安全drop
metadata: 
  node_type: memory
  type: project
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

★`data/seeds/non-manga-drop.yml`(2026-06新設、 promoteが series_key で除外、 種2/種3不変・可逆)= 掲載対象外を明示key列挙でdrop。 slug生成器も同listを除外。

**現状 388件**(reason別):
- `foreign_edition_or_broken` 14: 外国語版書誌(スウェーデン語版ONE PIECE/タンタン/仏BD)。 全76,435中わずか17件と網羅scanで確定([[mangal_inclusion_scope]])。
- `satellite_compilation` 173: ★**本編照合方式**=怪しい語(スペシャル/セレクション/総集編/DX/SP/傑作選等)を抜いた題が『番号付き本編』に一致する0-1巻=編集本。 酒のほそ道スペシャル⇄57巻 等。 ★抜いて本編無し=実作品は保護(478件)。
- `compilation_artbook` 67: イラスト集/トリビュート/best selection/THE MOVIE/THE n LOG/キャラクターリミックス/Season Best/データブック。 ★図鑑(おとめ図鑑=実作品)/プレミアム/plainリミックスは誤爆回避で除外。
- `mega_series_compilation` 131: 長尺本編(20巻+)を含む+編集語の0-1巻(鬼灯○○セレクション/トッキュー!!特別総集編)。 spinoff語(外伝/Legend of/returns)は守る。 ★ambiguous(School Rumble Z等)は触らない。
- `anthology` 3: galaxy-angel-parody(パロディアンソロジー、 Amazon15名/Yahoo明示)。

**★安全保証**: drop追加時は必ず ★**merge絡み検証**(dropキーが本編[≥10巻]と同一merge群に居ないか)= 本編影響0を実証してからcommit。 検出器は sanitized maxvol(BETWEEN 1-400、 年誤parse除外)使用。

**★守る原則**: 文言単独dropは誤爆(「セレクション」183件/「スペシャル」324件に実作品多数)→ ★0巻+語+本編存在 の組合せ判定。 EMPTY slug≠junk(上全/Page1=実在、 [[mangal_inclusion_scope]])。

関連: [[volume_split_merge]]、 [[mangal_inclusion_scope]]、 slug first-pass(`_gen-slugs-firstpass.py`)。
