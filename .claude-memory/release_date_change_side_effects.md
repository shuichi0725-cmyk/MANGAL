---
name: release_date_change_side_effects
description: "【型・実測】発売日を書き換えると①同巻に種2 ISBNが2本ある頁でpromoteのdedup勝者が入れ替わりISBNが頁から消える ②overrideが最終値に効かない経路がある(種4/canonical/overrides/renumber)。日付を触る全作業の前提"
metadata:
  type: project
---

★**発売日は「その巻の表示値」だけでなく、promoteの選択ロジックの入力でもある**。
書き換えると別のものが動く。2026-09-04のWikipedia日付掃引(2,410頁/10,810巻)で実測した2つ。

## ① 日付を変えると**ISBNが頁から消える**ことがある

同じ巻番号に**種2 ISBNが2本ある**頁(通常版と特装版/限定版など、末尾が隣接するISBN)では、
promote が代表を選ぶ `_dedup_key` が
`(volume-exclude?, -出版者記号の多数派頻度, 実効日付, 最小ISBN)` で、
★**実効日付に release-date-override が入る**(`_eff_date`)。
= **日付を揃えると勝者が入れ替わり、それまで表示されていたISBNが頁から丸ごと落ちる**。
負けた方は variant にも残らない。実測 8件/7頁(はじめの一歩106巻・いとしのムーコ5巻・
ペンギンの問題8巻・ラグーンエンジン1巻 等)。

→ ★**発売日を触る作業は、前後で「頁のISBN集合」を必ず比較する**。巻数だけ見ても気付けない
(総数は変わらないまま中身が入れ替わる)。

## ② override が**最終値に効かない頁**がある

promote には発売日を組み立てる経路が複数あり、`get_release_date_override()` が
最終出力に反映されない頁がある: **種4(volumes-supplement) / edition-canonical /
edition-overrides / renumber代表巻**の経路。
→ 一括で override を撒くと、**同じ頁の中で効いた巻と効かない巻が混ざる**。
実測126頁。[[wikipedia_release_date_is_authoritative]] の「頁内で基準を混ぜない」方針に反するので、
中途半端な頁は**その頁ごと取り消した**。

→ ★一括是正では **「override行の値 == 反映後の頁の値」を全行照合**し、
**一部だけ効いた頁**を洗って落とす。撒いた行数=直った巻数、ではない。

## 検算の型(このとき効いた)

- ★**ISBN走査は `variants` / `versions` も含めて再帰で `isbn13` を全部拾う**。
  `editions[].volumes` だけ見ると特装版が全部「消えた」ことになり、348件の偽陽性が出た。
- 作業前に作られていた `.cache/isbn-page-index.json`(`_exists.py --build`)を
  **前スナップショットとして使える**。
- コミット済み `data/manga-list-index.json` の `total_volumes` / `max_edition_volumes` は
  git に入っているので**作業前の巻数**として比較できる(manga.v2はgitignoreで差分が取れない)。
- ★`_reflect-targeted.py` の「★減少検出」は**詳細(スラッグ名・消えたISBN)をstderrに出す**。
  長時間ジョブでログをgrepで絞ると詳細行が落ちて後から追えない
  = **番人の出力を絞る時は詳細行も残すパターンにする**(2026-09-04に実際にやり直しになった)。

関連: [[wikipedia_release_date_is_authoritative]] [[gyara_type_regression_cleanup_state]]
[[volume_date_disorder_list]] [[edition_dedup_aoashi]]
