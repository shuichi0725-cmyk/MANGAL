---
name: diff-deploy-subset-related
description: 【型・根治済 2026-09-23】差分反映は対象頁だけのデータで建てていた=関連作品/著者keyが部分集合から計算された(うる星やつら→同じ回の44頁)。全件hardlink+生成だけ絞るに変更。関連の並びも見直し
metadata:
  type: project
---

**症状(ユーザ報告 2026-09-23)**: うる星やつらの関連作品が 赤いペガサス/おれは直角/まことちゃん(同誌)… で、
高橋留美子の作品が1本も無い。めぞん一刻・犬夜叉など他頁は正常。

**原因**: 本番のうる星やつら頁は 09-22 週次の**後の差分反映(44頁)**で上書きされていた。
`_deploy-differential.py` は **対象頁だけ**を `.cache/diffdata/manga` に置いて next build していたため、
`loadAllManga()` = 44頁 → `computeRelated` がその44頁から選んだ(関連に出た8作は全部その回の対象頁)。
同じ型: `authorKeyFor`(lib/authors の -2 連番。同読み別人 **418人**)も部分集合で振り直される。
ハブリンク(lib/hubs)は一覧索引(全件コピー)由来なので無事だった。

**根治(commit 22fa5f9d5)**: 公開済み全頁(prod-pages-manifest)+対象頁を hardlink で置き、
**生成だけ** env `MANGAL_ONLY_MANGA_FILE`(lib/loadData `buildOnlyMangaSlugs`)で対象頁に絞る。
差分ビルドでは著者2万頁を作らない(`app/author/[key]` が _empty)。所要 数分→**~12分**(実測746秒)。
★教訓: 「部分ビルド」は**生成を絞る**のであって**データを絞ってはいけない**。頁が全作品を見る処理
(関連・著者key・将来の横断機能)が黙って壊れる。preview(subset)は設計上の割り切り。

**同時にアルゴリズムも見直し(lib/related.ts)**:
- 候補側の多人数名義ガード(著者5人以上の候補は「同作者」に数えない)= 水木しげる漫画大全集(42名義)等の混入を除去
- 同作者の並び = 旧「新しい順」(単発読切ばかり上位)→ **3冊以上を先・発表年の近い順・slug**。人気値は使わない
- 結果: うる星やつら → パーフェクトカラー/めぞん一刻/るーみっくわーるど/人魚/らんま/1ポンドの福音/犬夜叉/高橋留美子劇場/RINNE/MAO

**本番反映 = 週次蒸留**(漫画頁コード変更=差分反映は次の週次まで abort)。週次の全件ビルドで44頁も直る。
関連: [[seo_index_coverage_state]] [[partial_rebuild_merge_recovery]] [[build_input_wiring_three_places]]
