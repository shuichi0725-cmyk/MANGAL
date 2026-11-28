---
name: like-button-retired
description: 【⏳後片付け】今日の一冊のいいねボタンを2026-11-28廃止(累計8回・過去ログは開くたび537回GET)。本番反映後に Worker /api/like と KV LIKES を外す
metadata:
  type: project
---

2026-11-28 ユーザ裁定「正直使われてないので廃止」→ commit ad39bf8608。
- 実績: KV LIKES(id 751056d3bdc34407a93da3403b4591bd)の7月〜累計 **8回**(全部1票)。控え = `.cache/like-retire-20261128/`。
- 無駄の正体: ボタン1個ごとに `GET /api/like` = 過去ログ(181日×3=537個)は開くたび537 Worker req+KV read、ホームは3。
- 消したもの: FeaturedDaily/SansedaiDaily/ArchiveClient のボタン・components/LikeButton.tsx・.design-sync の LikeButton・過去ログ説明の♥文・プライバシー「4.いいね機能」・規約「3-4.」(最終更新を2026年11月に)。LikeButtonMock(旧ホーム案 preview 頁用)は残した。

**⏳残り:**
1. 本番反映 = ユーザの「機能蒸留して」か次の週次(トリガー語待ち)。
2. その後 `workers/r2-serve.js` の `/api/like` 分岐と `wrangler-r2.jsonc` の LIKES binding を外し `python scripts/_deploy-worker.py` で出し直す。KV namespace 自体の削除はユーザに確認してから。

**Why:** 使われない機能が問い合わせ回数だけを食っていた。 **How to apply:** 「いいね」を復活させたくなったら1頁1回でまとめて数を取る形にする(1ボタン1GETは再発させない)。[[cloudflare_billing]]
