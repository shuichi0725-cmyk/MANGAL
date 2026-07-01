---
name: genre-quality-improvement
description: 【残タスク・ユーザ合意済】ジャンル付与の品質改善。現状=AI付与(未検証56%)+genres_anilist並存+野球サッカーのみ突合。監査→語彙マッピング→1系統統合→Wikipediaスイープの4段
metadata: 
  node_type: memory
  type: project
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
---

★2026-06-11(深夜) ユーザと合意した「後でやる」タスク。ユーザ評価=「改善しないとまずい」。
タクソノミーは増やさない(むやみに増やす気はない=ユーザ明言)。**付与の信頼性**を直す。

## ★【最重要・サイトの存在理由・2026-06-13 ユーザ表明】カテゴリ=未知との出会いの唯一の道
- ★ユーザの動機=「AIでアフィサイト作れるか」+「漫画を探しやすいサイトが無い、作りたい」。**discovery(発見)が価値の本体、アフィは収益手段**(両者は良発見→滞在→アフィで一致)。
- ★**既知探索(作者名/題名を知ってる)は既存検索で足りる=差別化にならない。未知だけど出会えるのはカテゴリだけ=このサイト唯一無二の価値**。
- ★帰結=**ジャンル品質は「残タスク」でなく中核**。誤ジャンル=発見が壊れる=サイトが目的を果たさない(実害最大)。今夜の成年漏れ修正後に**最優先級へ格上げ**(ユーザ指示)。
- ★richnessはタクソノミー増やさず出す: 既存facet掛け合わせ(ジャンル×分野×年代×巻数×連載状態)+ AniList themes/tags(異世界/復讐/タイムリープ等、既にデータ有=ジャンル分類でなく「気分・題材」軸、出すかは要ユーザ判断)。

## 現状の弱点(4つ)
1. AniListマッチ(~44%)以外の56%は**AI付与のみ=一度も検証されていない**(フリガナ/slugは検証済なのにジャンルだけ素通し)。誤ジャンル=作品が発見されない実害。
2. `genres`(AI/種3)と`genres_anilist`(enrich)の**二系統並存**。語彙も別(AniListは英語圏アニメ基準)。フィルターがどちらを信じるか未定義。
3. 人手検証済みソース=**Wikipediaカテゴリが野球/サッカーでしか未活用**(fantasy1,166/SF820/action383が調査済み待機=[[feature_roadmap_post_db]]参照)。
4. 1〜4個制約・主/副の重み無し。

## ★監査結果(2026-06-13 `_audit-genre-quality.py`、全66,582頁)
- ジャンル0件=0(全頁≥1)。但し **'other'のみ 1,095頁**(=discovery不可視。正体=総集編/メモリアルセレクション/介護のお仕事 等の編集本・実用書・obscure長尾、AniListで救えるのは4頁のみ)。'other'+実ジャンル=367(冗長)。
- **50%(33,169頁)がAI単独**(AniList照合無し)=未検証。
- ★**「AI⇄AniList一致率100%」は見せかけ**: promoteが genres=UNION(AI, AniList)で **AIを検証せず追加するだけ**。だからAIノイズが残る。
- ★**drama/comedy/romance 過剰付与**(各28k/25k/25k≈全頁38%)=generic希釈でdiscovery弱る。
- AI単独の具体キー: school6.3k/historical5.3k/isekai3k/essay1.4k/gourmet700/bl461/samurai298/yokai229…(未検証だが具体的)。

## ★精度最大化の設計(2026-06-13 ユーザ裁定)= 「AniList+Wiki信頼、AIは単独不採用」
- ジャンル採用条件: **AniListが言う ∨ Wikiが言う ∨ (AIが言い AniList/Wikiも言う)**。AIは票を足すだけ・単独でジャンルを作らない。信頼源がある頁ではAIノイズを落とす(drama過剰が消える)。信頼源ゼロの長尾だけAI fallback(低信頼)。
- ★**AniListは genres(広い18)+ tags/themes(細かい) の両方**を使う。★**themeはv3 dumpに完全保有**(Boys' Love9.5k/School4.3k/Isekai/Food/Youkai/Historical/Idol/Detective/Iyashikei 等51,570件)。v2にthemeが無いのは**enrichが旧dump+Demographicしか拾っていなかった**ため=**v3から再抽出するだけ(再dump不要)**。theme→master保守マップ(明白のみ、Super Power/Swordplay/War/Reincarnation/Yuriは曖昧で除外)。
- ★**Wikipediaカテゴリ=全採用**(スポーツも非スポーツも)。但し**スポーツ小分類は野球/サッカー以外作らない**(全部sportsに寄せ=既存方針)。戦争漫画88の受け皿(war新設 or historical)だけ要裁定。
- AniList∩Wiki重複=dedup(片方)。
- ★【最終決定 2026-06-13】(1)**warを新設**(genres.yml に追加・戦争漫画の受け皿。theme"War"高rank→war も採用可)。(2)★**長尾(信頼源ゼロ~40%)=AI暫定を残し「低信頼」内部マーク**(`genres_provisional: true`等)。信頼源(AniList/Wiki/将来の第三源)が来たら上書き、蒸留で埋まる余地を残す。= discoveryで不可視にしない+精度向上の道を開く。
- ★実験で裏付け済み(`_audit-genre-quality`+v3 theme): AIを外しAniList(genres+themes)のみにすると drama28k→10k/comedy25k→12k/romance25k→14k(AI乱発が消える)、themeが+bl1,328/+school855/+isekai134/+gourmet168/+yokai130 等を回収。被覆=AniListで33,276頁、残50%はWiki+AI fallback。
- ★実装TODO: (i)genres.yml に war (ii)`_build-anilist-enrich-map.py` を v3 dump 由来に変え theme tags も抽出(T2M保守マップ) (iii)Wikipediaカテゴリ全収穫→genre-wiki seed(野球/サッカー突合方式の拡張) (iv)promote genre マージを「trusted優先(AniList genres+themes ∪ Wiki)、AIは trusted空のみfallback+provisional印」に書換 (v)再promote。
- 実験手順=「AIを外し AniList(genres+themes)だけで再構築→被覆を見る→Wiki追加→長尾を判断」(ユーザ「一回振ってみて考える」)。
- ★構造的限界: AniList50%+Wiki(人気~5千記事・多くAniListと重複)の和でも**長尾~40-45%は信頼源が世に存在しない**(Wiki記事もAniListも無い)→ ここはAI暫定か'other'で割り切る(精度を上げる手が無い)。

## 改善4段(順序どおり)
1. **現状監査**(読み取りのみ): ジャンル0件数/ソース別カバレッジ/AI付与⇄AniListの一致率を測る
2. **語彙マッピング表**: AniList genres/tags → MANGALキー(~50行、一度きり)
3. **多数決統合**: Wikipedia∧AniList∧AIの2ソース一致=確定、不一致=レビュー(フリガナ3ソース方式の再利用)→ genresを1系統に
4. **Wikipediaカテゴリスイープ**: fantasy/SF/action等をseed化(野球方式=実証済)。★戦争漫画88件の受け皿キー裁定が必要(war新設 or historical)

## ★ジャンル=3源の合議(adultと同型・2026-06-13 ユーザ確認)
- 源は**AI生成(種3) / Wikipediaカテゴリ(Category:ジャンル別の漫画) / AniList genres** の3つ。adultの多源合議と同じ構造。
- ★**3源とも腐る=定期リフレッシュ必須**([[monthly_intake_reality]] の sources-state.yml に入れる): AI=新作未付与+未検証残/Wiki=編集者が新作をカテゴリに足す→再スクレイプ/AniList=再dump。**鮮度は最古の源で決まる**。
- 品質=3源の多数決/マージ(上記4段)。★「タグは増やさない」不変=Wikiは既存25キーを多くの作品に貼る源(新キー追加でない)。genre_other 1,462=master外キー→既存に寄せる。

## 備考
- サブタグ独立3軸基準(件数突出/境界明確/検索ニーズ、現状baseball/soccerのみ)は維持。
- seed+promote再生成で完結=URL影響ゼロ、公開後でも安全。ただしフィルターUIの信頼性に直結するので公開前推奨。
