---
name: madb-volume-misnumber-fix
description: MADB誤番号是正(下=3型)。上下2冊が[1,3]と水増し表示される系統バグ~1,677件をpromoteで1..N振り直し。番号gap検出器は月次監査候補
metadata:
  node_type: memory
  type: project
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

★MADBの系統的「巻番号水増し」バグと是正 (2026-06-03 実装・commit d54de21)。

**バグ**: MADBが「下」巻を**上中下の3番目**として `number=3` に付番 → 中が無い上下2冊作品が **[1,3](2が欠番)** と表示され「3巻ある」ように水増しされる。 例: うる星やつらパーフェクト★カラーエディション(上=1/下=**3**、 cm107巻ソートは正しく上1.0/下2.0なのに種2が3)。 ★**全DB ~1,677件**(merge解決後page×edition、 上下/上中下/前後が完全に揃い番号gap)。

**是正**(`_promote-bulk-v2.py` `_fix_complete_sequence_numbers`、 get_editions_with_volumes末尾で全editionに適用):
- ★**完全sequenceのみ対象**: ラベルが {上,下}/{上,中,下}/{前,後}/{前,中,後} を**完全network**し、 巻数一致、 かつ番号が1..Nでない時のみ、 ラベル順(上<中<下、 `_SEQ_RANK`)で **1..N振り直し**。
- ★**片側欠落(下のみ等)は触らない**(= 上巻欠落の取りこぼり40件。 renumberすると孤立下を1巻にしてしまう)。
- merge由来(カラーED=別sid統合後の上下)も単一sid多版(精霊の守り人=朝日文庫上下)も同じ`out`ループで是正。

**検証**: unit test 6パターン全正解(欠落保護含む) / カラーED(下3→2)・精霊の守り人(文庫上下→1,2、他edition無傷)end-to-end / 42-sample回帰=カラーEDのみ変化。 live `data/manga/urusei-...karaa-edeishon.yml` も下=2へsurgical是正(v2はsynopsis空化するのでコピー不可→liveを直接編集)。

**★番号gap検出器=script化済**: `scripts/_audit-volume-numbering.py`(月次監査の番号層、 read-only、 CLAUDE.md組込済)。 merge解決後 page×edition で `max(巻番号)>実巻数` を3分類: AUTO_FIXED(上下完全揃い1,677=promote是正済・件数監視) / MISSING_HALF(片側欠落55=種4領域・renumber不可) / GAP_OTHER(真の欠番・外れ値=8,296)。 出力 `.cache/audit-volnum-{summary.md,missing.tsv,gapother.tsv}`。

**★巻番号外れ値の是正(commit ae7f874)**: `_sanitize_volnum` 閾値を **1900→400** に拡張。 GAP_OTHERの外れ値の正体=★**タイトルの漢数字が巻番号に混入**(「千」→巻1000/「人間噂八百」[八百]→巻800/「一騎当千」[千]→巻1000/こち亀の孤立巻999/式乃巻609)。 [237,1899]に正規番号は{609,800,999,1000}=全て誤値のみ(正規最大=ちび本当にあった236)→ number≥400を無条件で0降格(年≥1900も包含)。 検証: 千→2巻/一騎当千→本編24維持/こち亀→max201(999除去)。 ★単発は号扱い→連番化、 正規巻と混在editionでは外れ値が落ちる(=正規巻優先)。

**★★最大の発見=number=0「1冊目消失」バグ(commit 3178803、 本セッション最大のデータ修正)**: 種2 buildが ★**schema:volumeNumber/position(MADB構造化巻番号)を取りこぼし、 rdfs:label(裸題=数字なし)parseに頼った**ため、 1冊目(label「クマとたぬき」=数字無)が **number=0** になり、 promoteの「numbered巻があればnumber=0をskip」規則で ★**1冊目が本番から消失**(2巻物が「巻2が1冊」表示)。 number=0は ★**90,372件=全巻の26%**、 うち ★**79%(71,525)がcm101にposition有=復元可**(70,962が巻1)。 fetch-madb.ts(208行)は本来position優先採用だが、 種2構築時のデータにpositionが無く0になった(現metadata101.jsonには充実)。 = GAP_OTHER過多(8,296)の正体は取りこぼしでなくこのバグ。
- ★**修正** `scripts/_patch-volnum-from-cm101.py`(intake STAGES先頭=種2派生層の最初・rebuild後自動、 commit f49b106): number=0/nullのみ・既存値不変・冪等。 マップ `.cache/madb-volnum.json`(位置) + `.cache/madb-ispartof.json`(容器326,606件)。 ★種2は.cache(gitignore)なのでpatch自体は非永続→**scriptが再現性の担保**(rebuild毎にintakeで再適用)。 種2 backup=`.cache/db-v2.sqlite.bak-volnum-*`。
- ★★**容器ゲート(最重要安全策)**: 初版patch(容器ゲート無)は ★**buildが「著者+題幹」クラスタで紛れ込ませた別作品(スピンオフ/関連本=別C-ID容器)に番号付与=803件の誤接続**があった(恋愛ラボ本編C336182にレポートC448333、 グレンラガン本編に別editionのstray等)。 ユーザの「別エディションくっつくとまずい」懸念で発覚。 → v2は **schema:isPartOf容器がeditionの主流容器と遠い(C-ID距離>20)なら番号付与しない**(隣接≤20=同一シリーズの別容器で許容、 容器情報無=反証不可で許容)。 Pass1=position採用(遠容器除外793) / Pass2=position無の漏れvol1を容器一致(≤20)+日付≤最古numbered時のみ先頭欠充当(316)。 計71,048行→クマとたぬき[1,2]/悪の秘密結社ネコ[1,2,3,4]/恋愛ラボ[0,14,15](レポート0維持)/グレンラガン[0,1-5](stray除外)。 GAP_OTHER 8,296→6,484。
- ★副作用注意: 巻番号復元で**多版の代表選択が変わる**(高橋留美子劇場でISBN/年が変化)→ v2→live launch時に要レビュー。
- ★残GAP_OTHER 6,751 = 分裂(vol1/vol2別sid)/別冊号番号/外国版/真の長編欠番(ごく一部)。 [[madb_native_series_structure]]の「name-parse再構築が根因」と同根。

関連: [[multi_edition_unification_pending]](版違い統合の本丸=レーベル×版表示)、 [[volume_split_merge]](renumber機構)、 [[madb_native_series_structure]]、 [[madb_data_acquisition]]。
