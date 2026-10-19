---
name: other_names_multilingual
description: 他言語名(other_names)=言語名つき表示・AIが埋めた英題は表示しない(ユーザ裁定A1 2026-10-19)。全頁適用済み・本番は次の週次・月次配線が未完
metadata:
  node_type: memory
  type: project
  originSessionId: 4eb881fe-cc0f-412d-b718-0578babc3249
  modified: 2026-10-19T02:56:41.857Z
---

2026-10-19 らんま1/2「他言語がハングルしかない」報告 → 全頁見直し。

**原因(型)**: 種3の英題 43,814件中 **37,716件は旧slug規則(英語名優先)のためAIが埋めた訳題**(`data/seeds/_fills` の amiss-/batch-/en-corrections)。頁上で公式英題のように出ていた(約2.9万頁、うち2,381頁は公式英題が別にある)。AniList の title.english は取り込まれず synonyms だけ・タイ語は enrich map の syn_ok で捨てていた・漢字だけの中国語題は「別名(日本語)」側に誤分類。らんまの英題は旧slug規則のため種3で `en: null` 削除済み(slugはもう英題から作らない)。

**★ユーザ裁定 A1**: AIが作った訳題は**表示しない**(検索の手がかり=alt索引には残す)。

**実装(commit 93bc09118b)**:
- 正本 = `scripts/_other_names.py`。英語 = AniList公式英題 > Wikidata en > 種3/MADB/NDL併記題(レーベル名・年は JUNK_EN で除外)。他言語 = Wikidata rdfs:label(主要13言語)+ AniList synonyms の文字種判定。日本語題のローマ字の写しは出さない(公式英題以外)。
- 出所 cache: `.cache/work-qid-map.json`(`_fetch-work-qid.py`・6,208作)/ `.cache/work-labels.json`(`_fetch-work-labels.py`・QLever)/ `.cache/anilist-titles.json`(dump から自動生成)。★月次蒸留で両 fetch を再実行すれば新作に付く。
- promote が全頁に `other_names` を書く(空でも [] = 処理済みの印)。作品頁は欄が**在れば新表示・無ければ旧表示**(lib/otherNames.ts)。
- AI判定は種3キー+値の一致(後から手で直した英題は値が違うのでAI扱いしない)。

**状態(2026-10-19)**: テスト10頁の見た目 → ユーザ「ok」 → **全頁に一括適用済み**(`scripts/_apply-other-names.py`・commit fbd2536587)。本番データ 69,648頁: 他言語名あり 23,306 / AI訳題を外す 27,475(うち公式英題へ置換 3,102)/ 英題が新たに出る 861。退避 = `.cache/other-names-bak-20261019/manga.v2.tar.gz`、記録 = `data/seeds/other-names-changelog.jsonl`(概要1行)+ `other-names-apply-20261019.tsv.gz`(頁ごとの前後)。★統合台帳には概要1行だけ(slug="*")= `_ledger.py <slug>` には出ない、頁ごとは tsv.gz を引く。
- ⏳**本番R2は次の週次蒸留**(作品頁コードを変えたので、それまで「差分反映して」はコードドリフトで週次へ回される)。
- ⏳月次蒸留に `_fetch-work-qid.py` / `_fetch-work-labels.py` は**未配線**(新作に Wikidata ラベルが付かない。AniList 英題・別名は dump 更新で付く)。
- 既存頁は種3キーが無いので AI判定は推定(題+値・表記ゆれ・持ち主が全部AI)。次のフルpromoteからキー判定に切替 = 数百頁で英題の出る/出ないが揺れうる。

関連: [[display_data_polish_tasks]] [[work_qid_enrichment]] [[feedback_accuracy_is_the_goal]]
