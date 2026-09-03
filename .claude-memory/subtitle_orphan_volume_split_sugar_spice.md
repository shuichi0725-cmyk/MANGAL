---
name: subtitle-orphan-volume-split-sugar-spice
description: 【型・検出器あり・3段適用済 2026-09-03】Sugar&Spice型=巻題を題としてMADBが単独登録→種2別sid→本編頁から末尾巻が欠ける。_audit-subtitle-orphan-volume.py で全DB掃引→override固定頁4/別sid195巻/取込もれ643巻を適用。残=REVIEW一覧(レーベル和英表記違い等)
metadata: 
  node_type: memory
  type: project
  originSessionId: f8fa63b4-3ce7-45e1-b2ab-f3f4fbab02f4
  modified: 2026-09-03T04:51:50.910Z
---

**型 (2026-09-03 ユーザ発見 sugar-spice)**: 各巻に固有の巻題を持つシリーズ(Sugar & Spice=全巻ジャズ標準曲題)で、MADBが
17/19/20巻を巻題「Somethin' stupid」等を**題として**別MADB-IDで登録し、種2のクラスタキー(著者+題)が別sid(number=0/1,
is_extra=1)に落とした。本編頁は「17巻欠け+18巻で終わり」に見えた(完結・全20巻)。是正=種4結線+4巻の後刷り日付是正。

**検出器 = `scripts/_audit-subtitle-orphan-volume.py`**(楽天キャッシュ1パス24秒。CLAUDE.md月次サニティ登録済):
副題/題の「親題+巻番号」→既存頁と照合→本番に無いISBNを 巻状態×種2(SPLIT/SAME_SID/ABSENT)×tier×一致×疑 で列挙。
第2部= edition-overrides(editions固定)頁の続巻取りこぼし(種2駆動)。

**2026-09-03 ユーザ「1から順番にやって」で3段を適用**:
1. 第2部(override固定): フェルマーの料理8/聖女に嘘は通じない6/壁抜けバグ12/狼男だよ2 を override に追記。
   見送り= 魔法科2頁(実体はよんこま編4-7=step2で別頁へ)/うちの3姉妹17-19(傑作選=除外が正)/嶋二(同人誌選集)/花警察・鬼太郎(多版別件)。
2. SPLIT(別sidに眠る): 機械証拠(版種keep/レーベル一致/発売日順/出版者記号一致/題完全一致)でAUTO162+手動採択→**195巻を種4で62頁へ**。
   ★同クラスタ掃引を追加(採択sidの兄弟巻で楽天キャッシュに無かったもの=CODE:BREAKER 15-26 は19だけ楽天に在った)。
   ★頁化済み変種: 特別編1巻『ハニー・ヴァイオレット』/2巻『レコンキスタ』が単巻頁で存在→種4で特別編1-7を揃え page-dedup drop→301。
   ★くらべて、けみして: 種2が新潮文庫1巻を通常版number=1で登録→原本1巻が同番号ガードで弾かれ、override で通常版1-2/文庫1に分離。
   見送り= 0巻(cluster)/文庫だけの頁に原版1冊(fanshii-dance)/プリキュア版混在/将太の寿司18(原シリーズ巻)/アニメKC/supo-chan(旧キャッシュ誤記録)。
3. ABSENT(真の取込もれ): 6ゲート(standard版/レーベル整合/発売日順/同番号無し/ISBN未在/bind/override・canonical外)で
   **AUTO 643巻/413頁 → volumes-supplement-auto.yml (source: rakuten-title-tail)**。REVIEW 516巻/325頁は
   `docs/production-diagnostics/subtitle-orphan-volume-review.tsv`(理由列つき。最多=レーベル和英表記違い416=alias表で救える)。

**判定の学び**: ①出版者記号は桁数表(2〜7桁)で切る(先頭7桁固定はKADOKAWA/講談社で題番号を巻き込み別社扱い) ②楽天の旧キャッシュ
(rakuten-isbn.jsonl)は誤記録あり=delta優先 ③種2の版種は当てにならない(新潮文庫がstandard) ④SAME_SIDの内訳=真の0巻(表示方針
マター)/page-dedup残骸/override固定/MADB誤番号 ⑤override が editions を持たなければ種4は効く(is-2010は題だけのoverride)。

**次**: REVIEW一覧の消化(レーベルalias表→再ゲート)、0巻表示方針、フリガナ等は別件。
[[volume_split_merge]] [[series_fragmentation_rootcause]] [[feedback_one_bug_means_a_class]] [[harvest_match_mechanism_applied]]
