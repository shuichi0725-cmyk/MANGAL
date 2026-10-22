---
name: author_qid_wrong_person
description: 頁の wikidata_qid(=series.qid)は頁の著者と別人のことがある。機械照合で 44,840頁中 不一致489(1.1%)+弱一致31。2/3は原作者を指す正当例。Person sameAs には使わない
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

## ★2026-10-22 同日 機械照合(全件)で数字を訂正
- 道具: 作家表 `.cache/db-v2.sqlite` mangaka(qid→name+alt_names)× 頁の authors / original_authors を正規化(NFKC・かな→カナ・旧字)して突合。Wikidata には問い合わせない(robots不可)。
- 結果 44,840頁: 著者欄に一致 43,226 / **原作者欄に一致 1,094** / 弱一致 31 / **不一致 489(1.1%)**。出力 = `docs/production-diagnostics/author-qid-mismatch.tsv`。
- ★抜き取り「3/40別人」は過大だった: live-machine(→狩撫麻礼)と yamamoto-masa…(→クロマツテツロウ)は**原作者欄に居る=正当**。真の別人は超人ロック異聞の1件だけ。
- 不一致489の型: ①頁に原作者が載っていない(FAIRY TAIL 100 YEARS QUEST=真島ヒロ / 半妖の夜叉姫=高橋留美子)= 頁側のデータ欠け ②QIDが無関係な別人(超人ロック異聞→やまむらはじめ / ブラック・ジャック大全集→山田マリエ)。
- Person sameAs を付けない判断は維持(1人著者でもQIDが原作者を指す=作画者Personに付けると誤り)。
