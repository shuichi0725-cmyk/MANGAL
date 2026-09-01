---
name: animatetimes-season-source
description: "アニメイトタイムズ季節まとめ=アニメ化コーナー第2情報源(2026-09-01新設): _animatetimes-season-crawl.py。タグ頁は＜＜/＞＞双方向連鎖(2010冬〜自動発見)・原作クレジット(掲載誌つき)抽出・週次step1組込済(fail-soft)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 191494c6-0eb5-4cbb-817a-a2afd70f0a40
  modified: 2026-09-01T07:58:04.555Z
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

## ★2026-09-01 「秋37しかない」ユーザ指摘で判明した凍結3層(全て是正済)
1. **view生成が未配線**: `_build-anime-season-view.py`(→data/anime-seasons-view.json=/anime頁の実体)が週次STEPSに無く7/12凍結 → STEPS末尾(list-index後=索引依存)に配線。
2. **AniList seed凍結**: 同上 → `anime-season-refresh`(--latest --refresh=当季+次2季を季単位置換・成功時のみ書換=中断安全)+`anime-season-join --rebuild-map`(★staleマップ事故の型対策)をSTEPSに配線。
3. **★LN原作の構造穴**: AniListは**ラノベもtype=MANGA**で持つ→アニメのrelationが指す"漫画"の実体が原作小説(薬屋99026=日向夏の小説等)=頁が無くhold行き。**薬屋S1〜S3が一度も結線されていなかった**。是正=accepts 11件per-case裁定(薬屋→kusuriya-no-hitorigoto/ダイヤのA→diamond-no-a-act-2/レイアース2026/塩対応→@comic頁/リボ払い【】vs〈〉括弧字種→norm是正済/まほいくrestart→無印コミカライズ=フランチャイズ結線方針)。
## ★2026-09-01後半: 薬屋検死+歴史保留の一括裁定(ユーザ指示で実施済)
- **薬屋検死=完了**: 実体は正しく2頁(無印=倉田三ノ路サンデーGX版22巻/-shino=ねこクラゲBGG版17巻)だがメタ3点交差→是正済: 無印title=『薬屋のひとりごと〜猫猫の後宮謎解き手帳〜』(edition-overrides・楽天確証・U+301C)/aid 99022→**113322**(relink=既存の誤relink行99022を書換)/誌monthly-sunday-gx(**magazines.ymlにキー新設**が必要だった=マスター未登録の訂正はsilent無視される)。-shino=99022確定(confirmed登録)+誌big-gangan。★NDLヨミ副題分は**429で未取得**=宿題(title_kanaは主題分のまま)。
- **左ききのエレンも同病**: 両頁aid109228→リメイク(集英社26巻)=109228確定/原作版(かっぴー単独・ナンバーナイン5巻・公開slug -nifuni=**命名逆転の名残**)=109229relink。★slugサフィックス逆転(薬屋-shino/左きき-nifuni)は**rename保留**=URL波及が大きくユーザ裁定マター。
- **型化**: `scripts/_audit-anilist-id-dup.py`(同一aid複数頁=266組。**A型疑い(2頁×同題)=残21組**が薬屋型の是正worklist/B型=楳図こわい本×13頁等のフランチャイズ扇形はAniList側1エントリで誤りでない)。出力=docs/production-diagnostics/anilist-id-dup.tsv。
- **歴史保留裁定**: adjudicateに`--deep`新設(**LN2ホップ**=NOVELノードのrelationsからコミカライズを辿りa2s直結線 or 題+著者ゲート)→自動97+per-case10(IS→is-2010[姓名順+＜＞字種]/ローゼン2013[U+2010字種]/左きき)+null確定8(SWビジョンズ/しょうたいむ=きりきり舞未収載・show-time頁は吉河美希の同名別作/ポケモン2023/だんでらいおん=空知英秋読切/DARK MOON)。**保留756→627・結線3,405・view3,323作品**。
- 残627の内訳(=anime-season-stays.tsv): **NO_PAGE 304**(参照漫画が本番に無い=新規登録の鉱脈。GATE自衛隊コミカライズ[竿尾悟]/雪女さんと呪いの指輪[ぷぅ崎ぷぅ奈]等)/NO_CAND 44/GATE_FAIL 3(意図的leave: GATE×2・アークザラッド)/relation無し題only 276(リメイク・キッズ・再編集)。
- norm強化: join/adjudicateの剥ぎ字種に 【】〈〉《》<>‐‑ を追加(リボ払い/IS/ローゼンの素通し封じ)。

## ★両載せ方針(2026-09-01 ユーザ裁定・やはり俺型)
- **1アニメに複数コミカライズ頁を載せてよい**: やはり俺の青春ラブコメ=「LNの漫画化(妄言録=佳月玲茅・ビッグガンガン)」と「アニメ化の漫画化(@comic=伊緒直道・サンデーGX)」の並立レアケース。ユーザ「両方載せるべき」。
- 実装= joinのaccepts読みを**同一anime_idの複数行accumulate**に変更(複数slug=複数行出力・view側は(season,slug)dedupで自然対応)。3季×2頁=accepts6行。
- やはり俺も薬屋型だった: 妄言録頁の題から「-妄言録-」欠落=素のLN題と同名→title-matchが**偶然**そこへ着地していた。是正= 題復元+★**kana=…モノローグ**(NDL確証・妄言録の読みは当て字「モノローグ」)+aid75447relink+誌2件(妄言録=big-gangan/@comic=monthly-sunday-gx)。
- ★薬屋(ねこクラゲ版のみ結線中)も両載せにするかは**未裁定**=ユーザに要確認。

## 初回gap実測(refresh後)
- 非掲載601作(漫画原作候補=MANGA? 122 / 対象外44 / 不明435)。2026秋の真の残り=鳴海の平日/タヌキとキツネ/ガルパンもっとらぶらぶ/紫禁・御猫房/Duel Masters LOSTの5件。
- ★gap TSVの注意: **cross-season偽陽性あり**(進撃完結編/ジョジョ再編集=AniListでは前季entry継続扱い)。裁定は週次の新規増分だけ見ればよい。頁への結線は既存 `anime-season-accepts.jsonl`(via:"animatetimes")。

関連: [[anime_flag_freshness]] [[feedback_one_bug_means_a_class]]
