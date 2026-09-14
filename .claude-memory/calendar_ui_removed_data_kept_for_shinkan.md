---
name: calendar-ui-removed-data-kept-for-shinkan
description: ホームのカレンダー/タイムマシンを完全撤去(2026-09-14)。ただし data/calendar は /shinkan 生成の入力なので残す=「消せない生成物」の型
metadata:
  node_type: memory
  type: project
---

2026-09-14 ユーザ指示でホームの **カレンダー(CalendarView)** と **タイムマシン(TimeMachine)** を PC/スマホとも完全撤去。`components/CalendarView.tsx` / `TimeMachine.tsx` / 未使用だった `ReleaseCalendarMock.tsx` を削除し、旧案 `/home-design-11` の参照も外した。配信も止めた= `_r2-sync.py` の out/calendar overlay 廃止・`_deploy-differential.py` のJSON面同期から calendar を除外・`public/calendar`(1,251ファイル)削除・preview暦の生成(`_weekly-step1.py` calendar-preview / `_prodwait-to-preview.py`)廃止。

★**`data/calendar` の生成(`_build-calendar.py data/manga.v2 data/calendar`)だけは残す**。
`scripts/_gen-shinkan-data.py` が `data/calendar/release/{ym}.json` を読んで `public/shinkan/{ym}.json` を作っており、**/shinkan(今月の新刊)の面がまるごとそこに乗っている**(ヘッダーの「新刊」リンクの行き先)。止めると新刊面が死ぬ。

**Why:** 「UIを消す=その生成物も消せる」と早合点しかけた。クライアント側の fetch 元(`/calendar/*.json` を読むのは CalendarView と TimeMachine だけ)を数えて結論しかけたが、**サーバ側のビルド連鎖が同じディレクトリを入力にしていた**。消費者は「ブラウザが読む所」だけではない。[[feedback_absence_needs_verification]]

**How to apply:**
- 生成物を止める前に、★**client fetch と server ビルド入力の両方**を数える(`grep "/calendar"` を UI だけでなく `scripts/` にも掛ける)。今回の決め手は `scripts/_gen-shinkan-data.py:22` の `SRC = data/calendar/release`
- 検証は**同じ dev サーバで変更前後を描画して差分を隔離**する(git stash → curl → 比較)。今回それで「今日のことば」の欠落が**変更前から dev で0**=無関係と切り分けられた
- R2本番に残る `calendar/**` は読み手が居ない死蔵物 → `data/seeds/pending-r2-prune.jsonl` に記帳済(slug=`calendar/**`)。次の prune で消す
- 関連: [[pending_r2_prune_ledger]] [[build_input_wiring_three_places]] [[seo_release_date_pages]]
