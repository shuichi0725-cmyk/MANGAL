---
name: daily-distill
description: 日次蒸留 — 2本立て: A=楽天予約ハーベスト(未来の新刊・カレンダーの餌)/B=NDL新着回収(過去の納本)。+NDL照合キュー消化+カレンダー更新。トリガー「日次蒸留して」。
---

# 日次蒸留 (= 2026-07-06 全面改訂: 楽天予約が主柱に)

**2本立て**: A=楽天予約ハーベスト(未来〜当月の新刊。カレンダー/新刊棚の唯一の未来供給源) /
B=NDL新着回収(納本済み過去分)。毎日でなくてよい(間隔が空いても窓が自動で広がり取りこぼさない)。
理想運用: 日次蒸留して→(previewで)確認→週次蒸留して=週1本番更新。

## NEVER(禁止) ★2026-07-09 ハードニング: 下記4つは今日全部踏んだ実害。飛ばすな

- ★**フルharvest処理禁止=必ず増加分だけ**: `preorders-latest.jsonl` を丸ごとclassifyするな。**必ず `preorders-prev.jsonl` との差分(新ISBN=fresh)に絞ってから**classify/生成する(下A0)。フル処理=昨日以前のbacklogを全部「新規」に水増しする(実害2934件)。
- ★**過去ドラフト再カウント禁止**: 増加分(ISBN fresh)でも、**前回previewドラフト化したが未promoteの作品**が後続巻の新ISBNで再登場する。`.cache/preorders/drafts*`(過去draft)の**題(base正規化)と突合して除外**してから生成(下A0)。[[daily_distill_classifier_gate]]。
- ★**ヨミ捏造禁止(厳守)**: title_kana=**楽天titleKanaのみ**。楽天に無ければ**題流用/生成読み/巻番号混入で捏造するな→hold**(NDL照合キュー行き)。**title_kanaに漢字が1字でも入る=捏造=即hold**(gen-midfillはゲート済、生成物は必ず漢字混入チェック)。
- ★**中間pushしない=最後に1回だけpush**(2026-07-20 ユーザ裁定): 日次蒸留は①続巻反映も索引もBも、途中は**全部ローカルcommit止め**(`_reflect-targeted.py --commit-only`/索引は`git commit`のみ)。全工程完了後に**`git push`を1回だけ**。中間pushを重ねると Cloudflare Pages のpreviewビルドが次々cancelされ「反映されない/36のまま」になる([[reflect_protocol_fast]] NEVER=追いpush禁止)。
- **429/throttle即中断**(NDL・楽天とも1.1〜1.3s/req厳守。リトライ連打禁止)。
- **捏造禁止**: ヨミ/著者/genreを推測で埋めない。ヨミ=楽天仮確定+NDL照合キュー(下記)が正規ルート。
- **単巻先行登録禁止**: 途中巻でページ無し(④)は全巻回収が成立した作品だけドラフト化。
- **②③④は必ずpreview先行**(B裁定)。ユーザ確認GOなしに本番化しない。**previewは"今回のみ"**(増加分−過去draft−捏造kana)に絞る。ユーザは「前回見た」に敏感で正確=水増しを即見抜く。
  ★2026-08-11 機械化: 手順4.5の `_preorder-preview-swap.py` が**previewの現掲示物を黙って退場**させる(=追加でなく入れ替え。ユーザ裁定「何も言わないでも入れ替えを行ってほしい」)。飛ばすと前回分が混ざる。
  ★2026-08-15 是正(ユーザ指摘「入れ替えるようにskillしたはずだけどなってない?」): 旧実装は退場条件を
  「日次ドラフトである AND data/manga.v2 に居ない」にしていたため**手作業でpreviewに入れた確認用コピーが1頁も退場せず**、
  2026-08-14に巻抜けセット155頁が残ったまま日次102頁が足され preview 257頁で新旧が混ざった。
  現在は**由来を問わず全部退場**(例外= 復元手段が無い頁[安全弁] と `data/seeds/preview-keep.txt` に明示した頁のみ)。
- ★**1回のAPIで全フィールド捕捉**(2026-07-09 ユーザ指摘 [[acquire_all_obtainable_info]]): 楽天API/harvestは書影だけでなく **itemCaption(あらすじ=genre/catch/synopsis元)/booksGenreId/itemPrice/subTitle/affiliateUrl** を返す。**書影だけ取って捨てるな**。captionを`_preorder_draft.rakuten_caption`に保存→genre(master32・provisional)/catch/synopsisを生成(caption有れば発売前でも付く)。書影のためにAPIを叩くなら同じ応答からcaptionも必ず取る。
- genre=closed vocabulary(master32)のみ+provisional。catch/synopsis=skill enrich-catch-synopsis の規律。
- ★★**「壊れているから」で deny しない**(2026-08-08 実害=熱愛プリンス全68巻を誤って消した)。
  deny してよいのは ①**書籍でない**(isbn13が978/979始まりでない特典・グッズ) ②**掲載scope外**(画集/アメコミ翻訳/非漫画)
  ③**実体が別頁へ移った** の3つだけ。**同一発売日/publisher未登録/索引skip は「異常」ではなく「未整備」**=
  調べれば理由がある(同日一斉刊行・マスター追加漏れ)。壊れているだけのものは**保留**にして台帳に残す。
  [[never_delete_because_broken]]
- ★**改善は即興でなくskill/scriptに焼く**: 実行中に穴を見つけたら手動で継ぎ足すな。scriptにゲート追加→commitしてから進む(即興は次回消える+報告が水増しでブレる)。
- ★**出荷前レビュー(`_preorder-review.py`)を通すまでpush禁止**(2026-07-20 実害=86ドラフト中49件をユーザ指摘後に総直し。
  検知は`slug-*-pending.tsv`に出ていたのに簿を消化せずpushした=プロセス漏れ。判断力でなく決定的ワークリストで塞ぐ):
  - **exit 0(ブロッキング0)を確認してから手順13のpush**。件数チェックでなく**ゲート**(exit 1=push禁止)。
  - `docs/production-diagnostics/preorder-review.tsv` の各行をAIが1行ずつ裁定:
    - **CONTINUATION**(最優先)=既存作の続巻を誤ってドラフト化。`_lookup.py --creator`で新シリーズ(第二章/龍を継ぐ男型=別頁が正)か
      続巻(千年狐十四/KATANA23型=種4転送)かを確認→種4転送 or 「新シリーズなので正」でpending該当行削除。
      ★続巻確定時は**NDLで全巻を見る**(Xinobi型 2026-08-22: 新刊4巻の裏で既存頁に2-3巻も欠けていた=1巻だけ転送して終わらない)。
      ★同名別コミカライズ(佐々木とピーちゃん型)は別頁が正=衝突slugは`-姓+年`suffix。
    - **SLUG_MUSH**(2026-08-23新設・ブロッキング)=無分割塊(ハイフン無しrun15字超)/78字超の語中切り。
      根因=短縮前のフル楽天題からslug生成。**題(短縮後)の意味の切れ目でrename**(本編句まで。副題は捨てる:
      isekai-rakuraku-mujintou-life / fushi-no-dungeon-master 型)。誤読(星間=seikan)・辞書語(exorcist/daily-mission/try)も同時に正す。
    - **NONMANGA**(最優先)=図鑑/写真集/再編集本。deny台帳(preorder-deny.jsonl)へ+ドラフト除去(preview+drafts両方)。
    - **MISREAD**=漢字誤読疑い。題を読んでslug綴りが読みと合うか確認。誤りはrename(preview+drafts両方)、
      正しければ`slug-gate-pending.tsv`の該当行を消す(nidaime/shinzou型=既に正=偽陽性)。
    - **KATA_UNCONV**=未変換カタカナ。辞書語(マージャン→mahjong型)はrename+`katakana-english.yml`に追加、
      造語/固有名(ヒトナー/オダロク=英語綴り無しが正)は`slug-katakana-pending.tsv`の該当行を消す。
    - **LONG_CHECK**(情報・非ブロッキング)=長題。語境界cut済だが意味の切れ目か1件だけ目視。
  - rename時は**preview(.preview-data/manga)とドラフト保管(.cache/preorders/drafts)の両方**を付け替える(衝突チェック=本番stem+alias+preview)。

## ★毎日の実行手順 (= runbook・この順で回す。2026-07-09 確立。ツール把握用)

前提: `git status` clean。楽天/NDL認証env有り。

| # | やること | ツール(コマンド) |
|---|---|---|
| 1 | 予約harvest | `python scripts/_rakuten-preorder-harvest.py` |
| 2 | ★**増加分に絞る**(必須) | `python scripts/_preorder-increment.py`  ← prev差分+過去draft除外。飛ばすと水増し |
| 3 | 分類 | `python scripts/_preorder-classify.py` |
| 4 | ①続巻→種4+反映 | `python scripts/_preorder-apply-zokkan.py` → `python scripts/_reflect-targeted.py --only <touched> --commit-only` ★**--push禁止**=commit止め(最後にまとめて1回push) |
| 4.5 | ★**preview入れ替え**(2026-08-11 ユーザ裁定=「追加でなく黙って入れ替え」/ 2026-08-15 範囲是正) | `python scripts/_preorder-preview-swap.py` ← **preview の現掲示物を由来を問わず全部退場**(日次ドラフト・手作業の確認用コピーとも)。データは消えない= ドラフトは `.cache/preorders/drafts/`、手作業コピーは `data/manga.v2` が実体。残したいセットは `data/seeds/preview-keep.txt` に1行1slugで明示。**確認を取らず毎回実行** |
| 5 | ②③新作ドラフト | `python scripts/_preorder-gen-preview.py new1a` ; `new1b` |
| 6 | ④途中巻ドラフト | `python scripts/_preorder-gen-midfill.py` |
| 7 | genre付与(★worksheet化 2026-07-10) | `python scripts/_preorder-genre-worksheet.py --emit` → AIがworksheetのgenres[]にmaster32キー記入(確信なければ空) → `--apply`(master32外=abort・純粋追加・provisional自動)。caption無し頁は先に `_preorder-capture-captions.py` |
| 8 | Cヨミ照合 | `python scripts/_verify-kana-pending.py --limit 200` |
| 9 | **検査**(下記チェックリスト) | 欠け>0なら原因調査 |
| 10 | ★**prev確定**(処理完了の宣言) | `python scripts/_preorder-increment.py --commit-prev` ← full→prev昇格。**これ以外の方法でprevを触るな**。飛ばすと次回差分が壊れる |
| 10.5 | ★**出荷前レビュー(ゲート)** | `python scripts/_preorder-review.py` ← **exit 0 まで push禁止**。下記で各行裁定 |
| 10.6 | ★**発売日ドリフト**(2026-09-04新設・すてごろブッチ型) | `python scripts/_audit-preorder-date-drift.py` → `python scripts/_apply-preorder-date-drift.py`(dry-run で保留理由を読む) → `--apply` → `_reflect-targeted.py --only $(cat .cache/preorder-date-drift-stems.txt \| tr '\n' ',') --commit-only`。★**予約巻は後から発売日が動く**(延期/前倒し)。この日のharvestが最新スナップショットなので**ここで突合するのが一番安い**(live不要)。適用は**楽天とNDLが一致した行だけ**=±1日の「奥付日 vs 店頭日」は保留に落ちる(変更しないのが正解)。日付が動いた月は `_build-calendar.py data/manga.v2 data/calendar <当月>` も回す(暦は本番フル版) |
| 10.7 | ★**保留頁の自動再訪**(2026-08-24新設③) | `python scripts/_preorder-refresh-held.py --limit 30` ← demographic/caption待ちで索引保留の予約由来頁を楽天再照会で埋める(捏造なし=返った時だけ)。touchedが出たら `_reflect-targeted.py --only <touched> --commit-only` |
| 10.8 | ★**レビューシート生成→ユーザへ**(2026-08-24新設①) | `python scripts/_gen-review-sheet.py` → `.cache/review-sheet.html` をユーザに送付(SendUserFile render)。書影/出版社/slug/ジャンル/再録疑いを一覧色付け=1頁ずつ開かせない |
| 11 | 索引+暦(**commit止め**) | `python scripts/_build-list-index.py .preview-data/manga .preview-data` ; `python scripts/_build-calendar.py .preview-data/manga public/calendar <当月>` ; `git add .preview-data public/calendar && git commit`(★**pushしない**) |
| 12 | B NDL新着(任意) | `python scripts/_distill_daily.py --discover`→`--plan`→`--emit` ★**push前に済ませる**(Bもpreviewドラフトを作る=最後の1pushに同梱) |
| 13 | ★**最後に1回だけpush** | `git push` ← 全工程(①〜B)完了後にここで**初めてpush**。Pagesビルドは1回だけ発火=追いpush回避([[reflect_protocol_fast]] NEVER)。中間で絶対pushしない |

### ★生成後チェックリスト (= 全部2026-07-09に実際踏んだ罠。毎回数える)
- □ **kana純カタカナ**(漢字/ひらがな0)。楽天ヨミ無し/汚染は**捏造せずhold**が効いているか
- □ **slug=辞書装置**(`_slug_kana_lib`経由)・英語綴り(summer-blend等)。pykakasi再発明でない。英語出ない語は`katakana-english.yml`に追加
- □ **全巻に発売日**(回収先行巻=種2 db-v2から引く)+**書影**(実URL=harvest/covers seed/楽天API。★構築禁止)
- □ **genre**=captionからprovisional・master32のみ(捏造なら空)
- □ **作者kana**=楽天authorKana由来 or 空(捏造なし。漢字混入0を確認)
- □ **preview=今回のみ**(増加分・前回draft混入0・捏造kana hold済。★手順4.5のswap実行済みか=`--list`で退場漏れ0を確認可。
  ★**頁数がその日のドラフト数と一致するか**を必ず数える= 一致しなければ前回分が残っている[2026-08-14実害])
- □ ★**本番待ちper-caseを見たい時は preview に手で足さない**= 日次のswapが毎回流す。skill `prodwait-preview`(「本番待ちテストに出して」)で
  週次前に一括投入するのが正規ルート。日次をまたいで残したい確認セットだけ `data/seeds/preview-keep.txt` に積む。
- □ ★**発売日ドリフト(手順10.6)の芯が消化済み**(2026-09-04新設)。★**「もう発売済のはずなのに書影が仮のまま」は
  延期のサイン**= 書影を疑う前に発売日を疑う。`preorder-date-drift.tsv` の POSTPONED/ADVANCED が芯、
  `-review.tsv` の「奥付日vs店頭日」は**変更しないのが正解**(NDL=こちらの値)。NOT_LISTED(楽天からも消えた)は人が裁定
- □ **索引skip 0**(Zod検証で落ちる頁=検索に載るが404)
- □ **索引衛生** `python scripts/_audit-index-hygiene.py data`(cover slim全行/スキーマ/head/alt。2026-07-14新設ゲート)
- □ **`--commit-prev` 実行済み**(処理完了後のみ。件数確認だけの日は実行しない)
- □ ★**slug-gate-pending.tsv を確認**(2026-07-14内蔵のヨミ一致ゲート: 装置が題を誤読した疑い
  =剣聖ken-hijiri型がここに落ちる。行があれば当該slugを手裁定=ヨミ基準で正す。
  裸巻数読み尾(アカルイミライニ型)は`clean_kana(base付き)`が自動トリム済=チェック不要)
- □ ★**診断簿を掃除してから読む** `python scripts/_prune-slug-diag-logs.py --apply`
  (kana-mismatch / slug-gate-pending / slug-katakana-pending は**追記専用**で、掃除しないと
   膨らんで誰も読まなくなる= skill が警告している形骸化そのもの。2026-09-05 実測で **676行中94%が残骸**
   [重複 / そのslugが本番にもう無い / 今のゲートでは一致]だった → 掃除して 38行。
   書き手側にも追記dedupを入れたので、以後は「本番に無いslug」の掃除が主目的。
   ★消すのは「もう存在しない・既知の偽陽性・解決済み」だけで、実修正が要る行は残る)
- □ ★**slug-katakana-pending.tsv を確認**(2026-07-14: 辞書に掛からずカナ転写したカタカナ語
  =「自動で決められない箇所」の簿記。lolly/blue-bird-reader型はここから拾ってユーザ報告→裁定。
  和製語(ママ/クズ/メシ等)はヘボンで正しい=報告不要。外来語らしきもの・公式英字がありそうな物だけ
  Web裏取り(公式英字>ユーザ裁定>ヘボン維持)。処理済み行は消してよい。一括監査=`_audit-slug-katakana.py <dir>`)
- □ ★**題末尾の巻表示掃引**(2026-07-14 サムライトルーパー型: 題が「〜　上」等で終わる新draftは
  題/kana(ジョウ)/romaji(jou)から剥離し `volumes[0].volume_label` へ退避。
  検出=`re.search(r"([\s　]+|[\s　]*[（(])(上|下|中|前編|後編)[)）]?$", title)` を新規分に掛ける
  =裸型「〜 上」と括弧型「〜（上）」の両方(ムジナの城型 2026-07-14に8件))
- □ ★**ISBNでない商品コードを弾く**(2026-08-08 ユーザ指摘「魔王軍はホワイト企業」): 楽天は**購入特典のしおり/
  ポスター/巻セット**も同じAPIで返し、それらの `isbn` は **978/979 で始まらない楽天独自コード**(2100015137963型)。
  題も「【特典】…(しおり)」「…1〜5巻セット」になる。**`isbn13` が 978/979 始まりでない巻を持つドラフトは非漫画**
  として deny(preorder-deny.jsonl)+ドラフト除去。★本編は既に頁がある(=続巻扱い)ことが多いので、
  弾いた後に `_exists.py --isbn`(★先に `--build`)で本編頁の巻構成を確認する。
- □ ★**「Vol.N」/「仮」を含む新規題は再編集本疑い**(むこうぶちVol.5仮型 2026-07-14:
  コンビニ廉価のテーマ別再編集シリーズが仮題のせいで1巻新規としてすり抜けた。
  `_lookup.py --title "題 Vol"` で同型Vol.1..N-1の存在と副題(テーマ名)を確認→該当なら drop。
  本編が本番に既存(_exists.py --title)なのに別レーベルVol.Nが来た場合は特に疑う)

### ★2026-08-08 の生成器修正(4件・手作業の再発を止めた)
1. **漢字誤読 → ヨミ基点で自動是正**。根因= slug を**漢字題から**作り、確定ヨミ(楽天titleKana)は
   事後照合に使うだけだった。ゲートが不一致を出したら**ヨミ基点で作り直す**ようにした
   (堕天使→datenshi / 魔導士→madoushi / 聖巡→seijun / 日の名残り→hi-no-nagori 等が自動で直る)。
   語境界は**題側のひらがな助詞**の並びでヨミを割って復元し、は=wa/を=o/へ=e に正規化。
   ★**題にラテン文字がある時は自動採用しない**(「THE COMIC」→ザコミック→zakomikku と劣化するため)。
   その場合は候補を `docs/production-diagnostics/slug-kana-candidate.tsv` に併記=人が1行で裁ける。
2. **題末尾の巻表示**: `(全N)` `(N巻)` `(全N巻)` `（上）` `空白+上下中前後編` を剥がすよう拡張。
   ★**ラテン/記号直後の裸数字は剥がさない**(「THE COMIC10」を取りたいが同じ規則が「ワイルド7」を壊す=検討して却下)。
   曖昧な数字は簿に回す。既存の「かな漢字直後の裸数字」も**ワイルド7型を壊す既知の穴**(今回は触らない)。
3. **CONTINUATION検出の強化**: 既存頁との突合に**強い正規化**(全半角記号/THE COMIC/＠COMIC/コミカライズ/
   末尾巻数を吸収)を追加。姫騎士がクラスメート！ THE COMIC10 が既存『姫騎士がクラスメート!』全9巻の
   **10巻**なのに新作扱いで別頁化されていた型を機械で捕まえる。
   同名別作品の偽陽性は `data/seeds/continuation-false-positive.tsv` に登録して再フラグを止める。
4. **ISBNでない商品コードを弾く**(上のチェックリスト参照)。

### ★2026-09-02 の恒久修正(日次蒸留で実踏した6型・全部scriptに焼いた)
1. **改名頁の続巻が「series_key逆引き不可」で保留**: 分類器の `_slug` は公開slug、manga.v2 のファイル名は SRC stem。
   `_preorder-apply-zokkan.py` に slug-overrides.yml の pub2stem 逆引きを追加(氷舞のアウフギーサー2 等4件)。touched も SRC stem で出す。
2. **特装版/限定版が続巻として種4に入り、通常版と同巻番号で二重化**(ゆるゆり25/大室家9/コナン109/アルスラーン25 等**11件**が本番に出ていた):
   分類器が `SPECIAL_ED`(特装版|限定版|小冊子付|しおり付|ポストカード…)を**続巻でも skip**、apply-zokkan に**同巻番号既在ゲート**
   (頁standard版 or 種4-auto に同番号があれば保留。既在が特装版entryなら通常版で置換=退役記帳)。既存11件は退役済
   (`volumes-supplement-retire-changelog.jsonl` op=retire_special_edition・backup付き)。★種4-autoの退役は seed lint が
   「台帳縮小」で反映を止める → `_check-seeds.py --allow-shrink volumes-supplement-auto.yml` で確認→seed commit→反映。
3. **副題付き続巻が ex_mid に漏れる**(ちいかわ なんか小さくてかわいいやつ(9)/捨てられた妃 めでたく…4/半グレ-六本木…-16/
   漫画 ゆうえんち -バキ外伝-11): 分類器③次マッチ=頁題が harvest題の**先頭セグメント**に一致+著者overlap+★巻連続(頁max+1..+3)。
   スピンオフ(僕ヤバ ラブコメディが始まらない2)は巻連続で落ちて ex_mid(全巻回収)に残る=正。
   併せて norm に引用符“”(チェリー勇者と“せい”なる剣10)、著者末尾♂♀(たかし♂)の正規化。
4. **分離器の巻数取り逃し**: 「〜副題〜9」(閉じ記号直後の数字=確定) / 「GOLD RUSH　8」(英字語+空白+数字=suspect)。
   それまで「裸数字末尾=続巻疑い」skip に落ちて**簿にも出ず消えていた**→ reason付き skip を triage に出すようにした。
5. **slug生成不可(装置が自動で決められない題)の通し方**: `data/seeds/preorder-slug-manual.tsv`(isbn13→slug→根拠)に人がヨミ基準で
   裁いた slug を置き、`_preorder-gen-preview.py new1a --isbn <isbn,...>` / `_preorder-gen-midfill.py --isbn …` で**保留分だけ**再生成。
   ★`--isbn` 無しの再実行は既生成ドラフトと衝突して suffix 付き二重ドラフトを作るので禁止。
6. **rename の同期は script**: `python scripts/_preorder-rename-draft.py old=new ...`(preview/drafts/made lists/kana-pending/pending簿の5点同期
   +衝突チェック+来歴 rename-log.jsonl)。手で mv しない。
7. **著者=出版社名ゲート**(みにくい小鳥の婚約(1)=楽天 author「小学館」): 楽天は著者未登録時に出版社名を返す。生成器が hold
   (著者不明を捏造しない)。★本番にも同型が9頁ある(NHKダーウィンが来た!/放課後ペダル/クローズ海賊版 等)=別途是正待ち。
8. **手塚マンガで憲法九条を読む** = 既刊短編7編の再編集本(解説付き)=抜粋本規則で deny。

### ★2026-09-04 の恒久修正(実踏8型・全部scriptに焼いた)

1. **分類器 ④次マッチ(緩和正規化)+著者=出版社placeholder免除**: 続巻4件が「途中巻/非漫画」に落ち頁が更新されていなかった。
   ・廻天のアルバス9 = 楽天author「小学館」placeholderで著者overlapが取れない
   ・ハンドレッドノート**ー**ホークアイズ**ー**4 = 本番は「-ホークアイズ-」(ASCIIハイフン)、楽天は長音符ーをダッシュに使う
   ・Fate/stay night **[**Heaven's Feel**]**12 = 本番は〈〉、楽天は[]
   ・転生王女は今日も旗を叩き折る12 = 本番題にルビ注記「旗**(フラグ)**」
   緩和キーは畳みが強いので ★**候補1件**+★**巻連続(頁max+1..+3)**を必須ゲートにする(新規衝突177種は全て自動不採用)。
2. ★**上下巻ペアの1頁統合を実装**(下 A2-2 に規定はあったが**実装がどこにも無かった**。grepヒット0)。
   『ひみつー佐世保事件で妹を喪ったぼくの話ー』(同日発売)が 上=new1b(1巻の新作) / 下=ex_mid(全巻回収不成立) に割れていた。
   増加分の**全class**から兄弟を集め volumes 1..N + `volume_label`(上巻/下巻)に組む。上(前編)が揃わなければ従来どおり保留。
3. ★**分離器が漢数字の巻表示を読めなかった**: 『寿司銀捕物帖（三巻）』が vol=None で **新作1巻** に分類されていた
   (=単巻先行登録の事故そのもの)。(一巻)(第三巻)(全五巻)十一〜九十九 を読む規則を `_preorder_title_lib` に追加。
4. **題末尾の巻表示**: `_VOL_TAIL` に **上巻/下巻/中巻** と **漢数字+巻** を追加(#介護ロボットが…（上巻）型)。
5. **ラテン混じり題でkana末尾の巻数読みが剥がれない**: 「Code;OSINT コードオシント 1」→kana「コードオシント**イチ**」。
   `kana_tail_trim` に「題のカタカナだけを抜いた文字列との**完全一致**」を第2照合先として追加。
6. **kanaの波ダッシュ**: ヨミ欄でカナに挟まれた〜/～は長音符なので ー に正規化(と〜ふのあわこ→トーフノアワコ→`toofu-no-awako`)。
7. ★**ヨミ一致ゲートが「辞書の英語化」を誤検出**: katakana-english.yml に ロボット:robot を足した途端 slug生成不可(hold)に落ちた。
   janome がヨミ側の長いカタカナ連を1語(未知語)扱いし辞書変換が効かず、題側=robot / ヨミ側=robotto で不一致に見えていた。
   → 題に**実在する**辞書見出し語だけをヨミ側にも切り出して比べ直す第2読みを追加(`_kana_dict_reading`)。
   ★この関数は**左から最長一致で1回だけ**走査すること。単純な replace 繰り返しだと部分一致キーが内側を割る
   (シャーロックホームズ → シャー+ロック+ホーム+ズ)。
8. ★**評論/研究書ゲート**(`_preorder_draft_lib.looks_like_criticism`): 『アトム』と『火の鳥』手塚SFの世界(前川輝光/鳥影社)が
   新作1巻としてドラフト化された。題は漫画作品名を含み `_SCOPE_OUT` を素通りする。決め手は**caption の語彙**。
   判定= ①コミックレーベル(seriesName)が空 ②評論語(読み解く/論じ/考察/作品解説/入門の決定版…) ③caption が自分を漫画と名乗らない、のAND。
   ★③が要る: ②だけだと「グルメコミックエッセイ」「夕暮宇宙船短編集(あとがき/解説付き)」など**本物の漫画**を2件拾った。
   実測=楽天予約2,823件中3件のみ発火し全て真陽性。**deny でなく hold**(人が裁定)。
9. **発売日ドリフトの保留理由が日数差を見ていなかった**: 61日の延期が ±1日の仕様差22件と同じラベル
   「奥付日vs店頭日=変更しない」で保留表に埋もれていた。±2日以内だけ仕様差、それ超は
   「★NDL未更新の疑い= 人が裁定」に分ける(自動適用はしない)。
   併せて `_apply-preorder-date-drift.py` の stems 出力に**末尾改行**を付けた
   (無いと読み手が最終行を落とす= 2026-09-04 に30頁中29頁しか preview へ入らなかった実害)。

★辞書追加は**本番の綴り慣行で裏取りしてから**入れる(索引を数える)。実測:
addict 4件/adikuto 1件・robot 47/robotto 2・deep 28/diipu 0・abyss 13/abisu 0・sherlock 11/shaarokku 0・holmes 28/0・sketch 13/0。

### ★今日の学び(runbookに焼いた恒久修正・再発防止)
- 増加分ゲート(過去draft再カウント防止) / kana捏造hold / slug辞書装置 / 発売日=種2引き当て / 書影=実URL(構築禁止) / 1API全フィールド捕捉(caption→genre) / preview今回のみ。

## A0. ★増加分ゲート (= 2026-07-09 必須。ここを飛ばすと全部水増しになる)

harvest後・classify前に**必ず**増加分に絞る。`_preorder-increment.py`(下記機能を1本化):
```
python scripts/_preorder-increment.py   # ①latest-prev差分(新ISBN) ②過去draft題を除外 → classified.json は増加分のみ
```
機能(script化して飛ばせなくする):
1. **fresh = preorders-latest − preorders-prev**(ISBN差分)。prev無しなら「初回=全部fresh」と明示ログ。
2. **過去draft除外**: `.cache/preorders/drafts*` + `data/seeds/preorder-pages/` の題(base正規化)集合と突合し、**既ドラフト作は増加分から落とす**。
3. 出力: `classified.json`(or 前段のfresh jsonl)を増加分のみに絞る + 件数ログ「fresh N / 過去draft除外 M / 実処理 K」。
※このscriptが無ければ手動で同等を実施し、**その場でscript化してcommit**(NEVER最終項)。

## A. 楽天予約パイプライン (= 主柱)

```
1. python scripts/_rakuten-preorder-harvest.py        # 6サブジャンル×発売日降順→未来〜当月全量(数分)
1b. python scripts/_preorder-increment.py             # ★A0=増加分に絞る(prev差分+過去draft除外)。飛ばすな
2. python scripts/_preorder-classify.py               # ①続巻/②新作作者既知/③新作作者新規/④途中巻頁無し/skip
   → ★生成後、title_kanaに漢字含むドラフト=捏造→hold(NEVER)。全巻回収の先行巻ヨミも楽天由来のみ。
3. python scripts/_preorder-apply-zokkan.py           # ①→種4自動追加(ゲート:slug実在/巻番号/series_key逆引き)
   → promote --only <touched> → reflect --only <touched> --commit-only  ★**--push禁止**(①も中間はcommit止め・最後の1pushに同梱)
4. python scripts/_preorder-gen-preview.py new1a      # ②ドラフト生成(→.preview-data)
   python scripts/_preorder-gen-preview.py new1b      # ③(著者マスタ新規はヨミ=楽天仮)
   python scripts/_preorder-gen-midfill.py            # ④(キャッシュ全巻回収成立分のみ)
   → preview索引再構築 → ★**commit止め(pushしない)** → 全工程完了後に**1回だけpush** → ★ユーザ確認
5. 確認GO後: python scripts/_preorder-promote-drafts.py --class new1a 等
   → data/seeds/preorder-pages/(git恒久保管庫=promote合流結線済・フルpromoteで消えない)
   → data/manga.v2(即公開) → reflect --only <last-promoted> --push
   ※種2への正式INSERTは月次蒸留時。それまでpreorder-pagesが恒久化を担う。
```
- 分類の保留/不備は `docs/production-diagnostics/preorder-triage.tsv` に自動記録。
- ②③生成時に**キャッチ/詳細/ジャンルも埋める**なら skill enrich-catch-synopsis を続けて実行。

## A2. ②③品質ゲート (= 2026-07-06 実戦で確立。previewに出す前に必ず)

**楽天予約の題は信用しない**。入口=★**タイトル分離器 `scripts/_preorder_title_lib.py`**(題/巻数/副題の三分解。
末尾(N)・第N巻・N巻・中間(N)副題型[三ツ星レシピ]・裸数字・その六かな数詞・上下巻・直結数字はsuspect格下げ[サンダー3保護/鬼平128照合])。
分類器/生成器は結線済み=剥がさない。previewに出したら以下を検査(全部実際に踏んだ混入):

1. **続巻の誤新作化**: 分離器vol≥2 or suspect≥2 → 既存頁一意一致+巻連続(max+1..+3)なら種4 / 一致なし=1巻から無い→保留(単巻先行登録禁止)
2. **上下巻**: ペア=1頁統合(上=v1,下=v2・題から上下除去) / 下巻単独=保留(上巻の全巻回収要)
3. **scope外**: 特装/限定版・アンソロ・傑作選/再編・コンビニ本(★題でなくimprint判定=集英社リミックス/プラチナコミックス/Gコミックス)・画集/ガイド/BOX・雑誌/別冊・アメコミ翻訳・(仮)・★**分冊版/合本**(2026-08-31 ユーザ裁定=非掲載が基本。下C参照)
4. **Zodスキーマ検証**: `loadAllManga`でskip 0確認(year_ended/authors.role/demographic enum=shounen/shoujo…。索引はPython製で検証なし=「検索に載るが404」の既知クラス)
5. **slug品質**: ★**正規装置 `_slug_kana_lib.make_slug` を使う**(2026-07-09 ユーザ指摘=pykakasi再発明禁止)。janome分かち+**`data/seeds/katakana-english.yml` 貪欲辞書変換**(サマーブレンド→summer-blend/デュエルマスターズ→duel-masters/ビューティーポップ→beauty-pop)+ヘボン(は=wa/長音保持)。**英語綴りが出ない語は辞書に追加して強化**(カタカナ→英単語)。`_preorder_draft_lib.make_slug`は装置に委譲済。rename時は**made lists+rakuten-kana-pending+staging三点同期**
6. 作者の法人クレジット(Magica Quartet/バンダイナムコ型)は既存DB慣行どおり正当=触らない
7. ★**全巻に発売日+書影が付いているか検査**(2026-07-09 ユーザ指摘): 特に④midfillの**回収先行巻**は要注意=
   ・発売日: 予約巻はharvest、**回収巻は種2(db-v2 volumes.release_date)から引く**(捨てるな)。種2未収載のみ空(NDL/enrichで後補完)。
   ・書影: ★**構築禁止**(2026-07-09 実害=cabinetパス/サフィックス`_1_2`/拡張子`.jpg|.gif`はISBNから推測不可・404)。
     **実URLのみ**= harvest cover(予約巻) → `covers.jsonl.gz`(covers seed) → **楽天API `largeImageUrl`**(`real_cover()`) の順。無ければNone(cover harvest/enrichで後補完)。
   ・gen-preview/gen-midfill は `_preorder_draft_lib.real_cover()` で結線済み。生成後 `release_date`/`cover_url` の欠け+**構築URL(`/cabinet/{isbn[-4:-1]}/`)混入**を必ず数える(>0なら原因調査)。

## B. NDL新着回収 (= 従来コア)

```
1. python scripts/_distill_daily.py --discover   # 窓=★前回実行月の前月〜当月(動的・取りこぼさない)
2. python scripts/_distill_daily.py --plan       # 差分レポート+カーソル更新
3. 新規掲載可→ai-todo.jsonl記入→ --emit(preview先行) ※詳細は従来手順(下の旧手順参照)
```
- NDLはNDC付与が納本後のため**未来は取れない**(未来=Aの楽天が担当)。

## C. NDL照合キュー消化 (= A裁定「漏れない仕組み」・毎回実行)

```
python scripts/_verify-kana-pending.py --limit 200
```
- `rakuten-kana-pending.jsonl` のpendingを古い順にNDL by-ISBN照合。
- 一致→confirmed / 不一致→`kana-mismatch.tsv`(slug直しの人間判断へ) / **NDL未収載→pendingのまま残る=漏れない**。
- 比較は巻番号・上下巻ヨミ差(「〜1」「ジョウカン」)を許容(2026-07-06 偽陽性4→0実証)。
- ★**不一致の裁定型**(2026-07-14 15件実戦): **偽陽性**=NDL側の巻マーカー`(001)`/副題有無/スペース・中黒差=対応不要。
  **実修正型**=①頁kana末尾に巻数読み(イチ)混入→剥離 ②slug誤読(魔眼=ma-me型)→ヨミ基準でrename
  ③**NDL改題型**=増補改訂で実題が変わったのに楽天旧題のまま(アスペルガー→自閉スペクトラム症)。NDL by-ISBN=ground truthで題/kana/slug更新。
  ★**偽陽性の追加型(2026-08-08)**: NDL の `title_kana` に**著者ヨミが入っている**ことがある
  (ふたりぼっちの失楽園 9784396786304 = NDL title_kana「イッシキイチ」だが実体は著者「一色いち」のヨミ。
  題自体は「ふたりぼっちの失楽園」で楽天と一致)。**題が一致していてヨミだけ人名になっていたらNDL側の異常**=
  楽天ヨミが正。[[audit_title_eq_author]] の「title==著者名」型がヨミ側にも出る、と理解する。
  他の偽陽性型= 巻マーカー(「〜 イチ」「(001)」「アットコミックダイニカン」)/ NDLヨミが副題込みで長い、は従来どおり対応不要。
  ★**分冊版/合本型**(2026-08-31 ユーザ裁定): NDLヨミ末尾に「**ブンサツバン**(分冊版)」「**ガッポン**(合本)」が付く巻は、
  楽天題が通常巻(1)に見えても実体は分冊版/合本 = **非掲載が基本**(分冊のみしか刊行が無い作品のみ掲載だが、多分それはない)。
  → deny(preorder-deny.jsonl・理由に「分冊版」と明記)+ドラフト除去(preview+drafts両方)+kana-pending/kana-mismatch消し込み。
  denyはpreorder経路のみのゲートなので、後日通常単行本が刊行されればMADB月次で正規に入る(その旨をreasonに書く)。
  実例= 死に戻り聖女は毒家族と決別する / 極悪令嬢は仁義を貫く(講談社KCx 2026-10-29。楽天seriesName=KCxが分冊版印刷の暗示)。

## D. 締め: カレンダー/新刊データ更新

```
python scripts/_build-calendar.py data/manga.v2 data/calendar <当月YYYY-MM>                     # 本番フル
python scripts/_build-calendar.py .preview-data/manga public/calendar <当月>                    # preview(★srcはpreview自身。本番+ALLOWフィルタだとpreview限定ドラフトが落ちる=2026-07-06実害)
```
- 本番R2へ即時反映したい時: 変更月JSON+manifest+beyond.jsonをPUT(姫松対応の手順)。通常は週次のr2-sync overlayが運ぶ。
- previewのカレンダーは**ページ実在フィルタ必須**(subsetなのでフィルタ無し=リンク切れ)。

## 報告形式

A: 収穫N件(月分布)/①種4追加/②③④ドラフト数+保留 ・ B: 新着N/欠落M ・ C: 確定/不一致/残pending ・ D: カレンダー月別巻数。

## 旧手順の詳細(B系の worksheet 記入規律)

- `is_manga`/`slug`(ヘボン・勝手命名禁止)/`genres`(closed)/`demographic`/`catch`/`synopsis`(60-120字・ネタバレ無)/`tags`(確信のみ)。
- Layer1: 楽天booksGenreIdがdemographic裏取り(001=少年/002=少女/003=青年/004=レディース/001021=BL)。
- 発売直後はcaption空が普通→ゲートが保留にする=正常(捏造して通さない)。caption供給後の日次で自動的に通る。

## 関連
- 後退蒸留=`_distill_backward.py <年>` / preview管理=skill test-deploy / エンリッチ=skill enrich-catch-synopsis

### ★prevの意味(2026-07-10 取りこぼし22件事故 → 同日script化で解消)
- `preorders-prev.jsonl` = **最後に「処理」した時点のfull**(最後にharvestした時点ではない)。処理せず件数確認だけした日をprevにすると、その日の増加分が永遠にスルーされる。
- ★**更新は `_preorder-increment.py --commit-prev` のみ**(手動copy禁止)。incrementが①full退避を毎回上書き(stale穴封鎖) ②絞り済みLATESTへの二重実行をhash検知でabort ③処理完了後のcommit-prevでfull→prev昇格+prev.bak退避、まで面倒を見る。runbook手順10。

### ★ライブ回収の束ねルール(2026-07-10 明日もいい日=スピンオフ混同事故)
- **束ねは正規化題の完全一致**(副題ブロック込み)のみ。title先頭一致は禁止(本編とスピンオフが同じ書き出しのなろう系で誤マッチ)。
- 束ねた後に**巻番号の連続性を検査**((1)が2つ/系列飛び=別シリーズ混在signal)。
- ★**著者集合は判定根拠にしない**(ユーザ裁定: スピンオフで作画が増えるとは限らない=同一人・減る・総入替すべてある。著者軸=分裂の根本原因 [[clustering_unit_is_series]])。
- kana安全網32字の長題誤hold(不貞の子=基底40字なろう系)は**是正済**(2026-07-10): `clean_kana`が基底題の機械読み長と整合(比0.6〜1.5)なら32字超でも通す。副題汚染(読み長より膨らむ)は依然hold。gen-preview/midfill結線済。
