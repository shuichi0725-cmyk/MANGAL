---
name: memory-archive-index
description: 完了・解消済み・歴史記録の記憶の索引(2026-10-06にMEMORY.mdの容量対策で本体から外した分。ファイルは全部残っている)。同型の再発や経緯を引く時に開く
metadata:
  type: reference
---

MEMORY.md 本体から外した完了・歴史の記憶。題は外した時点の原文のまま。

## 本番待ち・宿題・計画
- [【全実装済】検索フィルター一式](filter_ui_todo_2026_09_05.md)
- [【✅】FilterPanel件数表示](filterpanel_show_counts.md)
- [進行中状態2026-08-13](inflight_state_2026_08_13.md)

## 蒸留・取込
- [phase2文字化け2件skip](phase2_corrupted_keys.md)
- [蒸留定期運転の実態(2026-06調査=歴史)](monthly_intake_reality.md)
- [2026-08 月次蒸留 MADB1.2.19=完了](distill_2026_08_1219.md)
- [2026-07 月次蒸留 MADB1.2.18](distill_2026_07_1218.md)
- [週次リハーサル2026-09-02=アップ直前まで実測+穴](weekly_rehearsal_2026_09_02.md)
- [2026-09 月次蒸留 MADB1.2.20=完了](distill_2026_09_1220.md)

## 掲載範囲
- [コンビニ判一掃=148drop/16hold](konbini_reprint_sweep.md)
- [2026-09-01 drop16頁](drop_batch_2026_09_01.md)

## 巻・版・ISBN・頁の分裂と統合
- [【封鎖済】巻抜け仮想の偽陽性2種](volgap_virtual_false_positives.md)
- [【是正済】巻抜け検出の穴2つ=先頭欠け見逃し+入力TSV凍結](volgap_leading_gap_and_frozen_input.md)
- [【是正済】巻抜け仮想のgap判定=索引と同じ版単位に](volgap_virtual_edition_unit.md)
- [重複ページdedup完了](page_dedup_2026_06.md)
- [分裂・過統合クリーンアップ](fragmentation_overmerge_cleanup.md)
- [発売日逆行515件リスト](volume_date_disorder_list.md)
- [【✅】題+巻→楽天照合適用済](harvest_match_mechanism_applied.md)
- [【✅完遂】ギャラ型=巻×日付大逆行の是正](gyara_type_regression_cleanup_state.md)
- [【✅】がきデカ型=一部ISBN欠け機械是正](partial_isbn_gap_mechanism.md)

## キャッチ・あらすじ・ジャンル・要素
- [【✅】短キャッチrequeue完了](synopsis_short_requeue_done.md)
- [【✅】楽天あらすじ→genre/tag](genre_from_rakuten_story_plan.md)
- [ジャンル不一致514全裁定](genre_disagree_adjudication_state.md)
- [【✅完走】BookLive紹介文=第2材料源](enrich_booklive_seam_done.md)
- [【✅適用済】ラブコメ復権=romcom裁定](romcom_backfill_state.md)
- [【✅】派生ジャンル規則=promote恒久層](genre_derive_rules_layer.md)
- [【是正済】副題欄に副題でない物=3,324→3,141](subtitle_not_subtitle_cleanup.md)
- [キャッチから要素付与(10-01・後継は③)](themes_from_catch_2026_10.md)
- [Kobo紹介文→キャッチ5,811作(10-02)](kobo_caption_catch_route.md)

## 書影
- [kobo見直しセット復元](kobo_review_preview_set.md)

## 著者・ヨミ・slug・NDL
- [著者汚染overlay修正](author_pollution_overlay_fix.md)
- [フリガナ正当性検証完了](kana_validity_state.md)
- [NDL option2再クラスタ](ndl_option2_recluster.md)
- [slug主版消失修正+来歴ログ](slug_cluster_fix_and_changelog.md)
- [著者kana完埋め済](author_kana_fill_state.md)
- [【✅】slug適用パイプライン](slug_apply_pipeline.md)
- [新刊著者の連結バグ是正](new_manga_author_reparse.md)
- [【調査済】年サフィックスslug全洗い出し](year_suffix_slug_survey.md)
- [【✅】著者名の空白=authorKeyで照合吸収](author_name_space_conventions_conflict.md)

## 外部ソース(AniList・楽天・試し読み等)
- [AniListリンク精度=解消済](anilist_link_quality.md)
- [AniListリンク検証 全✅](anilist_link_verification_plan.md)
- [試し読み裁定=枯れ達成](tameshiyomi_adjudication_state.md)

## 公開・配信・検索・SEO
- [【✅】Kindleはブラウザで開く=解決](kindle_link_browser_not_app.md)
- [検索warm並走の競合型](search_warm_race_2026_08_31.md)
- [【✅】死蔵検索索引=廃止済](dead_search_index_retire_pending.md)
- [/browse がサーバ描画0だった](browse_ssr_shell_and_seo.md)
- [【✅修復済】301リダイレクト層=KV稼働](redirect_layer_inactive.md)

## 作品別・コーナー
- [ソーサリアン統合=本番化済](sorcerian_consolidation_state.md)
- [【✅】手塚全集タブ全滅→復旧](tezuka_tab_empty_pages.md)

## 道具の罠・運用の型
- [promote完了後プロセス居座り=os._exitで解消済](promote_hangs_on_exit_windows.md)
- [【✅】連載中再検査=外部権威降格層](ongoing_status_recheck_mechanism.md)
- [【復元済】源なしmanga.v2頁258件](orphan_source_pages_restored.md)

## 作業環境
- [新PCへ移行済み2026-07-17](pc_migration_2026_07_17.md)
