---
name: percase-fix
description: 作品名+リンク(Wiki/NDL)を渡されたら per-case で版/巻/ISBN是正(イアラ式)。汚染除去・版分離・巻補完・variants の選び方まで
---

# per-case是正 (= イアラ式。ユーザが作品名+Wiki/NDLリンクを出したら)

## NEVER (最重要)
- **推測やダミーで埋めない**([[feedback-accuracy-is-the-goal]])。不明=止めて報告
- **単一ソース+解釈で上書きしない**。Wiki×楽天×NDL の2ソース以上一致で確定
- NDL/楽天 live は **1.2-1.3秒/リクエスト**厳守。429=即中断(逐次保存しつつ)
- NDL不在=不存在と断じない(BL/小出版はNDL収録が弱い=不測ノ恋情の教訓)。楽天live(outOfStockFlag=1)が一次手段
- canonical に「現ページの現状」を凍結しない(汚染ごと凍結する=うる星の失策)。**外部権威(Wiki)から作る**
- 価格を表示に出さない(内部ソートのみ可)
- ★**種4に qid を書かない**(種2のqid=作者QID→作者の全作品に巻が注入される。うしおととら→藤田14作事故 2026-07-07。series_keysで十分)
- ★**種4の release_date はフル日付でも必ず引用符**(`'1986-09-18'`。裸だとYAMLがdate型に解釈されpromoteがクラッシュ)

## 2026-07-07 promote側で封鎖済の罠(知っておく)
- 混入巻除去(volume-exclude)+真巻登録(種4)のセット: 旧来は「混入巻が番号占有/偽日付タイ/ISBN無し幽霊」の三重の壁で真巻が弾かれた→全て封鎖済(こち亀vol1)。同時に書いてよい
- edition-override頁の出版年: 確定巻と既存年が非交差なら自動再計算(上杉謙信)。交差時は連載年保持(タッチ)
- renumber統合の代表巻=(sid,巻番号)単位(1sidに別書籍複数でも取りこぼさない=VPアンソロ第3集)

## 調査手順
1. `python scripts/_ledger.py <slug>` で操作履歴+holes / `python scripts/_exists.py --title/--isbn` で本番存在
2. 現ページ dump: editions×volumes×ISBN帯(prefix)×日付 → 混在/欠け/幽霊を分類
3. Wikipedia 書誌節を WebFetch(巻別ISBN・発売日が権威)。ISBN-10→13変換は check digit 再計算
4. 楽天キャッシュ照合: `.cache/isbn-title-map.json`(題)→ 日付/書影は `.cache/rakuten-isbn-delta.jsonl`。無ければ楽天live(openapi.rakuten.co.jp+Referer/Origin header、_complete-edu-gaps.py の search() 参照)
5. NDL SRU(title+creator)。「臨場」等の一般語title単独クエリはtimeoutする→creator束縛+失敗スキップ続行

## 型別の直し方(どの seed を使うか)
| 型 | 症状 | 直す場所 |
|---|---|---|
| 単純巻抜け | 欠番・ISBN確定可 | **種4** volumes-supplement.yml(series_keys=既存ISBN→db-v2逆引き) |
| 幽霊巻 | ISBN無し・実在しない巻番号 | **edition-overrides.json**(実在巻だけで再構築) |
| 版混在(奇子型) | 別版ISBNが枠に滲む・日付逆行 | 小規模=edition-overrides / 大物・刷タブ要=**edition-canonical/*.yml**(versions対応済) |
| 別作混入(Frankenstein) | 別作品の巻が枠に居る | 移設=種4(本来頁keys)+混入頁は volume-exclude or page-dedup |
| スピンオフ不可視 | 同名スピンオフのページが無い | **merge-exceptions.yml**(id対称block)+series-keep.yml(spinoff旧作drop救済)+種4gap fill |
| 断片重複 | 同ISBNが2頁に | **page-dedup.yml**(drop→canonical) |
| 特装が主枠 | 特装ISBNが通常枠 | **special-edition-fix-redo2.yml** に correction 追加(同一出版社コードのみ。跨ぎはoverride直書きvariants) |
| 書影無し | covers seed に無い | covers.jsonl.gz へ追記(**キーは isbn13/cover_url**。url ではない) |

## 適用と検証
- changelog(volume-gaps-changelog.jsonl 等)に1行 → **反映して**(reflect-targeted skill)
- 検証: 再生成後の頁 dump で 欠0・prefix整合・variants/書影 を数字で確認
- 新規発見の系統バグは検出器化を検討(_audit-solo-truncated.py / _audit-volume-output.py が前例)
