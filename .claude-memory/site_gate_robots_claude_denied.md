---
name: site-gate-robots-claude-denied
description: 【門】任意サイトを魚で取る前に scripts/_site_gate.py(止め札→robots.txt→サイト別間隔)を通す。2026-10-08 実測で ピクシブ百科事典・マンバ・ebookjapan が robots で Claude を名指し拒否。★マンバ蒸留の柱と食い違う可能性=ユーザ裁定待ち
metadata:
  node_type: memory
  type: reference
  originSessionId: 60837ea9-16b4-4ef2-9200-391e3397c8aa
  modified: 2026-10-08T13:19:14.016Z
---

2026-10-08、要素収集の柱([[element-harvest-pillar-state]])で任意サイトを魚(TinyFish)で取ることになり、
[[bookwalker_harvest_forbidden]] の「新しい情報源はまず robots.txt を取る。ClaudeBot が Disallow ならそこで終わり」を道具にした。

## 道具
`scripts/_site_gate.py` = `check(url)` が 止め札(DENY: booklive.jp / bookwalker.jp / amazon)→ robots.txt を判定、`pace(url)` がサイト別に最短5秒(`_rate_gate`)。
`python scripts/_site_gate.py <URL>` で可否だけ見られる(頁は取らない)。`--selftest` あり。
- 保守側の判定: 全クローラ(*)向けの規則と、`claude*` / `anthropic*` で始まる名指しの組の**両方**に許されたパスだけ可。
- robots が 401/403・届かない = 「確かめられない」= 取らない(fail-closed)。
- ★`urllib.robotparser` は使っていない(先勝ち・ワイルドカード非対応で誤判定した前例 = [[feedback_absence_needs_verification]])。最長一致+`*` `$` を自前で解釈し、自サイトの稼働中ルールを自己検査に入れてある。
- ★robots は URL の実ホスト(www. 付き)に取りに行く(www を外すと引けないサイトがある=実踏)。
- ★このPCの Python は証明書の鎖を検証できないサイトがある(紀伊國屋で実踏)→ その時だけ robots.txt を魚経由で読む。

## 2026-10-08 の実測
| サイト | 結果 |
|---|---|
| dic.pixiv.net(ピクシブ百科事典) | **不可**: robots が anthropic-ai / ClaudeBot を名指しで拒否 |
| manba.co.jp(マンバ) | **不可**: anthropic-ai / ClaudeBot / Claude-Web に `Disallow: /`。冒頭に方針文「基盤モデル学習・広域コーパス向け(GPTBot, ClaudeBot…)は拒否、AI検索・引用向け(Claude-SearchBot 等)は一部パスを除き許可」 |
| ebookjapan.yahoo.co.jp | **不可**: ClaudeBot を名指しで拒否 |
| w.atwiki.jp(アニヲタWiki)/ mangapedia.com / cmoa.jp / piccoma.com / mechacomic.jp / bookmeter.com / shogakukan.co.jp / magazine.jp.square-enix.com / tbs.co.jp / note.com / hatenablog / ameblo / animatetimes / natalie.mu | robots は可 |
| dic.nicovideo.jp(ニコニコ大百科)・animegaphone.jp | robots は可だが魚が 403 で拒まれる |
| kinokuniya.co.jp | robots は可(魚経由で読んだ)だが魚の取得が target_unreachable(9月の外部エンリッチでは取れていた) |
| shogakukan.co.jp の書籍頁 | 魚が empty_content を返すことがある |

## ★未裁定: マンバ蒸留との食い違い
既存の柱 `manba-distill`(manba.co.jp の 302 Location から BookLive title_id を採取・ブラウザ風UA)は、上の robots の方針と食い違う可能性がある。
skill manba-distill には robots への言及が無い。**2026-10-08 にユーザへ報告済み・裁定待ち**(私は柱を止めても変えてもいない)。

**How to apply**: 新しいサイトを取りに行く処理を書く時は `_site_gate.check` → `pace` を必ず通す。門が不可と言ったサイトを WebFetch 等の別経路で取らない。
関連: [[booklive_access_incident]] [[bookwalker_harvest_forbidden]] [[manba_booklive_titleid_route]]
