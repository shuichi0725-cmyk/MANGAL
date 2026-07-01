---
name: furigana-ndl-audit
description: フリガナ正当性=NDL公式タイトルヨミをground-truthに3ソース監査。furigana-corrections.yml seedをpromoteが最優先。NDLにも誤り(へうげ型)
metadata:
  node_type: memory
  type: project
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

★フリガナ正当性の決定版監査 (2026-06-03確立)。 [[kana_validity_state]]の後継・強化。

**3ソースと役割**:
- 種2(MADB ja-hrkt)=`series.title_kana` / 種3(AI生成)=supplement-v2の`title_kana` / ★**NDL Search公式タイトルヨミ**=ground-truth(ISBN照合 `dcndl:titleTranscription`、 `https://ndlsearch.ndl.go.jp/api/opensearch?isbn=`、 Python直アクセス可・要0.4s遅延で礼儀)。
- ★AniList romaji は**読み監査に不適**(英語題/意訳ノイズ大: 魔法騎士レイアース→"Magic Knight"、 王様ゲーム→"left overs")。 禍霊型(漢字誤読)で稀に効くのみ。

**★独立性の盲点(ユーザ指摘)**: MADBとNDLは出版インフラ(JPRO/取次/NDL書誌)を一部共有しうる→ **AGREE(両一致)は「両方正しい」か「共有上流の誤りを両方継承」か区別不可**。 だから検証の力は**DIFFER(独立不一致)に集中**。 実測: MADB≠NDLは純コピーでない(ブ/ヴ・ノ脱落・分かち書き有無で頻繁乖離)→共有誤りは限定的。 禍霊ドットコム→種2「カレイ」誤をNDL+AniList両独立が「マガツヒ」で摘発=第3軸の実証。

**監査ツール** `scripts/_furigana-audit.py`(月次再利用):
- Stage A(network不要)で suspect絞る: **flag1**=種2 title_kanaに漢字/ラテン/ひらがな混入(生title漏れ) / **flag3**=種2-MADBと種3-AIの**独立2読み不一致**(当て字 or 誤りの裁定要)。 全76k中 flag1≈2,012 / flag3≈278。
- Stage B: suspectのみNDL照合(`.cache/ndl-yomi-cache.json`=resumable)→ **title-overlap guard**(題のカタカナ連がNDL読みに在るか=wrong-ISBN/副題汚染を除外)付き consensus pick。
- 出力 `.cache/furigana-audit-proposed.json`。

**★delivery=専用seed** `data/seeds/furigana-corrections.yml`(key=series_key→title_kana/segmented): promoteの`load_furigana_corrections`が **title_kanaを最優先**で読む(series_row[種2]/src_yml[種3]より先、 `build_yml` L1188付近)。 ★blast radius=記載keyのみ・**種2種3不変・可逆**。 source別: ndl/manual=初回54 / audit-ndl=NDL+種3独立合意 / audit-s3=種2ゴミ→種3採用。 現194件。

**★NDLも万能でない(per-case保留の根拠)**: へうげもの→NDL「ヘウゲモノ」(歴史的仮名を素読み=誤、 正ヒョウゲモノ) / 九龍で会いましょう→NDL「キュウリュウ」(当て字カオルーン無視) / 銀河鉄道999→種3「スリーナイン」当て字 vs NDL「999」。 ★= NDL単独(両local誤)のTier2は`data/seeds/_furigana-review.yml`へ退避しper-case。 **NDL+種3が独立合意した時のみ高確度**。

**★当て字は守られる**: NDLは本物の当て字を追認(悪魔の花嫁→デイモス/聖ロザリンド→セイント/私立極道高校→キワメミチ)し、 偽当て字/誤読を正す。 CLAUDE.md「当て字3ソース突合」の自動化。

**適用実績(2026-06-03、 計376件)**: 初回DIFFER54 / flag3監査140(Tier1=NDL+種3合意/Tier1b=種2ゴミ→種3) / review確信32 / flag1監査145 / ユーザ確定6。
- ★**flag1のTier2安全判定=romaji corroboration**: 種3のカタカナ核⊆NDL かつ NDL完全カタカナ化 = NDLが種3の読みを保持しつつLatinを正ローマ字化(ロックマンX→エックス/PEACE MAKER鐵→ピースメーカークロガネ/Ns'あおい→ナースアオイ)→安全適用。
- ★**flag1 manual 1705件**=英語題で純カタカナ化不可(題がほぼ英語/NDLもLatin残)=★**未決のromanize policy**(全カタカナ読み振る vs 英語表示)。最大の残課題。
- ★**特例パターン**: ミタマセキュ霊ティ=読みミタマセキュレティ(セキュレティ=Security地口)、英題Mitama Security: Spirit Busters、slug=mitama-security。furigana-corrections entryに slug/alternative_titles_en の特例メタを併記(将来slug生成/en-fillが消費)。
- ユーザ確定の異読: 度胸星→ドキョウボシ/限界集落温泉→ギリギリオンセン/のろわれた手術→ノロワレタオペ(手術=オペ当て字)/アラミス'78→アラミスナナジュウハチ/ななか6/17→ナナカジュウナナブンノロク。

★**NDL応答は分かち書き(spaced)= 1回の取得で両kana形式が得られる(2026-06-05改善、ユーザ指摘)**: `dcndl:titleTranscription`はスペース付き(例「ツバサ ゲンガシュウ」)。 `.cache/ndl-yomi-cache.json`が**生spaced値で保存済**→ **title_kana(スペース除去)とtitle_kana_segmented(スペース保持=slug用)を同一fetchから両取得でき、再取得不要**。 画集はこれを `scripts/_extract-artbook-segmented.py`(キャッシュから抽出・整合ガードnospace==確定title_kana)で `data/seeds/art-book-furigana-segmented.yml`(108件)に永続化、 build_artbookが`title_kana_segmented`出力(出力161中98件)。 ★今後のfurigana pipelineも**NDL取得時に両形式を同時保存**すべき(何度も叩かない)。 [[art_book_inclusion]]。

★**slug前最終トリアージ完了(2026-06-10)= フォルダ名(slug)観点で安全宣言**: flag1全2,012を slug影響で機械トリアージ → **無影響1,634 / ラテン読み差~280(生成器のラテン保持規則=字面lowercase採用でslug不変=「英語題policy」はslug観点で解決) / NDLノイズ100(複数ISBN照合で構造バグ無し確認、プロジェクトX=作画交代の正当シリーズ) / 真の読み違い→大半は前回適用済みと判明、残5件のみ新規追記**(May探偵=タブン当て字維持・狼狽のみ/ポケモンDP/お兄ちゃんLAB/鉄道員=ポッポヤ/堕悪=ダアク。corrections計491)。 ★B(NDL=種2合意)9件中7件は**種3の読みが優秀**(ディーフォープリンセス等)=機械合意を鵜呑みにしない教訓。 ★**システム的発見=助詞「は」→wa が生成器要件**(現本番slugに -ha- 誤り137件、再生成で一括是正。-wa-正解2,938)。 残: Tier2 per-case少数 / 月次サニティ監査への組込。 関連: [[kana_validity_state]][[shu3_kana_two_forms]][[pending_slug_generator]]。
