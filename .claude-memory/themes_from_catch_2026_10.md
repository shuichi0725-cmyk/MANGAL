---
name: themes-from-catch-2026-10
description: "キャッチ文から要素(themes)を付ける作業(2026-10-01)。第1段キーワード18要素1,899作は反映済、第2段AI判定は検定報告後GO待ち"
metadata:
  node_type: memory
  type: project
  originSessionId: 2e2403af-9d7d-426e-a4c8-1c6d346610e9
  modified: 2026-09-30T22:13:47.046Z
---

道具 `scripts/_themes-from-catch.py` (measure / stage1 / apply <stage> [--go])。台帳 `docs/production-diagnostics/themes-from-catch-changelog.jsonl`、作業物 `.cache/themes-from-catch/`(sample.json=検定300作・sample-answers.json)。

- 2026-10-01 数え直し: 書影+キャッチ39,272 / 要素0 21,217 / 要素あり18,055。第1段(精度70%以上・支持15以上の18要素)で1,899作付与→反映後の要素0=19,318。
- 第2段AI検定(300作・親が逐次): 適合率62%/再現率21%。要素別は報告済。**GO待ち=適用していない**。
- 罠: 索引themesは「ジャンル名と同じ要素を畳む」ので 異世界/学園/野球/ボーイズラブ は正解データに出ない(精度1%に見える偽の低精度)。要素seedのキーはSRC slug(slug-overrides逆引き)。キーワード「取り合い」は「手を取り合い」で三角関係に誤爆→除去。

**Why:** 羅針盤のテーマ糸が要素0の作品で効かない。 **How to apply:** 第2段/ジャンル(段4)を再開する時はこの道具の apply を流用。[[onevol_catch_themes_enrich_2026_10]]

## 続報(2026-10-01)
- 第1段はOpus点検で47件取消済(台帳 stage1-revert)。**第1段 apply は再実行禁止**。キーワード一致は括弧内(「」『』)を除外するよう道具に追加。
- 第2段 試行(stage2-pilot): 対象=適合率70%以上の16要素のみ・要素0からランダム1,000作を親が逐次判定→**45作・のべ48件**(0個955作)。basis=キャッチ中の語句を台帳へ。反映済。残り約1.8万作とジャンル追加(手順4)は未着手=GO待ち。
- 手順4 ジャンル追加 試行(genre-pilot, 2026-10-01): 対象=汎用ジャンルのみ&(provisional or 空)=457作(全数)。検定200作 適合率90%(採用=fantasy/action/sports系/romcom/sci-fi/romance/mystery/adventure/historical/horror/mecha/gag/yokai/music/bl/mahou-shoujo/gourmet、n<3は不採用)。付与35作/0個422作。台帳 genres-from-catch-changelog.jsonl。**kibando は genre-append 済だが反映未実施**(再生成でISBN 9784253174770が消える減少検出でpush停止・--allow-loss未使用)。残りは進めない=終了。
- あらすじ→キャッチ 試行(catch-syn-pilot, 2026-10-01): 対象=書影あり・キャッチ無し・synopsis有=1,592作(Opus数1,595、差3=seedに既存)。200作を逐次判定→**65作に書込・135作見送り**(材料不足102=短編集の収録紹介のみ等/範囲外33=アンソロジー・成年向け・映画コミカライズ・画集)。混入疑い0。台帳 catch-from-synopsis-changelog.jsonl。作業物 .cache/catch-syn/。残り約1,400作は未着手=GO待ち。キーは seed=SRC slug / 索引=公開slug。
- あらすじ→キャッチ 本番(stage=catch-syn, 2026-10-01): 残り1,392作を逐次処理→**349作に書込・反映済**(材料不足844/成年向け117/範囲外75/混入疑い7)。試行65作と合算414作。混入疑い7=261青い空(安孫子)/315 Odds+1(自転車vsバイク)/416・1192ヤマト(聖悠紀)/599魔界高校白書(心理士)/860茄子/908日本沈没第二部。#679 Cloth roadは巻説明が別作品(書いたが要確認)。キャッチ無し残り18,960作は synopsis 空=材料なし。作業物 .cache/catch-syn/(e/a*.py=書いた文,e/s*.py=見送り理由)。
- Kobo紹介文→キャッチ 試行(catch-kobo-pilot, 2026-10-01): 材料= .cache/kobo-caption/harvest.jsonl の strict(40字以上・販売注記除去・最小巻)。対象8,549頁(キャッチ無し)から200作を逐次→**150作書込・反映済**(材料不足25/成年向け19/範囲外5/後の巻1/混入疑い0)。台帳 catch-from-kobo-changelog.jsonl。作業物 .cache/catch-kobo/。残り約8,350頁は未着手=GO待ち。
