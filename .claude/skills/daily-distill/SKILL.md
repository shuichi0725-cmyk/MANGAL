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
- **429/throttle即中断**(NDL・楽天とも1.1〜1.3s/req厳守。リトライ連打禁止)。
- **捏造禁止**: ヨミ/著者/genreを推測で埋めない。ヨミ=楽天仮確定+NDL照合キュー(下記)が正規ルート。
- **単巻先行登録禁止**: 途中巻でページ無し(④)は全巻回収が成立した作品だけドラフト化。
- **②③④は必ずpreview先行**(B裁定)。ユーザ確認GOなしに本番化しない。**previewは"今回のみ"**(増加分−過去draft−捏造kana)に絞る。ユーザは「前回見た」に敏感で正確=水増しを即見抜く。
- ★**1回のAPIで全フィールド捕捉**(2026-07-09 ユーザ指摘 [[acquire_all_obtainable_info]]): 楽天API/harvestは書影だけでなく **itemCaption(あらすじ=genre/catch/synopsis元)/booksGenreId/itemPrice/subTitle/affiliateUrl** を返す。**書影だけ取って捨てるな**。captionを`_preorder_draft.rakuten_caption`に保存→genre(master32・provisional)/catch/synopsisを生成(caption有れば発売前でも付く)。書影のためにAPIを叩くなら同じ応答からcaptionも必ず取る。
- genre=closed vocabulary(master32)のみ+provisional。catch/synopsis=skill enrich-catch-synopsis の規律。
- ★**改善は即興でなくskill/scriptに焼く**: 実行中に穴を見つけたら手動で継ぎ足すな。scriptにゲート追加→commitしてから進む(即興は次回消える+報告が水増しでブレる)。

## ★毎日の実行手順 (= runbook・この順で回す。2026-07-09 確立。ツール把握用)

前提: `git status` clean。楽天/NDL認証env有り。

| # | やること | ツール(コマンド) |
|---|---|---|
| 1 | 予約harvest | `python scripts/_rakuten-preorder-harvest.py` |
| 2 | ★**増加分に絞る**(必須) | `python scripts/_preorder-increment.py`  ← prev差分+過去draft除外。飛ばすと水増し |
| 3 | 分類 | `python scripts/_preorder-classify.py` |
| 4 | ①続巻→種4+反映 | `python scripts/_preorder-apply-zokkan.py` → `python scripts/_reflect-targeted.py --only <touched> --push` |
| 5 | ②③新作ドラフト | `python scripts/_preorder-gen-preview.py new1a` ; `new1b` |
| 6 | ④途中巻ドラフト | `python scripts/_preorder-gen-midfill.py` |
| 7 | genre付与 | 各draftの`_preorder_draft.rakuten_caption`(harvest捕捉済)を読み、master32から**provisional付与**(captionあれば発売前でも可)。無い分はcover用API時に同応答からvol1 caption捕捉 |
| 8 | Cヨミ照合 | `python scripts/_verify-kana-pending.py --limit 200` |
| 9 | **検査**(下記チェックリスト) | 欠け>0なら原因調査 |
| 10 | 索引+暦+push | `python scripts/_build-list-index.py .preview-data/manga .preview-data` ; `python scripts/_build-calendar.py .preview-data/manga public/calendar <当月>` ; commit+push |
| 11 | B NDL新着(任意) | `python scripts/_distill_daily.py --discover`→`--plan`→`--emit` |

### ★生成後チェックリスト (= 全部2026-07-09に実際踏んだ罠。毎回数える)
- □ **kana純カタカナ**(漢字/ひらがな0)。楽天ヨミ無し/汚染は**捏造せずhold**が効いているか
- □ **slug=辞書装置**(`_slug_kana_lib`経由)・英語綴り(summer-blend等)。pykakasi再発明でない。英語出ない語は`katakana-english.yml`に追加
- □ **全巻に発売日**(回収先行巻=種2 db-v2から引く)+**書影**(実URL=harvest/covers seed/楽天API。★構築禁止)
- □ **genre**=captionからprovisional・master32のみ(捏造なら空)
- □ **作者kana**=楽天authorKana由来 or 空(捏造なし。漢字混入0を確認)
- □ **preview=今回のみ**(増加分・前回draft混入0・捏造kana hold済)
- □ **索引skip 0**(Zod検証で落ちる頁=検索に載るが404)

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
   → promote --only <touched> → reflect --only <touched> --push   (①は確認不要で即出せる)
4. python scripts/_preorder-gen-preview.py new1a      # ②ドラフト生成(→.preview-data)
   python scripts/_preorder-gen-preview.py new1b      # ③(著者マスタ新規はヨミ=楽天仮)
   python scripts/_preorder-gen-midfill.py            # ④(キャッシュ全巻回収成立分のみ)
   → preview索引再構築 → push → ★ユーザ確認(段階: ①→②→③→④の順で1クラスずつ)
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
3. **scope外**: 特装/限定版・アンソロ・傑作選/再編・コンビニ本(★題でなくimprint判定=集英社リミックス/プラチナコミックス/Gコミックス)・画集/ガイド/BOX・雑誌/別冊・アメコミ翻訳・(仮)
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
