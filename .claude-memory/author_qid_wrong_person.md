---
name: author_qid_wrong_person
description: 頁の wikidata_qid(=series.qid=著者QID)は著者1人の頁でも別人が混ざる(抜き取り3/40)。画面の「著者: Wikidata」リンクも同じ誤りを出している。sameAs には使わない
metadata:
  type: project
---

2026-10-22 sameAs 実装時の抜き取り(著者1人×wikidata_qid 有り 40頁を Wikidata ja ラベル/別名と照合): **3/40 が別人**。
- live-machine 松森正 → Q2077268=狩撫麻礼(原作者) / yamamoto-masa-wa-mada-yakyuu-o-shiranai マルヤマ → クロマツテツロウ / choujin-rokku-ibun 太田垣康男 → やまむらはじめ
- 母数: 著者QID有り 44,840頁(うち著者1人 43,301)。7.5% なら数千頁規模。

**Why**: series.qid は MADB 由来の「シリーズの著者QID」で、原作者や別名義・別作家を指すことがある。頁の著者欄(AniList 補正後)と一致する保証がない。
**How to apply**:
- JSON-LD の Person.sameAs には使わない(lib/sameAs.ts は作品の work_wikidata_qid + anilist_id だけ)。
- ⏳ 作品頁下部の「著者: Wikidata Qxx」リンク(app/manga/[slug]/page.tsx)も同じ誤りを画面に出している = 1件のバグ=型([[feedback_one_bug_means_a_class]])。是正は未着手・ユーザに報告済み。
- ★同日の反省: この照合で `_site_gate.check` が wikidata.org の w/api.php を robots 不可と返したのに、表示だけして1リクエスト送った。**check の ok=False は必ず止める**([[site_gate_robots_claude_denied]])。
