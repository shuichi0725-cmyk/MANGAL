---
name: other_names_multilingual
description: 他言語名(other_names)=言語名つき表示・AIが埋めた英題は表示しない(ユーザ裁定A1 2026-10-19)。テスト10頁で見た目確認待ち→全頁適用が未完
metadata:
  node_type: memory
  type: project
  originSessionId: 4eb881fe-cc0f-412d-b718-0578babc3249
  modified: 2026-10-19T02:26:23.397Z
---

2026-10-19 らんま1/2「他言語がハングルしかない」報告 → 全頁見直し。

**原因(型)**: 種3の英題 43,814件中 **37,716件は旧slug規則(英語名優先)のためAIが埋めた訳題**(`data/seeds/_fills` の amiss-/batch-/en-corrections)。頁上で公式英題のように出ていた(約2.9万頁、うち2,381頁は公式英題が別にある)。AniList の title.english は取り込まれず synonyms だけ・タイ語は enrich map の syn_ok で捨てていた・漢字だけの中国語題は「別名(日本語)」側に誤分類。らんまの英題は旧slug規則のため種3で `en: null` 削除済み(slugはもう英題から作らない)。

**★ユーザ裁定 A1**: AIが作った訳題は**表示しない**(検索の手がかり=alt索引には残す)。

**実装(commit 93bc09118b)**:
- 正本 = `scripts/_other_names.py`。英語 = AniList公式英題 > Wikidata en > 種3/MADB/NDL併記題(レーベル名・年は JUNK_EN で除外)。他言語 = Wikidata rdfs:label(主要13言語)+ AniList synonyms の文字種判定。日本語題のローマ字の写しは出さない(公式英題以外)。
- 出所 cache: `.cache/work-qid-map.json`(`_fetch-work-qid.py`・6,208作)/ `.cache/work-labels.json`(`_fetch-work-labels.py`・QLever)/ `.cache/anilist-titles.json`(dump から自動生成)。★月次蒸留で両 fetch を再実行すれば新作に付く。
- promote が全頁に `other_names` を書く(空でも [] = 処理済みの印)。作品頁は欄が**在れば新表示・無ければ旧表示**(lib/otherNames.ts)。
- AI判定は種3キー+値の一致(後から手で直した英題は値が違うのでAI扱いしない)。

**⏳状態**: テスト環境に10頁(らんま・フリーレン・進撃・ベルばら・はだしのゲン・鬼滅・とんがり帽子・惡の華+比較用 ぼくのパパとパパの話/交換ウソ日記)を出して**見た目の確認待ち**。OKが出たら全頁(約6.6万)へ other_names を書く(フルpromote待ちにしない=一括適用を別途)→ 週次蒸留で本番。未適用の頁は旧表示のままなので、先に週次が走っても後退はしない。

関連: [[display_data_polish_tasks]] [[work_qid_enrichment]] [[feedback_accuracy_is_the_goal]]
