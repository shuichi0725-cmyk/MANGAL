---
name: feature-distill
description: 機能蒸留して=非漫画の面(ホーム/検索/AI書評/コーナー/ジャンル面)+共有チャンクだけを本番R2へ反映(~30分)。漫画66k頁と索引には一切触れない。週次(3h)とdiff-deploy(データのみ)の間を埋めるコードのみルート
---

# 機能蒸留して (= コードのみ本番反映)

トリガー語: **「機能蒸留して」**。UI/機能の改修(AI書評の不具合・検索改善・コーナーの並び/挙動/中身)を
**漫画データに指一本触れず**本番へ出す。3ルートの使い分け:
- **データだけ** → 差分反映して(diff-deploy)
- **コードだけ** → 機能蒸留して(このskill)
- **両方/大規模/索引形式変更** → 週次蒸留して

## NEVER
- トリガー無しで自発実行しない(本番ルールは週次と同じ)
- **索引・calendar・sitemap・manga/** をこのルートでPUTしない(エンジンが除外するが手動でも触らない)
- 索引JSONの**形式**を変える改修をこのルートで出さない(旧漫画頁の旧JSが同名索引を読む。
  形式変更=ファイル名バンプ([[index_format_change_versioned_filename]])+週次)
- `_r2-sync.py` をfeatビルドのout/に対して実行しない(manifest全置換で漫画キーが消える)
- 価格の静的表示を含むUIを出さない(週次と同じ検査)

## 実行

```
# 1) 計画(初回や不安な時。staging+build+同期計画まで、PUTしない)
python scripts/_deploy-feature.py --dry

# 2) 本番反映
python scripts/_deploy-feature.py

# ビルド~数十分 → ★デタッチ起動+ログ監視(ツールrun_in_backgroundは~10分で親ごとkill)
#   .cache/_featdeploy.ps1: python scripts/_deploy-feature.py *> .cache/featdeploy.log
#   Start-Process powershell -ArgumentList "-NoProfile","-File",".cache\_featdeploy.ps1" -WindowStyle Hidden
#   進捗= .cache/feature-build.log(next build) と .cache/featdeploy.log
# 直前のfeatビルドを使い回して同期だけ: --skip-build
```

## エンジンの仕組み(scripts/_deploy-feature.py を理解して使う)

1. **データ凍結**: ビルドは `.cache/prod-pages-manifest.json`(本番公開済みstem)だけをhardlink stagingした
   `.cache/featdata` で行う → 本番待ちの新規頁がホーム/ジャンル面に焼き込まれ404リンク化する事故を封鎖。
2. **漫画詳細スキップ**: `MANGAL_FEATURE_BUILD=1` で app/manga/[slug] は placeholder(_empty)のみ生成
   (ビルド3h→数十分)。out/manga が6頁以上あればフラグ不発としてabort。
3. **選択同期**: out/ から manga/**・calendar/**・ルート索引5本・sitemap を除外した全ファイルを
   r2-manifest とsha256差分でPUT。チャンクはcontent-hash名=純粋追加なので**旧漫画頁は旧チャンクで無傷**
   (--pruneしない運用が前提)。既存チャンク名の中身違いは異常として明示表示(通常0)。
4. **コーナーJSONガード**: out/data/*.json 内の slug を再帰回収し、本番manifestに無い頁を参照する
   JSONはskip+警告(週次で頁公開後に再実行)。
5. **manifest増分更新 / marker は feature_commit のみ**(code_commit は触らない=漫画頁は旧コードの
   ままなので diff-deploy のドリフトガードを誤解除しない)。
6. **edge purge**: 変更したHTML(/path)+txt+data JSONを /api/purge(10/batch)。
7. **疎通**: ホーム200 / 変更面200 / **旧漫画頁200(無傷確認)** の3点。

## 事後・報告
- 報告: PUT数(頁/チャンク新規/データ)+purge結果+疎通3点+「漫画頁は次の週次で新コードに揃う」を明示
- ヘッダー等**全頁共通部品**の修正は漫画頁側は週次まで旧のまま(仕様。ユーザ合意済 2026-07-28)
- AI書評(seeds/ai-reviews.yml)やコーナーJSON(public/data/*.json)の**中身更新**もこのルートでOK
  (読者=再ビルドされる面だけ。ただし新規頁参照はガードに掛かる→週次待ち)
- 連続改修の2回目以降: コード変更が同じならビルド再利用 `--skip-build` で数分

## 関連
- 本番フル=skill weekly-distill / データのみ=skill diff-deploy / テスト確認=skill test-deploy
- 索引形式変更の規約=[[index_format_change_versioned_filename]] / 長時間ジョブ運転=skill long-job-ops
