---
name: display-data-polish-tasks
description: "【残タスク】実機レビューで見つかった表示データの磨き(2026-06-12監査済): 著者重複16頁/synonyms日本語混入3,914頁/月精度日付73%/page-1空kana/未定義genre other"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8f5c881f-9859-490c-b682-bd1969ec515c
---

★2026-06-12 ユーザ実機レビュー(プレビュー=本番コピー)で発覚 → `_audit-author-dupes-and-synonyms.py` で全数化済み。

1. **著者の正規化同名重複 = 16ページのみ**(J.P.ホーガン vs J.P. ホーガン / シュルツの・と. / ★全く同一文字列の二重もあり=merumo-chan/rdb/sensei-no-kaban)。→ ★promoteの著者リスト構築に正規化dedup(空白・中黒・ピリオド除去で同一なら1つ)を1行入れて次回promoteで解消。
2. **synonyms に日本語混入 3,914ページ** — AniList synonymsには日本語別名(1年1組…)・カタカナ音写・中国語(比一厘米更近)が混在。表示ラベル「他言語・別名」を ★「別名(日本語)」と「他言語」に分けるのが筋。題名と同一のものはdrop。表示層のみの修正。
3. **release_date 月精度(日欠落)= 73%**(186,028/253,622)。日を表示する箇所は全て要ガード(0日バグ=見本市コーナーで実害確認→修正済)。★手元資産では埋められないと確認済(2026-06-12): NDLキャッシュ=日精度0(書誌は年月まで)/MADB raw自体が月精度63%=上流仕様/OpenBD・楽天ダンプは未保有。★恒久策=楽天ブックスAPIのsalesDate(日精度・無料)を種4/書影取得と相乗りでバックフィル(18.6万ISBN≈1req/sで52時間、新刊優先の部分実行可、seed化→promote)。それまで月表示が正解。
4. **page-1 / 囿者は懼れず = title_kana空**(c3のkana補完が種3に未反映、pkl 6/03が古い)→ 種3に kana 純粋追加(ページワン/ユウシャワオソレズ)後に再promote。スキーマ検証で空kanaはloader例外になる(プレビューで実証)。
5. **未定義genreキー `other`**(arina-no-tane等)— promoteが master(genres.yml)に無いキーを出力。→ ジャンル品質改善([[genre_quality_improvement]])の監査段で一緒に棚卸し。

いずれも次回promote再生成で反映する類=低リスク。1と4は数行修正で即可能。

## ★【検証の落とし穴・2026-06-13 自戒】成年「漏れ」誤認 = adult-leak-slugs.txt と bash[-f]CRLF
- `.cache/adult-leak-slugs.txt` は**旧・全成年候補リスト=force_adult:False の意図的overrideも含む**。これと v2 を突合すると **override が「漏れ」に誤認**される(13件騒動の正体=12件全部がoverride+cage score0)。
- ★**正しい成年漏れ検査** = `adult_score>=3 ∧ 非override(force_adult:False除外) ∧ v2に在る`。これで真の漏れ=**0**を確認済み。
- ★bash `while read s; [ -f "$s.yml" ]` は **CRLF改行のファイル名で `\r` 混入→偽**(昨夜の leaked=0 偽陽性の元、今夜の grep監査バグも別件)。**検証は python(strip済)で**。bash[-f]ループ禁止。
- 教訓: 「旧リスト∩本番」≠「漏れ」。漏れ=ルール(score≥3∧非override)で判定。検証スクリプトのバグで本番を誤判定しない(promoteを3回無駄に回した反省)。

## ✅成年取りこぼし=修正済み(2026-06-13 夜間パイプラインで本番反映)
- 貧乳日記(板場広志)で発覚 → 全数調査で**2,233頁が無ガード公開**だった(種2のadult_score判定は正常、★消費側=slugパイプラインに成年ゲートが未配線=根因)。
- ★修正= `_slug-apply-prep.py` に **adult_score>=3 hold** を配線(force_adult:False例外尊重)。promote 66,563頁→recluster→ISBN移動→alias再生成→hygiene(成年先alias 1,186掃除)。旧漏えいslug **2,232件全退避を検証済み**。commit 6e09d58d。
- ★名義使い分け確定: **板場広志=一般名義/「板場広し」=成年名義**。MADB creditの「し」がmangaka.csv Q11532585 alt_name経由で「志」に正規化される=**成年名義が一般名義に飲まれる**現象。表示方針(クレジット原文 vs 正規人物名)は**ユーザ裁定待ち**。
- ★新シグナル2つ(月次監査へ追加価値):
  1. **「楽天ブックスに取扱なし」=強い成年シグナル**——楽天Booksは成年コミックを扱わない(=APIに成人フラグが無い理由)。収穫のno_hitは僅か0.7%なので不在は情報量大。貧乳日記=楽天無し✓。収穫キャッシュから無料で全件判定可能。
  2. **作者の名義使い分け**(「◯◯し」型のひらがな成年名義)——Wikipedia裏取りで判定可。
- 関連: [[adult_per_edition_angel]](劇画再販社の取りこぼしと同類=imprintリスト依存の限界)

## ★楽天発売日バックフィル = 全量実行中(2026-06-12 着火・ユーザGO)
- `_rakuten-fill-dates.py --newest-first` を**セッション独立プロセス**で実行中(Start-Process、約53時間、新しい順)。ログ=`.cache/rakuten-fill.log`、キャッシュ=`.cache/rakuten-isbn.jsonl`(全レスポンス保存=書影URL/価格込み、全量~333MB)、seed=`data/seeds/release-date-fill.json`。
- ★進捗確認= `wc -l .cache/rakuten-isbn.jsonl`(目標182,357)。中断/PC再起動→同コマンド再実行で続きから(キャッシュ済はskip)。
- 実測レート(300件テスト): 日埋まり75% / 年月+1月ズレ25%(=**月末発売の奥付ズレ**、MADB=奥付月・楽天=実売日。全件が+1月差) / 楽天に無し0%(outOfStockFlag=1が効く・ユーザ指摘)。
- ★キー=`.env.local`(gitignore)。新仕様=applicationId+accessKey+**Referer/Origin両方**(許可サイト=workers.dev等)。QPS1。
- ★保留(ユーザ「後で考える」): +1月ズレ~4.5万件の扱い=(a)楽天実売日採用(月が変わる・seedオーバーレイで種2不変) or (b)月のまま。レスポンスはキャッシュ済なので**後から決めてもAPI再呼び出し不要**。review=`.cache/rakuten-date-review.tsv`。
- promote反映=release-date-fill.jsonを月精度volumeにのみ適用する結線(未実装、適用時に書く)。
