---
name: daily-distill
description: 日次蒸留 — 2本立て: A=楽天予約ハーベスト(未来の新刊・カレンダーの餌)/B=NDL新着回収(過去の納本)。+NDL照合キュー消化+カレンダー更新。トリガー「日次蒸留して」。
---

# 日次蒸留 (= 2026-07-06 全面改訂: 楽天予約が主柱に)

**2本立て**: A=楽天予約ハーベスト(未来〜当月の新刊。カレンダー/新刊棚の唯一の未来供給源) /
B=NDL新着回収(納本済み過去分)。毎日でなくてよい(間隔が空いても窓が自動で広がり取りこぼさない)。
理想運用: 日次蒸留して→(previewで)確認→週次蒸留して=週1本番更新。

## NEVER(禁止)

- **429/throttle即中断**(NDL・楽天とも1.1〜1.3s/req厳守。リトライ連打禁止)。
- **捏造禁止**: ヨミ/著者/genreを推測で埋めない。ヨミ=楽天仮確定+NDL照合キュー(下記)が正規ルート。
- **単巻先行登録禁止**: 途中巻でページ無し(④)は全巻回収が成立した作品だけドラフト化。
- **②③④は必ずpreview先行**(B裁定)。ユーザ確認GOなしに本番化しない。
- genre=closed vocabulary(master32)のみ+provisional。catch/synopsis=skill enrich-catch-synopsis の規律。

## A. 楽天予約パイプライン (= 主柱)

```
1. python scripts/_rakuten-preorder-harvest.py        # 6サブジャンル×発売日降順→未来〜当月全量(数分)
2. python scripts/_preorder-classify.py               # ①続巻/②新作作者既知/③新作作者新規/④途中巻頁無し/skip
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
