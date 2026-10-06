---
name: competitor-mangaseek-teardown
description: "【競合実測2026-09-17/10-06】mangaseek.net=インデックス78k。薄さ/sitemap/URL設計/Amazon APIは勝因でない=差は22年のドメイン年齢。★発売日一覧の突き合わせ=予約はMANGAL圧勝・発売後の続巻抜けでMANGAL内部の穴2つを発見"
metadata: 
  node_type: memory
  type: reference
  originSessionId: f0744808-d697-4640-bcd9-3f109fc1665e
  modified: 2026-10-06T13:41:18.850Z
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

## ★2026-10-06 2回目(ユーザ「Amazon APIが使えて10倍インデックス。参考になるか」)= 発売日一覧の突き合わせが収穫

- work頁も `.htaccess` で `/app/view_work.cgi` に内部リライト=**全部動的CGI**。robots は9/17から不変。
- Amazon API の使い道(見える範囲): `/sale/` Kindleセール(割引率)・ホームの Amazon おすすめ・新刊一覧に Kindle版を別行。
  新刊一覧の購入リンクは Amazon/楽天/紀伊國屋/セブンネットの4店(ISBNだけで作れる=APIは不要)。
  ★**インデックス差とは無関係**(Googleの評価にAPIは関係しない)。
- 発売日頁 `/item/release/YYYY-MM-DD.html`(robotsでDisallow)を3日分だけ取得し `public/shinkan/{ym}.json` とISBN照合:

| 発売日 | mangaseek(紙) | MANGAL | 共通 | MANGALのみ |
|---|---|---|---|---|
| 2026-11-06(1か月先) | 2 | **84** | 1 | 83 |
| 2026-10-06(当日) | 27 | 17 | 17 | 0 |
| 2026-09-17(19日前) | 151 | 111 | 110 | 1 |

  → **予約の先読みはMANGAL(楽天予約ハーベスト)が圧勝**。Amazon APIでも先の新刊は増えない。
  → 発売後はmangaseekが多い。差の中身 = 掲載対象外(成年/TL・画集・コンビニ版・自選集・アンソロ)+**既存頁の続巻の抜け(9/17で19冊・10/6で4冊)**。
  原因は2つともMANGAL内部: ①7/24の種4-auto全消しが未復元([[seed4_auto_wipe_accident]]・19冊中11冊) ②日次の増分方式で初回に適用されなかった巻が再分類されない([[daily_distill_hold_not_requeued]])。
  ついでに `Sランクパーティから解雇された〈呪具師〉` が**同じ14 ISBNの頁2枚**(esu-rank-…/s-rank-…)と判明。
- ★mangaseek から**データを取り込むのはしない**(みんなで作るDB+/item/はDisallow)。使ったのは「外部の物差し」として数日分の件数照合だけ。
  同じ穴はMANGAL内で「楽天取得台帳に在る×既存頁に題一致×頁にISBN無し」で自己検出できる。
- 他の機能(誕生日の漫画家/Web漫画更新/note感想の紹介/誰でも編集/X・Bluesky・はてなブログ・プレスセンター)はGoogle差の原因ではない。
  効くのは場外の露出=外部被リンクだけ(既知の結論どおり)。
- Amazon API 自体の現況 → [[openbd_eol_amazon_required]](PA-APIは2026-05-15停止→Creators API・直近30日10件)。
