---
name: competitor-mangaseek-teardown
description: "【競合実測2026-09-17】mangaseek.net=sitemap158,139・インデックス78k(49%)。薄さ/sitemap作り込み/URL設計は勝因でない(全部うちより粗い)。差は22年のドメイン年齢"
metadata: 
  node_type: memory
  type: reference
  originSessionId: f0744808-d697-4640-bcd9-3f109fc1665e
  modified: 2026-09-17T09:48:23.782Z
---

ユーザ「mangaseek は Google に78,000インデックスされている。参考になることある?」→ robots/sitemap/実HTMLを実測した結果。

## 規模

| | mangaseek | MANGAL |
|---|---|---|
| sitemap URL | **158,139** | 91,024 |
| インデックス | ~78,000(**49%**) | 2,760(**3.0%**) |
| 内訳 | work 110,030 / person 30,269 / item-release 12,815 / magazine 2,715 / publisher 580 / award 271 | manga 69,352 / author 20,203 / ハブ 1,469 |

## ★潰せた仮説(これが収穫。全部「勝因ではない」)

- **薄さは理由じゃない**: `work/1.html` は**本文1,891字**、しかも「商品は未登録です」= **1巻も紐付いていない頁**。それで通っている。
  → うちの GSC「クロール済み-未登録35件」と同じ結論を外部事例が裏書き。**インデックス目的の本文/メタ磨きは効かない**。
- **sitemapの作り込みも理由じゃない**: `lastmod`/`changefreq`/`priority` が**全部ゼロ**、名前空間が **2005年の `sitemap/0.84`**。うちの「lastmod見送り」判断は正しかった。
- **URL設計も理由じゃない**: `/work/1.html` = 連番、slugですらない。

残る差 = **2004年開設(work/1 の初投稿 2004-04-25)の22年**。うちは2ヶ月。

## 真似してはいけない点

- `Disallow: /item/` を出しているのに sitemap に `/item/release/*` を **12,815本載せている**(自分でブロック)。発売日頁の内部リンク144本中**78本がそのブロック先**。
- 理由が robots.txt のコメントに書いてある: 「session_status.cgi が 2026-08-29 だけで **38,966回** Perl fork された」= **動的CGIだからクロールを削るしかない**側。
  うちは静的R2で真逆(クロールは増やしたい)ので、負荷を理由に絞る発想は持ち込まない。
- `aggregateRating` 構造化データを持つが実ユーザ投票。うちが AniList スコアで同じことをやるのは不可。

## ★ここから立てた仮説は Bing 実測で否定された

「person頁が内部リンク225本(work116/magazine53)に対しうちの著者頁は4本 → 著者頁を太らせろ」
→ **うちのクエリ実態が違った**([[bing_search_reality_2026_09]])。他社の構造から仮説を立てたら、**自サイトの実測で必ず検算する**。
関連: [[feedback_raw_count_is_not_worklist]] [[seo_index_coverage_state]]
