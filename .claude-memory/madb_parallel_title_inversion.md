---
name: madb_parallel_title_inversion
description: 【型・是正1件】MADBが途中巻から「表紙の欧文並列書名」を本題として登録し(@language:en 誤記つき)、種2が2 seriesに割れて先頭巻が消える
metadata: 
  node_type: memory
  type: project
  originSessionId: 58a222b6-cb74-4572-9905-4dacb5f8ddb9
  modified: 2026-09-10T04:24:13.648Z
---

2026-09-10 実踏(成仏させてよ! / 百地元 / 新潮社Bunch comics)。ユーザは ISBN 1本と頁URLだけ提示。

## 症状
頁 `let-s-go-nirvana` に 2-4巻しか無く、1巻(9784107727428)が**本番のどこにも無い**。
題も英語(`Let's go nirvana`)、kana は `Let'sgonirvana` の化け。

## 真因 = MADB cm101 の生データが途中巻から転倒している
`.cache/madb/metadata101-clean.json`:
```
1巻: "schema:name":["成仏させてよ!",{"@value":"ジョウブツサセテヨ !","@language":"ja-hrkt"}]   ← 正常
2巻: "schema:name":["Let's go nirvana",{"@value":"成仏させてよ","@language":"en"}]            ← 転倒
```
**本題と表紙の欧文並列書名が入れ替わり、言語タグまで ja-hrkt→en に誤記**されている。
取込器は1要素目を題として採るので、2巻以降だけ別 series_key になり種2が割れる:
- sid155149 『成仏させてよ!』= 1巻のみ → **src頁が無く頁化されない**([[orphan_series_promote_is_srcpage_driven]])
- sid131838 『Let's go nirvana』= 2-4巻 → これが本番頁になっていた

## 見分け方(NDLが決め手)
NDL は並列書名を `=` で表す。**この記法が出たら本型を疑う**:
```
巻=1 | 成仏させてよ! 1
巻=2 | Let&#39;s go nirvana = 成仏させてよ! 2      ← 「=」の右が日本語本題
```
楽天は全巻とも日本語題(「成仏させてよ！ N」)なので、NDL×楽天の2ソースで確定できる。
`python scripts/_lookup.py --creator "<著者>" --title "<題>"` が一発。

## 直し方
1. `series-merge.yml` に2 series_key を結線(main = **日本語本題側**)
2. `.cache/apply/key2slug.tsv` のキーを本題側へ、slug も本題ベースへ。`data/manga/<slug>.yml` を作り直す
   ([[new_page_creation_srcpage_key2slug]])
3. title_kana は **NDL の dcndl:transcription**(spaced)。`title-kana-fill.yml` に key=series_key で入れる
4. 欧文並列書名は捨てずに種3 `alternative_titles.en` へ(検索性)
5. slug が変わるので [[slug_rename_kills_slugkeyed_seed]] の後始末: catch-ja.json 等の**公開slugキー seed を移設**、
   slug-aliases.yml を張り替え(★逆向きの古い alias が残っていると**ループ**になるので必ず削除)

## ★slug-aliases に「逆向き」が居たら、それは退化の痕跡
本件は `joubutsu-sasete-yo: let-s-go-nirvana` が既に在った = **元は正題ベースの slug だったのに、
MADBの題が退化した時の一括slug適用で英題slugへ変わった**。つまり rename ではなく**復元**。
英題 slug を見たら CLAUDE.md の slug 規則(公式英題は slug に使わない)違反として疑ってよい。

## ★種3に「題から推測した捏造」が同居する
旧キーの種3 entry は `genres:[music,drama]` / `synopsis:「Let's go nirvanaを描く少年向け音楽ドラマ。」`
= Nirvana から音楽と推測した AI 生成(実際はヤクザ×禅寺のアクション)。
promote が種3 synopsis を使わない設計([[synopsis_ja_seed]])なのは正しい。**引き継がない**。

**Why:** 巻抜けの真因が「題の破損 → series分裂」であることがあり、巻だけ足しても直らない。
**How to apply:** 巻抜けで題が英語/カタカナに見えたら、まず NDL の `=` 記法を見る。
関連: [[series_fragmentation_rootcause]] [[volgap_diagnosis_order]] [[merge_needs_external_proof]]
[[series_merge_last_entry_wins]] [[targeted_reflect_author_credit_hole]]
