---
name: feedback-daily-distill-no-drafts-quiet
description: ★日次蒸留=ドラフト廃止(新作もゲートを通ればその日に本番化)/作業中の途中経過を報告しない/最終報告は「結果」から書く(前置き禁止)。2026-10-08 ユーザ裁定
metadata:
  type: feedback
---

2026-10-08、日次蒸留の報告を受けたユーザの裁定(3点)。

1. **ドラフト廃止**: 予約の新作(②③④)を「previewで確認待ちのドラフト」にしない。出荷前レビュー(`_preorder-review.py` exit 0)と
   生成後チェックリストを通したら、その日のうちに `_preorder-productionize.py --keep-preview` で本番化(preorder-pages+manga.v2+索引)。
   preview は当日分の閲覧用に残す(確認待ちではない)。旧B裁定「②③④は必ずpreview先行」を置き換える。
2. **途中経過を報告しない**: 作業中に「今〜しています」を書かない(この日は数十回書いて「多い」と言われた)。
3. **最終報告は「結果」から**: 「日次蒸留が終わりました」「pushは最後に1回」「テスト環境に反映されるまで15〜20分」「本番公開は週次」等の前置きは不要。

**Why:** 確認待ちのドラフトはユーザの手間を増やすだけで、品質はゲートと検査で守れている。報告は量が多いと読まれない。
**How to apply:** daily-distill skill の手順10.9(本番化)と報告形式に焼いた。ゲート(レビュー/チェックリスト)を飛ばして本番化しないこと
=人の確認が無くなった分、検査が唯一の守り。判断が要る点だけ最後に短く並べる。
関連 [[feedback_report_in_japanese]] [[feedback_plain_status_text]] [[feedback_user_directive_supremacy]]
