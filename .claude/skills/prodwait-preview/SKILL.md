---
name: prodwait-preview
description: 本番待ちテストに出して=前回週次以降の全変更(本番待ち)を.preview-dataへ一括投入し、次の週次で公開される内容を事前レビュー可能にする。1コマンド(_prodwait-to-preview.py)
---

# 本番待ちをテスト環境へ (= 2026-07-10 確立・script化)

トリガー語: **「本番待ちテストに出して」「本番待ち全部テストへ」**(「次の週次の分を見たい」も同義)。
週次蒸留の**事前レビュー**が目的: 次回「週次蒸留して」で公開される変更を、先にpreviewで全部確認できる状態にする。

## やること (1コマンド)
```
python scripts/_prodwait-to-preview.py --dry-run   # まず件数と日別内訳(何も書かない)
python scripts/_prodwait-to-preview.py --push      # 投入+索引+カレンダー+commit+push
```
内蔵(scriptが面倒を見る・手で再実装しない):
1. cutoff=markerのcommit日時 → mtimeで本番待ち頁を列挙
2. **mtime汚染ガード**: >20,000頁=フルpromote(全消し復旧等)の汚染と判断してabort → 実変更の始点を調べ `--since YYYY-MM-DD`(2026-07-06全消し復旧で実際に踏んだ)
3. **preview専用ドラフト温存**(manga.v2に無い確認待ち②③④は消えない)
4. masters6本の差分同期(漏れ=新出版社キー頁404の罠)
5. 索引再構築+**skip診断は内部slugで**(ファイル名≠slugのslug-override頁を誤検出しない)+原因分類。`genre:other`=既知クラス(本番索引も同様にskip)=報告のみで止めない
6. previewカレンダー再生成(src=preview自身)

## NEVER / 罠
- **push後15-20分・追いpush禁止**(test-deployと同じ)
- 本番R2へは出さない(公開は「週次蒸留して」のみ)
- 週次実行後はmarkerが進むので、次回からcutoffは自動で正しくなる(--sinceは汚染時だけ)
- previewが千頁級になる=正常(1,218頁で実証済)。「セットを絞りたい」時は skill test-deploy(per-case投入)を使う

## 関連
- per-case/少数セットの投入=skill test-deploy / 公開=skill weekly-distill / ドラフト昇格=skill productionize-drafts
