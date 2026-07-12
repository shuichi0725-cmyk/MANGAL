---
name: kobo-review-preview-set
description: トリガー「kobo見直ししたい」= Kobo補完302作の装丁確認セットをpreviewに復元する手順(slug一覧はgit保存済み)
metadata: 
  node_type: memory
  type: project
  originSessionId: 3fa9d18f-c403-43f6-b43c-0df5a60e7ccc
---

ユーザ裁定 2026-07-13: Kobo補完302作の装丁確認は中断して他作業を進める。**「kobo見直ししたい」と言われたら同じテスト環境を復元する**。

## 復元手順(数分)
```
rm -f .preview-data/manga/*.yml
for s in $(cat data/seeds/preview-sets/kobo-review-2026-07-13.txt); do cp "data/manga.v2/$s.yml" .preview-data/manga/; done
python scripts/_build-list-index.py .preview-data/manga .preview-data
git add .preview-data && git commit -m "kobo見直しセット復元(302作)" && git push
```
- slug一覧の正 = **data/seeds/preview-sets/kobo-review-2026-07-13.txt**(git追跡・302行)
- 復元時は data/manga.v2 から最新をコピー(=その後のper-case修正も反映された状態で見られる)
- push後15-20分でmangal-preview反映

## このセットの中身/文脈
- Kobo補完バッチ1+2の採用302作(同巻割り×全欠け充足ゲート、covers.jsonl.gzに~1,600巻分追記済み)
- 頁内書影重複(関東平野型)の是正済み22頁を含む([[inflight-state-2026-07-12]])
- 確認の目的=装丁NG(電子と紙の装丁が違いすぎる作品)の目視拾い出し。NGは作品名指定→covers seedから個別除去(backup=.cache/covers-bak-*)
- 巻数タイ3頁(prime-rose/ai-hitotsu-akiko/love-senka)は「新しい版に残す」ヒューリスティックで裁定済み=ユーザが逆を望めば付け替え
