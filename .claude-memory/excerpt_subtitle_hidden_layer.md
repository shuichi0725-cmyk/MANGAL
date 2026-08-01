---
name: excerpt_subtitle_hidden_layer
description: 抜粋本の証拠が楽天副題にしか無い層=promoteの副題dropが構造的に見えない。250頁を3分類済み
metadata: 
  node_type: memory
  type: project
  originSessionId: 9e4afa8a-543a-4b77-966f-1cb6d5cb07d4
  modified: 2026-08-01T04:20:18.550Z
---

★**抜粋本(既刊の再編)が「楽天の副題」にしか現れない層**(2026-08-01 ユーザ発見『Papa told me が分裂している』から型化)。

## 根因(ここが本質)

promote の `DROP_SUBTITLE_PATTERNS` は **頁自身(種2由来)の subtitle** を見る。
ところが抜粋本の決定的証拠が **楽天の subTitle にしか無い**ことがある = **ルールが構造的に発火し得ない**。
→ 語を足せば直る話ではない。**見ている場所が違う**。

実例(是正済): 『Papa told me（春/夏/秋/冬）』副題「シーズンセレクション」= Young you特別企画文庫・集英社・
1996-11に4冊同時刊行の季節別選集。頁側 subtitle は空。結果 **同一4冊セットが3か所に割れ冬は欠落**していた
(春=本編頁に版として吸収 / 夏・秋=独立頁 / 冬=不在)。
是正 = `non-manga-drop.yml` に春夏秋冬の series_key(=SRCの `_skey`)+ `volume-exclude.yml` に本編×4ISBN。
★**dropだけでは本編に吸収済みの巻は抜けない**。両方要る。

## 検出器 `scripts/_audit-excerpt-subtitle.py` → `docs/production-diagnostics/excerpt-subtitle.tsv`

ISBN索引×楽天jsonl2本を走査。初回実測 **250頁/324巻**。3分類:
- **VERSION_MIX 45頁** = 頁の**一部の巻だけ**が抜粋 → 頁は本物、その版だけ混入 = `volume-exclude` 案件。
  ★**最も確度が高く頁を消さないので安全**。例: 男一匹ガキ大将52巻中7巻 / ドラえもん46巻中1巻 /
  エンジェル日誌41巻中2巻 / ドラクエ4コマ劇場22巻中15巻 / ワタシの川原泉5巻中4巻。
- **RECOLLECT 179頁** = 全巻が抜粋 かつ 同著者に桁違いの巻数の頁が在る。同一セットが複数頁に割れている例=
  「金田一少年の事件簿」ベストセレクション7頁 / 手塚治虫セレクション7頁 / 金子節子"家族"傑作選4頁。
  ★**誤検出あり**: 高橋留美子傑作集(Pの悲劇/専務の犬)は**正当な短編集=keep**(MANGALルール「短編集/作品集はkeep」)。
- **REVIEW 26頁** = 再録元を機械特定できない(作家短編集型)。

## 判断の勘所

- ★**自動一括dropは禁止**。ただし当初懸念した**レーベル名型**(叶精作セレクション/クマのプー太郎セレクション/
  カプコン・セレクション/アリスくらぶ未発表セレクション)は **この250には入っていない** =
  あれらは**頁自身の題**に語がある別層(本番索引で33件)。楽天副題側だけを見る本監査は素性が良い。
- 「副題に実在頁の作品名が入るか」も試したが、『スペシャル』『ロマンス』等の短い頁題が誤マッチして**決め手にならない**。
  効いたのは 金田一少年の事件簿(61巻) / あぶさん(107巻) のような**長くて巻数の多い親**のみ。

## 未着手

VERSION_MIX 45頁 / RECOLLECT 179頁 / REVIEW 26頁 の是正は**全部これから**(ユーザ裁定待ち)。
安全な順 = VERSION_MIX(頁を消さない) → RECOLLECT をグループ単位 → REVIEW。

関連 [[konbini_reprint_sweep]] [[non_manga_drop_cleanup]] [[feedback_one_bug_means_a_class]] [[exclusion_priority_policy]]
