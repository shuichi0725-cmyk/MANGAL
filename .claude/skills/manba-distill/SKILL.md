---
name: manba-distill
description: マンバ蒸留して/マンバ蒸留続けて = manba.co.jp 経由で BookLive! の title_id を採取し、試し読みの空白を埋める。BookLiveには1リクエストも出さない(302 Locationを読むだけ)。resumable
---

# マンバ蒸留 (= 2026-09-07 新設。試し読み取得の代替経路)

**トリガー語 = 「マンバ蒸留して」「マンバ蒸留続けて」**(どちらも同じ=台帳から続きを回す)。

## なぜ在るか (= 3行で)

2026-08-29 の規制事故([[booklive_access_incident]])以降、BookLive! への直接クロールは**停止札**で禁じている。
一方うちが必要なのは **title_id ただ1つ**だけ = 試し読みURLは `title_id + 巻番号3桁` から**構築**する
([[tameshiyomi_url_is_constructed]])。manba.co.jp は作品ページに BookLive への遷移リンクを持ち、
その **302 Location** に title_id が入っている ⇒ **BookLiveを1回も叩かずに title_id が採れる**。

## ★絶対に守ること

- **リダイレクトを追わない**。`_NoRedirect` opener で 302 の `Location` ヘッダを読むだけ。
  追うと booklive.jp / valuecommerce にリクエストが出る = 停止札違反。実装済み、剥がすな。
- **直列のみ・並列禁止**。`_rate_gate.wait("manba", 5.0)`。manba は個人運営規模。既定 5秒/req を縮めない。
- **失敗を否定記録にしない**。429/403/5xx/timeout は `Abort` で**即中断し台帳に何も書かない**
  ([[feedback_no_negative_record_on_failure]])。書くのは manba が返した想定内の応答だけ。
- **偽採用より偽保留**。候補が1件に絞れない時は `ambiguous` で残す。埋めない。

## 手順 (= この3つだけ)

```
# 0. 現在地(★再開時はまずこれ。/clear後もここから状況が分かる)
python scripts/_manba-booklive-titleid.py --from-list --all --status

# 1. 続きを採取(既に台帳に在る作品は自動skip = 何度打っても重複しない)
python scripts/_manba-booklive-titleid.py --from-list --all --sleep 5 [--limit 100]

# 2. 非hitの再走(ゲート改善やmanba側更新の後だけ。普段は不要)
python scripts/_manba-booklive-titleid.py --from-list --all --redo nonhit --sleep 5
```
- 対象リストの正本 = `docs/production-diagnostics/no-tameshiyomi-active.tsv`
  (= 試し読み無し × 最終巻2025年以降 × 5巻以上。生成 = `python scripts/_list-no-tameshiyomi.py --csv`)。
  `--all` 無しだと「試し読み未検査分」だけに絞られる。**続きを回す時は --all** を付ける。
- 台帳 = **`data/seeds/manba-titleid.jsonl`(git追跡・追記のみ)**。★`.cache` ではない
  (/clear・PC移行・掃除で消えるため 2026-09-07 に移設)。1行1作品・同一slugは最終行勝ち。
- 長い(全量=482件で~80分)ので background 起動+ログ追記。`--limit` で刻んでよい。中断しても台帳から再開できる。

## 同定ゲート (= 誤同定は別作品のリンクを焼く。ここが本体)

| 段 | 条件 | 備考 |
|---|---|---|
| **T1** | 正規化題が**完全一致** かつ (著者overlap **or** 巻数±3) | 素直な一致 |
| **T2** | 正規化題が**包含一致** かつ 著者overlap **and** 巻数±3 | ★and必須。manbaは正式題(親題+外伝+副題)を使うので包含が緩く、片側だけだと同題アンソロジー/別作画の外伝を掴む |
| 版違いガード | manba題にだけ `無修正/完全版/特装版/合冊版/単行本版/マイクロ/…` が在る | `hit_edition_suspect` に降格 = **適用しない**(別商品のtitle_id) |

どの段でも**候補が1件に絞れた時だけ採用**。複数 = `ambiguous`。

## 実測 (2026-09-07 初回)

- 未検査53件: hit 38 / 版違い疑い 2 / 同定不能 4 / 一致なし 6 / ゲート不通過 2 / 取扱なし 1
- ★**答え合わせ20件**(既に title_id を持つ作品で同じ採取をかけ既知値と照合):
  hit 16 で **16/16 完全一致・誤同定 0%**(T1 14 / T2 2)。版違いガードは1件も誤降格しなかった。
- 取れない主因 = **manbaは版/形態ごとに別boardを立てる**(【単行本版】が2つ 等)。
  `ambiguous` の多くは manba 側の重複board(薬屋のひとりごと 80647=16巻 / 250285=17巻・著者同一)。

## 反映 (= ★別ステップ。GO必須)

採取は台帳まで。`data/tameshiyomi-map.json` への反映は**ユーザGO後**に行う(本番頁の表示が変わる)。
- 対象は **`result: "hit"` のみ**。`hit_edition_suspect` / `ambiguous` / `no_match` は入れない。
- 反映時は `scripts/_gen-tameshiyomi-map.py` の作法(末尾は本番頁の巻数まで構築で延長)に合流させる。
  マップは**ビルド時join入力**なので、変更後は preview/本番の再ビルドが要る
  (`.github/workflows/deploy-preview.yml` の paths に `data/tameshiyomi-map.json` が入っている)。
- 巻数一致のみで通った hit(著者が一致しなかったもの)は**目視1件**してから入れる。

## 報告形式

`--status` の数値行を引用する。採取N / hit / 版違い疑い / 同定不能 / 一致なし / 取扱なし、
と **残件と概算時間**。反映していないことを明示する。

## 関連
- 対象リスト生成 = `scripts/_list-no-tameshiyomi.py` / 事故則の正本 = [[booklive_access_incident]]
- 試し読み全体 = skill `tameshiyomi-harvest`(BookLive直叩き=停止札で凍結中) / [[tameshiyomi_url_is_constructed]]
