---
name: drop_page_redirect_chain
description: 頁をdropしたら、その頁を「指している」既存リダイレクトを最終行先へ張り替える
metadata:
  type: feedback
---

頁を統合・廃止する時、`public/_redirects` には **その頁を行き先にしている旧slugの行**が既に在ることが多い
(過去のslug是正の産物)。放置すると `旧slug → 廃止slug → (404)` の**死んだ連鎖**になる。
Cloudflare の `_redirects` は連鎖を辿らない。

**Why**: 2026-08-08 ワイルド7で `wild-7-1969` 等5頁を廃止した際、`/wairudo-7-1969 /wild-7-1969 301` が
5本残っていた。旧romaji slugから来たユーザが404に落ちる。

**How to apply**:
1. drop する slug ごとに `_redirects` を**行き先側でも**検索し、該当行を最終行先へ書き換える。
2. 新規行の重複チェックは **行頭一致**(`l.split()[0]`)で行う。単純な部分文字列判定は
   「行き先として出現している」行に誤ヒットして**追記がスキップされる**(実際に4本落とした)。
3. `data/slug-aliases.yml` にも old→new を追記。
4. R2上の実フォルダは残るので、次の週次蒸留で `_r2-sync.py --prune` を付ける([[r2_orphan_pages_prune_missing]])。

関連: [[reflect_protocol_fast]] [[slug_collision_year_rule]] [[wild7_franchise_state]]

## ★2026-10-08 追記: 正本は slug-aliases.yml だけ(public/_redirects は生成物)
- `public/_redirects` と KV の `redirects.json` は **`_gen-redirects.py` が `data/slug-aliases.yml` から毎回作り直す**。
  `_redirects` に手で足した行は、週次の `_kv-redirects-sync.py` の再生成で**黙って消え、KV にも入らない**。
- 実踏: ホロビート改名(horobiito→horobeat・6b4d956ec)は `_redirects` に1行足しただけ → 週次で消えた →
  `slug-aliases.yml` に `horobiito: horobeat` を足して KV 再投入(31,573件)。旧slugが本番未公開だったので実害なし。
- slug を改名したら **`slug-aliases.yml` に old: new を書く**(上の手順3)。`_redirects` を直接いじらない。
