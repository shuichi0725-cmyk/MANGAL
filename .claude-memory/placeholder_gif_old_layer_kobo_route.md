---
name: placeholder_gif_old_layer_kobo_route
description: "【型・未着手 2026-09-11】旧作の仮書影(.gif)9,412巻は楽天紙では永久に埋まらない=Koboなら埋まる(HELLSING 2-4巻で実証)。周回queueが2019年以前を既定除外しているため未配線"
metadata: 
  node_type: memory
  type: project
  originSessionId: ac630d68-4de0-4259-a1f9-db37d14ed2a6
  modified: 2026-09-11T01:26:10.626Z
---

## 何が穴か

`data/seeds/cover-override.jsonl` の周回(skill `placeholder-cover-refresh`)は **2019年以前を既定で除外**する。
理由は正しい —「楽天**紙**を引き直しても旧作は `.gif` のまま」。だが**結論が一段足りない**:
★**楽天紙で埋まらないだけで、Kobo電子なら埋まる**(= [[cover_source_affiliate_only]] の Kobo 知見と、
仮書影周回が**接続されていない**)。[[cover_harvest_plan]] は `cover_url=null` 層の計画で、この層は**別物**
(cover_url が非nullなので監査上は「書影あり」に見え、どの検出器にも出ない)。

## 実測(2026-09-11 本番 data/manga.v2 1パス走査)

- cover_url 総数 273,320 / **仮 `.gif` = 9,412巻 (3.4%)**、またがる頁 **3,037**
- うち **同一頁に実物書影がある頁 = 1,410**(= 装丁目視ゲートの比較元が取れる = HELLSING と同じ形。ここが芯)
- 頁内が全部 `.gif` で比較元なし = 1,627(= ゲートは「頁内で装丁が統一されるか」判定に落ちる)
- 仮.gif の年代分布(頁の最古発売年): 1990年代 4,438 / 1980年代 1,975 / 2000年代 1,508 / 2020年代 861 / 1970年代 403

## 実証済みの手当て(= HELLSING 2-4巻、1件だけ適用済)

1. 楽天 BooksBook API を **title+author で全商品**引き、`.gif` が本当にその巻だけかを確認(別ISBNの重版に実物が無いことも)
2. Kobo EbookSearch API で電子版の巻別書影を取得
3. ★**装丁目視ゲート**: 同頁の紙の実物巻 ↔ 同巻の Kobo を並べて同装丁か確認([[kobo_cover_wrong_for_old_print]] の
   「別の版のカバーアートが付く」型が重いので、注意書きはゲートを外す理由にならない)
4. `cover-override.jsonl` へ追記 → `_reflect-targeted.py --only <slug>`

## 未決(ユーザ裁定待ち)

芯1,410頁を機械で回すか否か。回すなら Kobo API のレート(429が出やすい)と、装丁ゲートをどこまで
自動化するか(=コンタクトシート一括生成 → 割れた分だけAI、が [[feedback_agent_fanout_token_cost]] に沿う形)。
★件数を仕事量と読まないこと [[feedback_raw_count_is_not_worklist]] = Kobo に電子版が無い旧作は相当落ちる見込み。
