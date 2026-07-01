---
name: author-roles-state
description: "series_authors.role 忠実化の現状と限界。101-clean が役割タグを剥がす重要事実、104ベース1,512昇格適用済"
metadata: 
  node_type: memory
  type: project
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

series_authors.role = {artist, writer_artist, original_author} の3値。 役割は MADB schema:creator の `[漫画]/[原作]/[キャラクターデザイン]` 等のタグから `_madb_authors.py` で導出。

**★重要な落とし穴 (2026-05-30 発見)**:
- **`metadata101-clean.json` は役割タグを剥がしている** (`['高橋留美子','椎名高志']`)。 生 **`metadata101.json` にはタグ有り** (`['[メインキャラクターデザイン]高橋留美子','[漫画]椎名高志']`)。
- build の role 出所: **104(クラスタrecord)= タグ有り・クリーン** / orphan101 = books from **101-clean = タグ無し**。
- volumes(101)経由で role 再導出すると、 **別sidに紛れたスピンオフrecord に汚染**される(進撃 sid に `[原作]諫山+[漫画]士貴(別作品)`が混入 → 諫山が誤って original_author 化)。 104ベースは per-cluster なので汚染なし。

**実施済 (commit 6e0bb02)**:
- `_classify_tag`: `[キャラクターデザイン]`を editorial(`デザイン`誤マッチ)から救済→story、 `[絵]/[イラスト]/[アーティスト]`→artist、 `[脚色]/[原著]`→story 追加。
- `_merge_role`: 専用 `_MERGE_PRI={artist:0,original_author:1,writer_artist:2}` で **generic writer_artist を最下位**に(同一人物の巻間タグ統合で specific を勝たせる)。 `_ROLE_RANK`(pick_primary/series_key用)は不変=series_key影響なし。
- `_apply-roles-from-build.py`: 新 series-v2.json(build再実行で生成、104ベース)を series_key で db に map → role を **writer_artist→specific 昇格のみ** in-place UPDATE(著者集合不変=merge無影響、sid不変)。 **1,512件適用**(writer_artist 202,862→201,350 / artist→14,570 / original_author→13,690)。 進撃/うる星/berserk は正しく不変。 本番42ページ変化0(curated は単独作家中心)。

**半妖クラス 解決済 (commit a514953)**: `_apply-roles-rawfiltered.py` = 生 metadata101(タグ有り)を使い **汚染フィルタ**で救済。 ★各 record の登場著者が全員その series の確定著者集合(series_authors の mangaka 名)に収まる record のみ採用 → 進撃 sid に紛れた別作品スピンオフ(`[原作]諫山+[漫画]士貴`)は士貴が集合外で除外、 半妖は全 record が {高橋,椎名} で採用。 **8,973 昇格**(writer_artist 202,862→193,889)。 半妖修正(authors=椎名/作画, original_authors=高橋/原作)、 単独作家(進撃/うる星/berserk/鋼/コナン/DB)は writer_artist 不変、 本番42ページ変化=半妖のみ。 旧 _apply-roles-from-build.py(104のみ・orphan未対応)は統合削除。 **これが正式な role 再導出ツール**。

**捕捉した2バグ(教訓)**: ①101-clean が役割タグ剥離(生101必須)②volumes由来は別sidスピンオフ汚染(確定著者集合フィルタで除去)。 どちらも dry-run検証で事前捕捉 → rollback。

**著者ゼロ補完 (2026-06-01)**: 被覆監査で公開ページ1,164件が**著者ゼロ**判明(無職転生/虚構推理/左ききのエレン等の人気作)。 根本原因=`madb104`系がseries_authorsを欠く系統問題(著者はkey/別記録/AniListに在る)。 修正可能性: AniList staff補完746(64%)+key回収400(34%)+困難18。 ★`_build-author-fill-map.py`=dumpのstaffから`anilist_id→{authors,original_authors}`(104,308件)を**whitelist厳密分離**(Story&Art→writer_artist/Art→artist/Story→writer=authors、 Original Story/Creator=original_authors、 翻訳者/Character Design/Editor除外)。 promoteは★**著者ゼロ((unknown))の時のみ**AniList補完(`.cache/author-fill-map.json`をanilist_id経由、 既存著者上書き禁止)。 検証=虚構推理→作画片瀬茶柴/原作城平京、 無職転生→作画藤川祐華/原作理不尽な孫の手(★原作を主著者にしない=ユーザ指摘対応)。 本番42不変、 全DB時746補完。 ★残: AniList無し400件はseries_key(`name:著者|name:題`)から回収する別手法が未実装。

**著者ゼロの根本原因 確定 (2026-06-01、 虚構推理ケース精査)**: 著者ゼロは ★**MADBの巻途中での形式変更 × build残骸**の合わせ技と判明。 虚構推理: cm104シリーズC357981は creator=`[原作]城平京/[漫画]片瀬茶柴`(タグ有・numberOfItems=9)で正常。 cm101単行本は ★**vol23で形式が変わる**: vol1-22(M518456等)= `isPartOf=C357981` + dcterms:creator C52648(片瀬茶柴) + schema:creator タグ有。 ★vol23-24(M1062679/M1088431)= **isPartOf=null(シリーズから外れた)** + 新C-id `C429607(城平京)/C429609(片瀬茶柴)` + schema:creator=`["城平京","片瀬茶柴",カナ,カナ]`(★[漫画]/[原作]タグ無・フリガナ混入)。 → ①巻数16はMADBのシリーズ紐付けラグ(新巻がisPartOf喪失)で、 ★種2の24巻集約はむしろ正確 ②resolve_authors自体は両記録から著者を出せる(実証: C357981→片瀬茶柴artist / 新巻→城平京+片瀬茶柴 both writer_artist)のに series_authors が空 = ★現db-v2が著者解決適用前のbuild残骸(cluster keyは城平京を使うのにseries_authors空)。 ★MADB新形式は役割タグを落とすので原作/作画を区別できない → **AniList(役割保持)が最良の補完源**。 [[series_fragmentation_rootcause]] 関連。

**注意**: db の role 変更は `.cache/db-v2.sqlite`(gitignore)にのみ存在。 本番 yml(commit済)に半妖の結果は反映。 db 再build後は `_apply-roles-rawfiltered.py --apply` を再実行する運用(再build自体は sid変化 → series-merge-auto.json 再生成カスケード)。 関連 [[series_fragmentation_rootcause]]。
