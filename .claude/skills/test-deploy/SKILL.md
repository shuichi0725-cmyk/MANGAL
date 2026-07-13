---
name: test-deploy
description: テスト環境に出して=対象頁を.preview-dataへ投入/入替してmangal-previewで確認可能にする(push自動デプロイ・15-20分)
---

# テスト環境に出して (= preview投入)

トリガー語: 「テスト環境に出して」「テストに入れて」「preview で見たい」等。
★**「本番待ち全部」を出す時は skill prodwait-preview**(`_prodwait-to-preview.py --push` 1コマンド=週次の事前レビュー)。このskillはper-case/少数セット用。

## 手順
1. 入替なら先に空にする: `rm -f .preview-data/manga/*.yml`(ユーザが「消した上で」と言った時のみ)
2. 対象を copy: `cp data/manga.v2/<stem>.yml .preview-data/manga/`(複数可)
3. preview索引再構築: `python scripts/_build-list-index.py .preview-data/manga .preview-data`(~20秒/500頁)
4. masters が変わっていたら同期: `cp data/publishers.yml .preview-data/publishers.yml` 等
   ★**schema(lib/schema.ts)のenum等を変えた時は必ず全masters(demographics/genres/publishers/magazines)をdiff確認**。
   2026-07-14実害: demographics.ymlからother削除時にpreviewミラー未同期→enum backstopがbuildを止め、preview deploy3連続failure(ユーザにエラーメール)
5. `git add .preview-data && git commit && git push`

## NEVER / 罠
- **push後15-20分待つ・追いpush禁止**(前ビルドがcancelされ「変わらない」)
- preview索引はsubset=正常。**public/ の索引(ルート直下3本)を本番索引に差し替えない**(previewが66k化して壊れる)
- UI変更は .preview-data 不要(コード push だけで preview に出る)
- デプロイ確認は Actions REST API か時間経過。反映されない時はビルドcancelを疑う
- 本番R2へはこのskillでは**絶対出さない**(週次蒸留のみ)


## ★previewセット管理 (= 2026-07-06 「元々入っていた漫画が消えない」事故から)
previewは**「いま確認したいセットだけ」を入れる**(混在=確認ノイズ+件数混乱)。
- セット入替: `.preview-data/manga/` を対象ymlだけにする(旧セットは削除可=本番/ステージングに実体がある)
- ドラフト退避場所: `.cache/preorders/drafts/`(未確認の②③④はここ。previewに出すのは確認する分だけ)
- 入替後は必ず: `python scripts/_build-list-index.py .preview-data/manga .preview-data`(索引)
  + previewカレンダー再生成(`_build-calendar.py .preview-data/manga public/calendar <当月>` ★srcはpreview自身=ドラフトも載る)
  + push
- ★カレンダーは二重化済み: public/=preview実在フィルタ版 / data/calendar=本番フル(r2-sync overlayが自動で本番へ)
