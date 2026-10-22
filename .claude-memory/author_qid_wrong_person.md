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

## ★2026-10-22 是正完了(4区分・すべて反映+push)
- ①ADD 42頁(a61d722cf): NDL 1巻書誌の役割どおりに原作者/作画者を補完・役割逆転を是正(最強伝説仲根・ニンジャスレイヤー・森村誠一ミステリー等)。
- ②クレジット 218頁243件(32ad5ce28): キャラクター原案/監修等を credits へ。
- ③要裁定 54頁(3ed44e019): 表記ゆれは「NDL と作家表の2源が一致した表記」へ(田淵→田渕・谷ゆきこ→谷ゆき子・ベルネ→BELNE 等)。ゴミ著者名(編著/企画/な/(unknown)/秋田書店)を NDL で置換。アンソロ・判断不能は触らない。
- ④リンク非表示: `data/author-qid-hide.json`(監査が生成・週次step1 `author-qid-hide`)に載る頁(残445)は「著者: Wikidata」を出さない(page.tsx)。
- 道具: `_audit-author-qid.py`(監査+hide一覧)/ `_audit-author-qid-ndl.py`(NDL 1巻・再開可)/ `_audit-author-qid-propose.py`(NDL役割→欄の案)。`_lookup.ndl_live` に creators_raw(役割つき)を追加。
- ⏳ **職業名つき著者名 69件**(あさひ漫画家・鈴木大輔作家・松イラストレーター等)= NDL典拠の同名区別「あさひ (漫画家)」のかっこ落ち。削ると同名別人の著者頁と合流する恐れ=表記方針(かっこ復元等)をユーザ裁定待ち。「ファンタスティック小説家」は本物のペンネーム(除外)。作家表 mangaka にも64件。
