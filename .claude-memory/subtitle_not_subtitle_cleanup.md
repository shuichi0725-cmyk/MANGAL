---
name: subtitle_not_subtitle_cleanup
description: "【是正済2026-09-30】副題欄に「副題でない物」=頁の土台が別の本/作者名レーベル/帯の説明文/○○短編集/THE COMIC/題名の英訳。 3,324→3,141頁。 判断の決まりと道具つき"
metadata:
  node_type: memory
  type: project
  originSessionId: dbe7c616-0000-4bd6-a5d1-d867f19ceb02
  modified: 2026-09-30T06:07:49.309Z
---

ユーザ指摘(こち亀「人生はゲームだよ!の巻」)から、副題のある全3,324頁を型分けして是正(2026-09-30)。

- **副題の決まり方**(promote build_yml): 種3(代表シリーズの key の subtitle)→ 種2 代表行の subtitle → edition-overrides の `subtitle`(空文字=消す・キーは公開slug)。
- **型と判断**(ユーザ「一律には言えない」「判断は任せる」):
  - A 頁の土台(代表 _skey)が別の本 44件 → 39件は副題で別作品を区別する正しい例(ガンダムW ENDLESS WALTZ 等)。 誤り5件だけ消す(こち亀/八男/恥ずかしそうな顔で…/なぎら/フィールドの狼)。
  - B 作者名つきレーベル(ケン月影特選時代劇 等)・B2 帯の説明文(子育てマンガ/フルカラーコミック)・C 本の種類(○○短編集/作品集/セレクション/テーマ別アンソロジー)・F「THE COMIC」/題名のローマ字・英訳/公式英題 → 消す。
  - 残す: 正式な副題、親作品との関係(スピンオフ/『○○』公式アンソロジー/第9部/番外編/外伝)、表紙の英語副題。 D(巻・部の番号)は全部残す。
- 実施: 消す183・直す1(南極漂流記)。 記録= `data/seeds/subtitle-fix-changelog.jsonl`(before/after/backup)。 判断表 artifact https://claude.ai/artifact/KSPDU3vV8XcziFvV8SQDTP
- G(ふつうの副題らしい2,821件)は未着手(説明文が少し混ざるが機械判定は困難)。
- ★こち亀の「その他 編集: ホーム社」= 是正済(2026-09-30): skey-overrides で土台を本編 qid:Q1321466 へ(巻229のまま)。 付け替えで本編の種2に混入していた著者 吉村作治が出てきたので author-role-corrections の remove で除去。 英題は「KochiKame: Tokyo Beat Cops」→「KochiKame」に変わった(本編側の値)。 ★型: 土台の付け替えは著者・英題も入れ替わる=前後の差分を必ず比べる
- ★別件で見つけた型: 2026-08-17 ギャラ型一括是正(edition-canonical)が「巻数が最多の run を主版」にしたため、攻殻機動隊で英語対訳版(Kodansha bilingual comics・掲載対象外)が主版になり原本3冊が3版に割れていた → 原本 KCデラックス 1/1.5/2巻に書き直し済。 canonical 全766本を imprint(bilingual/english/remix/novel/collection box)で掃引して該当は攻殻機動隊だけ。
- 抜粋本(○○セレクション=既刊の寄せ集め)と思われる頁が掲載に残っている(叶精作セレクション/ののちゃんセレクション 等)= 未着手。

関連: [[feedback_one_bug_means_a_class]] [[edition_canonical_mechanism]] [[edition_overrides_key_is_public_slug]]
