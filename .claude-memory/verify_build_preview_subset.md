---
name: verify_build_preview_subset
description: 【手法】週次(3時間)を回さずに変更を実ビルドで検証する型= out/ を rename退避 → MANGAL_DATA_DIR=.preview-data で next build(3,828作品・十数分)→ 実HTMLを検算 → out/ 復元
metadata:
  type: project
---

2026-09-18 確立。**tsc も vitest も「描画結果」「metadataの実出力」を見ない**ので、
SEO/描画まわりの変更は実ビルドでしか確かめられない。かといって週次フルは3時間。その間を埋める型。

## 手順

```
mv out out.full-bak                                   # ★同一ボリュームのrename=一瞬(9.4GBでも)
MANGAL_DATA_DIR=.preview-data NODE_OPTIONS=--max-old-space-size=12288 npx next build
  … 実HTMLを検算(title / h1 / description / canonical / リンク本数 / 番人を回す)
rm -rf out && mv out.full-bak out                      # 復元(週次の出発点を変えない)
```

- `.preview-data` = **3,828作品の完全なサブセット**(masters・seeds・索引・art-books 込み)。
  GitHub Actions の preview デプロイが `MANGAL_DATA_DIR: .preview-data` で使っている**正規の経路**。
  ハブ・著者頁・コーナーも全部この縮尺で生成されるので、**作品頁の metadata まで検算できる**。
- 所要は十数分(フル3時間に対して)。

## もう一つの選択肢と、その限界

`MANGAL_FEATURE_BUILD=1 npx next build` = 非漫画面だけ(`app/manga/[slug]` は `_empty` のみ)。
コーナー/ハブの検証には十分で速いが、**作品頁が1枚も出ないので作品頁の検証には使えない**。
★この out/ に番人(`_check-ssr-content.py`)を掛けると **`/authors` が偽陽性**で落ちる
(out/author が placeholder だけ → 著者索引が空になる)。`*/_empty.html` は除外済み。

## 戒め

- **out/ を消す前に必ず rename で退避**。`out.full-bak` が在れば失敗しても即戻せる。
- 検証が終わったら**必ず復元**する。out/ は本番と対応する状態なので、中途半端な out/ を残すと
  次の週次の判断材料(番人・finalize の頁数チェック)が狂う。
- ★**commit は検証が通ってから**。この型を使えば「実物を見てから push」が現実的なコストで回る。

関連: [[ssr_content_gate]] [[preview_deploy_github_actions]] [[long_job_ops]]
