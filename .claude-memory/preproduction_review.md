---
name: preproduction-review
description: 本番DB生成前の最終見直し(2026-06-04)。4軸(slug/フリガナ/title/副題)監査で候補を記録(未適用)。最優先=slug衝突1,794の解消(de-collapse+姓年suffix)。朝レポート=docs/pre-production-review.md
metadata:
  node_type: memory
  type: project
  originSessionId: 3fe2031d-27c6-4148-af85-43439f3427ec
---

★本番DB生成「前」の最終データ見直し。 2026-06-04、 ユーザ指示「フォルダ名/フリガナ/漫画名/副題を多角的に慎重に、 直さず候補を記録して朝レポート」。 ★**全て未適用**(GO待ち)。

**監査ツール**: `scripts/_audit-preproduction.py`(read-only、 最終ページ70,615=merge/drop適用後)。 出力 `.cache/preprod/*.tsv` + `collisions.json`。 ★**朝レポート本体 = `docs/pre-production-review.md`**(候補の全集約)。

**★最優先=本番ブロッカー = slug衝突 1,794 slug / 4,194ページ**(別作が同一URL):
- ★**469 = 同一著者franchise**(別作なのにAniList romaji[共有aid]でslug潰れ。 ゲゲゲ/RE:BORN群/赤塚バカボン各版)→ ★完全title(副題込)kana_hepburnで**固有slug化**要。
- ★**1,308 = 別著者homonym**(別作の同読み。 oni=男弐/鬼/鬼公子炎魔、 maria、 日本の歴史×29、 源氏物語、 三国志)→ ★**姓ローマ字+発売年suffix**(主版=最古/最多巻 無印)。
- ★= **slug生成器の改修**(de-collapse + suffix)が本番前の必須作業。 学習漫画common題(日本の歴史/三国志)は出版社別 or drop の方針判断も要。

**小規模の個別候補(各 未適用)**:
- slug_empty 4: γ→gamma/π→pi/＆→and/クラスめいと→個別マップ。
- title_pua 13: 不可視PUA(❤=U+E2BB / é=U+E310等。 Atta2=Attaché/Dj vu=Déjà vu)→復元or除去。
- 外国孤児 3: 翻訳credit題(Telgemeier/Togashi仏/Toriyama瑞)→non-manga-drop追加。 ※「;」正当題(Steins;Gate/Robotics;Notes)は触らない。
- sub_publisher ~8: レーベル/形式が副題欄漏れ(カーラ→レディースコミックス/銀魂THE FINAL→アニメコミックス)→クリア。
- kana_hasspace 4: title_kanaのスペース除去(protocol違反)。
- 崩れ字title: `囿者は懼れず`(囿→勇?懼→恐?)→NDL/原典確認。
- slug_toolong 1,609 / title_latinonly 3,739 = ★**大半が正当**(長文LN題 / 英題作manhwa、 ISBN978-4=日本)、 低優先。
- ★**外国版drop候補 375件**(latin題 ∧ ISBN非9784=英/仏/独/北欧。 Peanuts/Biggles/Asterix/Babymouse/Pokemon英版/作者名孤児/画集)→ scope外=drop。 `.cache/preprod/foreign_editions.tsv`。

**★状態**: 監査完了→朝レポート提出済。 ★ユーザGOサインで着手(最優先=slug de-collapse)。 [[merge-needs-external-proof]]の成果(merge約250+drop)適用後の状態で監査。

関連: [[furigana_ndl_audit]](フリガナは既に448 NDL補正・残差低)、 [[collision_slug_investigation]]、 [[merge_needs_external_proof]]、 [[pending_slug_generator]]。


## 2026-07-02 slug/フリガナ総点検表(ユーザ発注=本番前洗い出し)
- ★`docs/production-diagnostics/slug-kana-audit.tsv` = 全66,751頁×(題/現kana/slug/楽天titleKana/種2MADBkana)+flag+tier。生成=`.cache/_ska_flags3.py`(pages/rakuten-kanaは.cache/ska-*.jsonにキャッシュ済=再実行高速)。
- flag実績: **NOHYPHEN 501+LOWHYPHEN 85**(楽天分かち書き2語以上で検証済=ハイフン規則違反・機械修正可能な本命) / KANA_DIFF_RAKUTEN tier1 218 / KANA_DIFF_MADB tier1 57(=フリガナ疑義レビュー) / SLUG_TOKEN_MISMATCH tier1 3,262(hana-no-deka型=辞書誤読を含むが、**外来語英綴りルール正解slugのFPが大量混在**=kanaから英綴りを検証できない構造的限界。目視or英語辞書照合が要る)。
- NDLフリガナ列は断念(66k live=22h・キャッシュにヨミ列無し)→楽天+MADBの2ソース照合で代替、疑義のみNDL live方針。
- ★次の一手: NOHYPHEN/LOWHYPHEN 586件に「楽天分かち書き→提案slug」を生成してレビューTSV化→承認後に一括rename(slug-overrides+alias機構は整備済)。
