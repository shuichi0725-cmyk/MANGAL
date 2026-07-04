---
name: diff-deploy
description: 差分反映して=変更ページだけ部分ビルド→本番R2へ選択PUT(数分)。コードドリフト時は自動abort→週次蒸留へ誘導
---

# 差分反映して (= 差分ビルドエンジン)

トリガー語: **「差分反映して」**。データ修正(per-case/日次蒸留等)を**本番R2まで数分**で出す軽量ルート。
週次蒸留(フル~3h)との使い分け: **コードが変わったらフル**・データだけなら差分。

## 実行
```
python scripts/_deploy-differential.py --dry     # まず計画(検出結果)を確認
python scripts/_deploy-differential.py           # marker→HEAD の data/manga.v2 差分を自動反映
python scripts/_deploy-differential.py --only a,b,c   # 明示指定(SRC stem)
```
所要 ≈ 部分ビルド数分 + PUT数秒。

## エンジンの安全機構(理解して使う)
1. **コードドリフトガード**: 前回フルビルド以降に app/manga・app/layout.tsx・components/・lib/・next.config.ts・package.json 等が変わっていたら**abort**(exit 4)→「週次蒸留して」が必要。部分ビルドHTMLが参照するチャンクが本番に無い事故の封鎖(buildId固定が前提)
2. **選択同期**: PUTするのは対象頁(manga/<内部slug>.html/.txt)+本番索引3本(ルートキー)のみ。部分ビルドのホーム/一覧はsubsetデータ汚染物=**絶対同期しない**設計
3. 削除ymlはR2 DELETE / 5MB索引ガード / 3000頁超はabort(フル推奨)
4. **edge cache purge**: worker /api/purge(PURGE_TOKEN認証、.env.local R2_PURGE_TOKEN)で対象URL即時失効
5. marker(.cache/prod-deploy-marker.json)を成功時に更新。**週次蒸留完了時は code_commit/data_commit 両方をビルド時commitに更新すること**(weekly-distill skill 参照)

## NEVER
- ドリフトabortを--onlyで回避しようとしない(チャンク欠落で本番白画面になる)
- トリガー無しで自発実行しない(本番ルールは週次と同じ)
- ホーム/一覧/カレンダー等 非mangaファイルを手でPUTしない

## 事後
- 疎通出力(疎通 n/3 OK)を確認・ユーザに 更新頁数/削除数/purge結果 を報告
- 新規頁が index guard(schema検証)で out に無い→abort(exit 7)。先に頁を直す
