---
name: element-assign
description: 要素付与して <作品>=要素収集(element-harvest)の束から、ジャンル・要素の「付与案」を作る。AniListは票で機械的に仕分け、語彙の語は材料から機械で拾い、Sonnetが芯・在る・違うを判定、根拠は道具が一字一句で検査。案を作るだけで本番には書かない。どのモデルが運転してもよい(判定のSonnetは道具が直接呼ぶ)。試行中 v0.10(2026-10-09)
---

# 要素付与 (= トリガー「要素付与して <作品名>」)

## これは何か

要素収集(skill `element-harvest`)が作った束(`.cache/element-harvest/<stem>/material.json`)から、
その作品に付けるジャンル・要素の**付与案**を作る。

- `run` / `check` は**案を作るだけ**。本番データ(`data/manga.v2` / seed / 索引)には書かない。書くのは `apply`(下の「本番へ書く」。ユーザの Go が要る・Opus の仕事)。
- 試金石 = 『やはり俺の青春ラブコメはまちがっている。』(2頁・反映済み)。出し方の線は 2026-10-09 にユーザ裁定で確定(確かな出どころの語だけ・強い順に最大10・材料が薄い作品は埋めない・作品ごとの裁定は求めない)。30作の全自動の試し(trial30)の結果は `data/element-harvest/trial30-summary.tsv`。

## やること (1コマンド)

```
python scripts/_exists.py --title <題の一部>            # stem を引く
python scripts/_element-assign.py run <stem>            # 候補づくり → Sonnet が判定 → 道具が検査 → 付与案
python scripts/_element-assign.py show <stem>           # 付与案を読む
```

- 束が無いと言われたら、先に要素収集を `done` まで終わらせる(skill `element-harvest`)。
- 終わったら `run` の出力(「== 要素付与の案 ==」以下)を**そのまま貼って**報告する。自分の言葉で言い換えない。
- 台帳を commit+push: `git add data/element-harvest && git commit -m "要素付与(案): <題> (<版>)" && git push`

## 役割分担 (★AIは読んで選ぶだけ)

| 誰 | すること |
|---|---|
| 道具 | AniList のタグを票で仕分ける / 信頼源のジャンルを決める / 語彙の語を材料から一字一句で拾って候補にする / 根拠の検査 / 付与案と台帳 |
| Sonnet(道具が直接呼ぶ) | 候補ごとに **芯・在る・違う** を判定し、材料の一節を根拠に抜く。語彙に在る別の語、新しい語も根拠つきで挙げる |
| 運転者(どのモデルでも) | コマンドを打って、出力をそのまま報告するだけ。判定に口を出さない |

★判定の Sonnet は `claude -p` を**道具なし・短いシステム文で1回**呼ぶ(会話の土台を読ませない)。運転者のセッションに材料を読ませて判定させない(高くつく)。

## 付与案の読み方

| 欄 | 意味 |
|---|---|
| ジャンル「足す案(信頼源)」 | 原作小説・アニメ・自分の AniList ジャンルにあるもの。汎用ジャンル(ドラマ・コメディ・恋愛・日常・アクション)はここでしか足さない |
| 表に出す案(強い順に最大10語) | AniList の票が線以上(主題60・人物70・舞台70)か、材料が「主軸だ」と述べている語のうち、**語彙と訳が在る語**を強い順に10まで(v0.8)。強さ = ユーザ裁定 > AniList と材料が一致 > AniList だけ > 材料だけ。★**サイトに出すのはこの欄だけ**(2026-10-09 ユーザ裁定「全部つけると多すぎる」) |
| 隠して持つ(4欄) | サイトには出さず記録だけ(羅針盤の「近さ」にだけ使う隠し要素にする案 = ユーザ発案)。①上限であふれた語 ②**強いのに語彙か訳が無くて出せない語(= 語ごとの裁定の候補)** ③ネタバレ印・**ありふれた語**(多くの作品に当てはまり間違いではない語 = 語ごとのユーザ裁定 `rulings.yml` の `word_rulings`。v0.10)・出さない決まりの語 ④作中に在るが中心でない語(AniList の票40以上、材料で主要人物の属性 等)。★**ネタバレ印の語は票が高くても出さない**(2026-10-09 ユーザ裁定「いらない」)。ただし AniList の印は粗いので、**その語を持つエントリの半分以上に印が在る時だけ**有効(三角関係は関連7件中1件だけ → 表に出す) |
| 使わなかった AniList の票 | 登録者の少ない関連作・おまけ映像にしか無い票(v0.9。収集の道具 v0.5 が「本筋」のエントリだけに絞る = skill `element-harvest`)。付与にも隠し要素にも使わない |
| 新しい語の候補 | 今の語彙に無い語。**付けずに** `data/element-harvest/word-candidates.jsonl` に貯め、何作にも出た語だけユーザが採否を決める |
| 付けない | 語は材料に出るが根拠にならないと Sonnet が判定したもの(別の語の一部・あだ名・脇役1人の性質・冗談など) |
| 道具が弾いた答え | 根拠の文が材料に一字一句で無い等、検査で落ちたもの |

印: 〔表示できる語〕= 表示はできるが今まで AI が選べなかった語 / 〔新しい語〕/(ネタバレ印)= AniList の印、または展開の材料だけが根拠 / 読み替え案・仮の訳 = 訳がユーザ裁定待ち。

## 本番へ書く (= Opus の仕事。ユーザの Go が要る)

付与案の「表に出す案」と「足すジャンル」だけを seed へ書き、targeted 反映でテスト環境に出す。運転者(Haiku/Sonnet)はここをやらない。

```
python scripts/_element-assign.py apply <stem> --go "<ユーザのGo発話の引用>"   # seed に足す(頁はまだ変わらない)
python scripts/_reflect-targeted.py --only <stem,...> --commit-only -m "…"     # 頁と索引へ反映(skill reflect-targeted)
cp data/manga.v2/<stem>.yml .preview-data/manga/                                # テスト環境の対象に入れる(未投入の頁)
python scripts/_build-list-index.py .preview-data/manga .preview-data --update <stem,...>
git add … && git commit && git push                                             # ★push は最後に1回だけ(追いpush禁止)
```

- `apply` が書く先: 要素 = `data/seeds/tags-enrich-2425.json`(対訳表で表示できる AniList タグは**英名**、それ以外は**和名**)/ ジャンル = `data/seeds/genre-append.yml`(source=`element-assign:<版>`)/ 記録 = `data/seeds/element-assign-changelog.jsonl`(Go の引用・前後・退避先つき)。
- ★**新しい語は `apply` が断る**。語彙(`data/seeds/wamei-tags.yml` の `allow`)に足すのはユーザ裁定で、足した語だけが付く。
- ★**AniList タグの訳(`data/seeds/tag-i18n.yml`)は足してよい**(2026-10-09 ユーザ裁定「たす今後も足して良い。」= 毎回聞かなくてよい)。迷いのない訳だけ、末尾に日付と裁定の引用を書いて純粋追加(`genre: ""`)。訳し方に幅がある語は急がない。
- ★語彙(和名タグ表・訳表)を変えたら、**テスト環境の写し `.preview-data/seeds/` も同じにする**(頁の要素欄は写しを読む。`_reflect-targeted.py` が反映のたびに差を写す。2026-10-09 に「ぼっち」がテスト環境の頁にだけ出ない漏れを実踏)。
- ★**語ごとのユーザ裁定 = `rulings.yml` の `word_rulings`**(`hide_common` = ありふれた語は表に出さず隠して持つ)。語を足す時は、足す語を見せて裁定を受けてから。
- ★**隠して持つ語は羅針盤の「隠し要素」になる**(画面に出さず、近さの点数にだけ使う。2026-10-09 ユーザ発案)。`apply` が `data/seeds/element-hidden.json`(公開slug → 鍵。AniList のタグは `ani:<英名>`、材料の語は和名。語彙に無い新しい語は入れない)へ同時に書く。
  もう apply 済みの頁に後から持たせる時 = `python scripts/_element-assign.py hidden <stem> --go "…"`(頁の表示は変えない)。
  書いたら `python scripts/_build-compass-hidden.py`(約12秒)で配るファイル `public/data/compass-hidden.v1.json` を作り直して一緒に commit。仕組みと数字は memory [[compass_hidden_elements]]。
- ★`apply` は**足すだけ**。前から頁に付いている要素(AniList 由来など)は消せない(消す口は未実装)。裁定と食い違う既存の語が残る時は、黙って済ませず報告する(俺ガイル@comic の「三角関係」で実踏)。
- 取り消し: 足した行を seed から消して反映し直す(記録の `revert` を見る)。
- ★**作品ごとのユーザ裁定 = `data/element-harvest/rulings.yml`**(`show` = 表に出す語 / `hide` = 出さない語。ユーザの発話を `quote` にそのまま書く)。道具は付与案の仕分け(票の線・ネタバレ印)より**これを優先**する。ユーザが「この語は出して/要らない」と言ったら、ここに書いて `check <stem>` → `apply` → 反映。**Claude の判断で書き足さない**。

## NEVER

- (運転者は)付与案を本番データや seed に書き写さない。`apply`・反映・デプロイをしない。
- 付与案に自分の判断で語を足さない・消さない(直すのは道具か指示文。それは Opus の仕事)。
- 「■ 中断」が出たら止めて報告する。繰り返し叩かない。

## Opus 側 (試行の点検)

1. 付与案(`.cache/element-harvest/<stem>/assign/assign-proposal.md`)と Sonnet の生の答え(`assign-answer.json`)を読む。
2. 見る点: 「違う」にすべき語が 芯・在る に入っていないか / 根拠の文がその語を本当に支えているか(人名・あだ名・題名・たとえ話でないか)/ 同じ意味の語が2つ出ていないか / 新しい語が作品固有の名でないか。
3. 直す場所: 判定の決まり = `_element-assign.py` の `RULES`(★この作品の語を例に書かない。v0.1 で例に書いた2語だけが新しい語として返った)/ 線や訳 = 冒頭の方針の定数 / 語彙 = 対訳表・和名タグ(ユーザ裁定)。
4. 指示文を直したら `VERSION` を上げて `run` し直す(`--no-record` を付けると台帳に書かない)。
5. ユーザ裁定待ちの方針(票の線・ネタバレ印の扱い・訳の読み替え・新しい語の採否・ジャンル上限)と試行の数字は memory [[element_harvest_pillar_state]]。

## 関連

- 前段 = skill `element-harvest` / 語彙 = `data/genres.yml`・`data/seeds/tag-i18n.yml`・`data/seeds/wamei-tags.yml`・`data/enrich-out-2026-07/theme-vocab-ja.json`
- 土台を読ませない呼び方の実測 = memory [[lean_headless_claude_call]]
