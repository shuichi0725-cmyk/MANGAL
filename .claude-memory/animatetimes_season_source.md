---
name: animatetimes-season-source
description: "アニメイトタイムズ季節まとめ=アニメ化コーナー第2情報源(2026-09-01新設): _animatetimes-season-crawl.py。タグ頁は＜＜/＞＞双方向連鎖(2010冬〜自動発見)・原作クレジット(掲載誌つき)抽出・週次step1組込済(fail-soft)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 191494c6-0eb5-4cbb-817a-a2afd70f0a40
  modified: 2026-09-01T06:26:18.177Z
---

2026-09-01 ユーザ持込(animatetimes.com/tag/details.php?id=5947=2026秋)から新設。「今後は週次で変更があるか見て更新」がユーザ指定の運用。

## 機構
- **`scripts/_animatetimes-season-crawl.py`**: 季節まとめタグ頁は ＜＜前季/次季＞＞ の**双方向連鎖リスト**(起点1本で全発見。2010冬 id=10668 が終端)。初回=66季(2010冬〜2027冬)・4,087作。
- 抽出物: 目次(作品名)+**原作クレジット**(「原作：じゅら（講談社「ヤンマガWeb」連載）」形式=掲載誌・出版社つき)+放送形態+スケジュール+再放送判定。
- seed = `data/seeds/animatetimes-seasons.jsonl`(季単位で決定的再生成。**変更履歴はgit diffが台帳**)。HTMLは `.cache/animatetimes/<id>.html`。
- `--weekly` = 最新2季+次季を強制再取得→差分表示→gap TSV再生成。★**fail-soft**(網断でもexit 0=週次を止めない)。**週次step1のSTEPS先頭に組込済**(`animatetimes-weekly`)。
- `--report` = AniList seed(anime-seasons.jsonl)非掲載を `docs/production-diagnostics/animatetimes-season-gap.tsv` へ(MANGA?/non-manga/? を原作クレジットのキーワードで機械分類)。

## AniList側の対
- `_anime-season-harvest.py` に **`--refresh`** 追加(対象季の行をreplace再収穫。旧=季単位skipで凍結)。2026-27再収穫で秋61→73作、2027冬0→35作。→ `_anime-season-join.py` で再結線。
- ★運用: **AniList refresh が主、animatetimes は番人+gap埋め**。gapの大半はAniList refreshで自然合流する(フールナイト/ケロロ軍曹☆/彼方から実証)。残るのは キッズ枠/国内マイナー/表記ズレ/再編集版。

## 初回gap実測(refresh後)
- 非掲載601作(漫画原作候補=MANGA? 122 / 対象外44 / 不明435)。2026秋の真の残り=鳴海の平日/タヌキとキツネ/ガルパンもっとらぶらぶ/紫禁・御猫房/Duel Masters LOSTの5件。
- ★gap TSVの注意: **cross-season偽陽性あり**(進撃完結編/ジョジョ再編集=AniListでは前季entry継続扱い)。裁定は週次の新規増分だけ見ればよい。頁への結線は既存 `anime-season-accepts.jsonl`(via:"animatetimes")。

関連: [[anime_flag_freshness]] [[feedback_one_bug_means_a_class]]
