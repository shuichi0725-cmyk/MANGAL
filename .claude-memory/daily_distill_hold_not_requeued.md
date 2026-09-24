---
name: daily_distill_hold_not_requeued
description: 【未決・構造穴】日次蒸留で保留(hold)になったISBNは prev に入るので次回以降の増加分に二度と出ない=triage簿だけが痕跡。2026-09-02時点9件
metadata: 
  node_type: memory
  type: project
  originSessionId: 450de73b-b605-4986-907d-85f528e9a408
  modified: 2026-09-02T11:51:52.825Z
---

2026-09-02 日次蒸留で確認。`_preorder-increment.py` の fresh = latest − prev(ISBN差分)で、`--commit-prev` は
**保留(ドラフト化しなかった)ISBNも含めた full を prev に昇格**する。increment に hold の再投入は無い(grep で hold/triage 参照ゼロ)。
帰結: `preorder-triage.tsv` の `*_hold` 行(著者不明/ヨミ汚染/全巻回収不成立/slug生成不可)は**人が簿を消化しない限り永久に落ちる**。
月次蒸留で種2に入っても promote は元頁駆動なので新規シリーズは頁化されない([[orphan_series_promote_is_srcpage_driven]])。

2026-09-02 時点の保留9件(全て prev 在): みにくい小鳥の婚約(著者=出版社名) / 六歳の王女ですが(ヨミ汚染) /
ex_mid 7件(夜明けをつれてくる犬・腹パン系ダンジョン配信者・二度目の人生・S級ギルド・ハズレ職・侯爵令嬢リディア・不純すら純情=先行巻がキャッシュに無い)。

**Why:** 「保留=後で通す」つもりの行が、機構上は「二度と来ない」になっている。捏造しない方針で hold を増やすほど取りこぼしが溜まる。
**How to apply:** `_preorder-increment.py` に **hold再投入**を焼く: triage の `*_hold` ISBN のうち ISBN索引(`.cache/isbn-page-index.json`)に無い物を
full harvest から拾って fresh に足す(=毎回再分類→材料が揃った日に自然に通る)。ex_mid の「全巻回収不成立」は楽天 live 題検索の fallback を
`_preorder-gen-midfill.py` に足すと大半が通る(先行巻が2026年刊でローカルcacheに無いだけ)。
併せて未着手の小穴: `clean_kana` は題に巻数があっても**空白無しの末尾巻読み**(…デスイチ)を剥がさない(精霊聖女で手直し)。
KANA_VOLNUM レビューは slug 側しか見ないので title_kana に漏れる。[[intake_manifest_ledger_live]]

## 2026-09-07 追記: B柱(NDL)側の同型は封鎖した

`_distill_backward.py --plan` は `ai-todo.jsonl` を**毎回まっさら再生成**するので、worksheet に
`is_manga: false` と裁定を書いても**翌日また同じ候補が並ぶ**(A柱の hold と同じ「二度と消えない/通らない」構造)。
→ plan に **恒久除外簿 `data/seeds/preorder-deny.jsonl` の読み込みを追加**(A柱と同じ台帳を両柱で共有)。
裁定済み3件(クレヨンしんちゃんパニック=コンビニ再編集 / とっておきドラえもん=傑作選 / 花丸ハムスターほおぶくろセレクション=傑作選復刊)
を除外して **掲載可worksheet待ち 5→2**。残2件は caption 無しで genre が確定できず登録保留(捏造しない)。

★A柱(preorder hold の再投入)は**まだ未着手**= 上の How to apply がそのまま残タスク。

## ★2026-09-24 ユーザ「日次蒸留時に保留になっている物をみなおしてほしい」→ 一括見直し(commit a3d771be8)
- ★triage は**毎回上書き**なので、過去の保留は **git の全版(37版)を和集合**して拾う(1,046件)。
  現状 = 本番掲載済376(別経路で入った)/ドラフト化2/**未解決668**。書誌は過去harvest(`.cache/preorders/preorders-*.jsonl`)から659件引けた。
- ★保留行は**理由が slug 列にずれていた**(見出し8列に7列で書いていた)= reason 列は空。6か所を8列に是正済。
  過去版を読む時は hold 行だけ `slug` 列を理由として読むこと。
- **現行分類器で再分類**(スクリプトを別出力先へ sed で差し替えて実行=本番の日次台帳 classified.json/triage を汚さない):
  zokkan 196 / new1a 80 / new1b 43 / ex_mid 303 / skip 37。= 7月以降の分類器改良と頁の増加で**続巻の2割が今なら通る**。
  - 続巻: **版違い疑い17件は自動適用から外す**(題に 愛蔵版/完全版/大全集 等があり頁題に無い=通常版に混ぜてしまう)。
    残り179件を apply-zokkan で適用 → 種4 +152冊/148頁。preorder-pages 由来16件は直接追記(上下は 上/下ラベル+発売済なら completed)。
  - 反映で**既定の slug 改名が33頁ぶん同時に適用**された(alias は全部既存)→ prune 台帳に旧slugを足した。
- **残り**(`docs/production-diagnostics/preorder-hold-review-2026-09-24.tsv`): ex_mid 303 / new1a 80 / new1b 43
  = preview ドラフト生成→ユーザ確認が要る(未実施)/ 版違い疑い17 / 巻番号不明・同巻既在 11。
- ★**構造穴(再投入が無い)は依然未実装**。次にやるなら: 保留を永続台帳に積み、`_preorder-increment.py` が毎回
  「未解決の保留」を fresh に混ぜて再分類する(今回の和集合+再分類を自動化する形)。
